"""
高级页面内容提取工具。

支持：
- 提取完整 HTML 源码
- 提取结构化页面信息（所有链接、文本内容等）
- 提取可跳转的 URL 列表
- 支持 LLM 分析 HTML 内容
"""

from typing import List, Optional, Dict, Any
from urllib.parse import urljoin
import json

from playwright.sync_api import Page, TimeoutError


def extract_full_html(page: Page, selector: Optional[str] = None) -> str:
    """
    提取页面的完整 HTML 源码。
    
    :param page: Playwright Page 对象
    :param selector: 可选的 CSS 选择器，如果提供则只提取该元素的 HTML，否则提取整个页面
    :return: HTML 源码字符串
    """
    try:
        if selector:
            element = page.locator(selector).first
            html = element.inner_html()
        else:
            html = page.content()
        return html
    except Exception as e:
        print(f"[page_content_extractor] Error extracting HTML: {e}")
        return ""


def extract_all_links(page: Page, current_url: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
    """
    提取页面中所有可跳转的链接（标题 + URL）。
    
    :param page: Playwright Page 对象
    :param current_url: 当前页面 URL，用于解析相对路径
    :param limit: 可选的最大提取数量，None 表示提取全部
    :return: 链接列表，每个链接包含 title 和 url
    """
    results: List[Dict[str, str]] = []
    
    try:
        # 查找所有链接元素
        links = page.locator("a[href]")
        count = links.count()
        
        if limit:
            count = min(count, limit)
        
        for idx in range(count):
            try:
                link = links.nth(idx)
                
                # 提取文本标题
                title = ""
                try:
                    title = (link.inner_text() or "").strip()
                    # 如果标题为空，尝试获取 title 属性
                    if not title:
                        title = link.get_attribute("title") or ""
                except Exception:
                    pass
                
                # 提取 URL
                href = link.get_attribute("href") or ""
                if href:
                    # 规范化 URL
                    normalized_url = urljoin(current_url, href.strip())
                    if normalized_url and normalized_url.startswith(("http://", "https://")):
                        results.append({
                            "title": title or normalized_url,
                            "url": normalized_url
                        })
            except Exception:
                continue
        
        return results
    except Exception as e:
        print(f"[page_content_extractor] Error extracting links: {e}")
        return []


def extract_all_elements(
    page: Page,
    element_types: Optional[List[str]] = None,
    include_text: bool = True,
    include_links: bool = True,
    limit_per_type: Optional[int] = None,
) -> Dict[str, Any]:
    """
    提取页面中的所有元素（链接、按钮、输入框等）。
    
    :param page: Playwright Page 对象
    :param element_types: 要提取的元素类型列表，如 ['a', 'button', 'input']，None 表示提取所有类型
    :param include_text: 是否包含文本内容
    :param include_links: 是否包含链接
    :param limit_per_type: 每种类型的最大提取数量
    :return: 结构化元素字典
    """
    if element_types is None:
        element_types = ['a', 'button', 'input', 'textarea', 'select', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']
    
    result = {
        "links": [],
        "buttons": [],
        "inputs": [],
        "headings": [],
        "text_content": ""
    }
    
    try:
        current_url = page.url
        
        # 提取链接
        if include_links and 'a' in element_types:
            result["links"] = extract_all_links(page, current_url, limit=limit_per_type)
        
        # 提取按钮
        if 'button' in element_types:
            try:
                buttons = page.locator("button, input[type='button'], input[type='submit']")
                count = buttons.count()
                if limit_per_type:
                    count = min(count, limit_per_type)
                
                for idx in range(count):
                    try:
                        btn = buttons.nth(idx)
                        text = (btn.inner_text() or btn.get_attribute("value") or "").strip()
                        btn_type = btn.get_attribute("type") or "button"
                        result["buttons"].append({
                            "text": text,
                            "type": btn_type
                        })
                    except Exception:
                        continue
            except Exception:
                pass
        
        # 提取输入框
        if 'input' in element_types:
            try:
                inputs = page.locator("input, textarea, select")
                count = inputs.count()
                if limit_per_type:
                    count = min(count, limit_per_type)
                
                for idx in range(count):
                    try:
                        inp = inputs.nth(idx)
                        inp_type = inp.get_attribute("type") or inp.tag_name().lower()
                        name = inp.get_attribute("name") or ""
                        placeholder = inp.get_attribute("placeholder") or ""
                        result["inputs"].append({
                            "type": inp_type,
                            "name": name,
                            "placeholder": placeholder
                        })
                    except Exception:
                        continue
            except Exception:
                pass
        
        # 提取标题
        if any(f'h{i}' in element_types for i in range(1, 7)):
            try:
                headings = page.locator("h1, h2, h3, h4, h5, h6")
                count = headings.count()
                if limit_per_type:
                    count = min(count, limit_per_type)
                
                for idx in range(count):
                    try:
                        heading = headings.nth(idx)
                        level = heading.evaluate("el => el.tagName.toLowerCase()")
                        text = (heading.inner_text() or "").strip()
                        if text:
                            result["headings"].append({
                                "level": level,
                                "text": text
                            })
                    except Exception:
                        continue
            except Exception:
                pass
        
        # 提取页面主要文本内容
        if include_text:
            try:
                # 移除脚本和样式标签后提取文本
                text_content = page.evaluate("""
                    () => {
                        const clone = document.cloneNode(true);
                        const scripts = clone.querySelectorAll('script, style, noscript');
                        scripts.forEach(el => el.remove());
                        return clone.body ? clone.body.innerText : '';
                    }
                """)
                result["text_content"] = (text_content or "").strip()
            except Exception:
                pass
        
        return result
    except Exception as e:
        print(f"[page_content_extractor] Error extracting elements: {e}")
        return result


def extract_blog_content(
    page: Page,
    selector: Optional[str] = None,
) -> Dict[str, Any]:
    """
    提取博客/文章正文内容。
    
    智能提取页面中的主要内容，包括：
    - 标题
    - 正文文本
    - 作者信息（如果可识别）
    - 发布时间（如果可识别）
    
    :param page: Playwright Page 对象
    :param selector: 可选的 CSS 选择器，限制提取范围（如主要内容区域）
    :return: 包含博客内容的字典
    """
    result = {
        "title": "",
        "content": "",
        "author": "",
        "publish_time": "",
        "url": page.url
    }
    
    try:
        # 如果指定了选择器，只在该区域内提取
        target_element = page.locator(selector).first if selector else page
        
        # 提取标题（优先查找h1，其次h2）
        try:
            title_elem = target_element.locator("h1").first
            if title_elem.count() > 0:
                result["title"] = (title_elem.inner_text() or "").strip()
            else:
                title_elem = target_element.locator("h2").first
                if title_elem.count() > 0:
                    result["title"] = (title_elem.inner_text() or "").strip()
        except Exception:
            pass
        
        # 提取正文内容（智能提取主要文本区域）
        try:
            # 尝试多种策略提取正文
            # 策略1: 查找常见的文章内容容器
            content_selectors = [
                "article",
                "[role='article']",
                ".content",
                ".article-content",
                ".post-content",
                ".note-content",
                "main",
                ".main-content"
            ]
            
            content_text = ""
            for sel in content_selectors:
                try:
                    content_elem = target_element.locator(sel).first
                    if content_elem.count() > 0:
                        content_text = (content_elem.inner_text() or "").strip()
                        if len(content_text) > 100:  # 如果内容足够长，使用它
                            break
                except Exception:
                    continue
            
            # 策略2: 如果没有找到特定容器，提取整个页面的主要文本
            if not content_text or len(content_text) < 100:
                content_text = target_element.evaluate("""
                    (element) => {
                        // 移除脚本、样式、导航、页脚等无关内容
                        const clone = element.cloneNode(true);
                        const toRemove = clone.querySelectorAll(
                            'script, style, noscript, nav, header, footer, .nav, .header, .footer, .sidebar, .ad, .advertisement, .comment'
                        );
                        toRemove.forEach(el => el.remove());
                        
                        // 提取文本内容
                        return clone.innerText || '';
                    }
                """)
                content_text = (content_text or "").strip()
            
            result["content"] = content_text
        except Exception as e:
            print(f"[page_content_extractor] Error extracting blog content: {e}")
        
        # 尝试提取作者信息
        try:
            author_selectors = [
                ".author",
                "[class*='author']",
                "[class*='writer']",
                ".byline",
                "[itemprop='author']"
            ]
            for sel in author_selectors:
                try:
                    author_elem = target_element.locator(sel).first
                    if author_elem.count() > 0:
                        result["author"] = (author_elem.inner_text() or "").strip()
                        if result["author"]:
                            break
                except Exception:
                    continue
        except Exception:
            pass
        
        # 尝试提取发布时间
        try:
            time_selectors = [
                "time",
                "[datetime]",
                ".publish-time",
                "[class*='time']",
                "[class*='date']",
                "[itemprop='datePublished']"
            ]
            for sel in time_selectors:
                try:
                    time_elem = target_element.locator(sel).first
                    if time_elem.count() > 0:
                        time_text = time_elem.get_attribute("datetime") or time_elem.inner_text()
                        if time_text:
                            result["publish_time"] = time_text.strip()
                            break
                except Exception:
                    continue
        except Exception:
            pass
        
        return result
    except Exception as e:
        print(f"[page_content_extractor] Error in extract_blog_content: {e}")
        return result


def extract_page_content(
    page: Page,
    current_url: str,
    mode: str = "links",
    selector: Optional[str] = None,
    limit: Optional[int] = None,
    include_html: bool = False,
) -> Dict[str, Any]:
    """
    综合页面内容提取工具，支持多种提取模式。
    
    :param page: Playwright Page 对象
    :param current_url: 当前页面 URL
    :param mode: 提取模式，可选值：
        - "links": 提取所有可跳转的链接（标题+URL）
        - "all": 提取所有元素（链接、按钮、输入框、标题、文本等）
        - "html": 提取 HTML 源码
        - "full": 提取所有内容（包括 HTML）
        - "blog_content": 提取博客/文章正文内容（标题、正文、作者、发布时间等）
    :param selector: 可选的 CSS 选择器，限制提取范围
    :param limit: 可选的最大提取数量（对链接有效）
    :param include_html: 是否在结果中包含 HTML 源码
    :return: 提取结果字典
    """
    result = {
        "url": current_url,
        "mode": mode,
        "data": {},
        "html": ""
    }
    
    try:
        # 根据模式提取内容
        if mode == "html":
            result["html"] = extract_full_html(page, selector=selector)
            result["data"] = {"html_length": len(result["html"])}
        
        elif mode == "links":
            if selector:
                # 如果指定了选择器，只在选择器范围内提取链接
                container = page.locator(selector).first
                links = container.locator("a[href]")
                count = links.count()
                if limit:
                    count = min(count, limit)
                
                links_data = []
                for idx in range(count):
                    try:
                        link = links.nth(idx)
                        title = (link.inner_text() or "").strip()
                        href = link.get_attribute("href") or ""
                        if href:
                            normalized_url = urljoin(current_url, href.strip())
                            if normalized_url.startswith(("http://", "https://")):
                                links_data.append({
                                    "title": title or normalized_url,
                                    "url": normalized_url
                                })
                    except Exception:
                        continue
                result["data"] = {"links": links_data}
            else:
                result["data"] = {"links": extract_all_links(page, current_url, limit=limit)}
        
        elif mode == "all":
            result["data"] = extract_all_elements(
                page,
                limit_per_type=limit,
                include_text=True,
                include_links=True
            )
        
        elif mode == "full":
            result["data"] = extract_all_elements(
                page,
                limit_per_type=limit,
                include_text=True,
                include_links=True
            )
            if include_html or True:  # 默认包含 HTML
                result["html"] = extract_full_html(page, selector=selector)
        
        elif mode == "blog_content":
            # 提取博客正文内容
            blog_data = extract_blog_content(page, selector=selector)
            result["data"] = blog_data
        
        else:
            result["data"] = {"error": f"Unknown mode: {mode}"}
        
        return result
    
    except Exception as e:
        print(f"[page_content_extractor] Error in extract_page_content: {e}")
        return {
            "url": current_url,
            "mode": mode,
            "data": {"error": str(e)},
            "html": ""
        }

