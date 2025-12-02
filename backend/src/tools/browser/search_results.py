"""
搜索结果提取相关工具。

当前支持：
- 从指定 selector 提取文本/属性
- 对百度搜索结果页做结构化兜底提取
"""

from typing import List, Optional, Dict
from urllib.parse import urljoin

from playwright.sync_api import Page, TimeoutError


def _normalize_link(current_url: str, href: Optional[str]) -> str:
    if not href:
        return ""
    try:
        return urljoin(current_url, href.strip())
    except Exception:
        return href.strip()


def _append_result(results: List[Dict[str, str]], title: Optional[str], url: Optional[str]) -> None:
    normalized_title = (title or "").strip()
    normalized_url = (url or "").strip()
    if not normalized_title and not normalized_url:
        return
    results.append({"title": normalized_title, "url": normalized_url})


def extract_search_results(
    page: Page,
    current_url: str,
    selector: Optional[str],
    attribute: str = "text",
    limit: int = 3,
) -> List[Dict[str, str]]:
    """
    通用的数据提取工具，当前重点支持搜索结果场景（如百度搜索）。

    返回提取到的「标题 + URL」字典列表，若无结果则为空列表。
    """
    results: List[Dict[str, str]] = []

    def _extract_from_locator(target_selector: str, max_items: int) -> None:
        elements = page.locator(target_selector)
        count = min(elements.count(), max_items)
        for idx in range(count):
            element = elements.nth(idx)
            title_value = ""
            try:
                if attribute == "text":
                    title_value = (element.inner_text() or "").strip()
                else:
                    attr_value = element.get_attribute(attribute)
                    if attr_value:
                        title_value = attr_value.strip()
            except Exception:
                title_value = ""

            href_value = element.get_attribute("href") or element.get_attribute("data-url")

            # 如果自身没有 href，尝试寻找子节点上的链接
            if not href_value:
                try:
                    nested_candidates = element.locator("a[href]")
                    if nested_candidates.count() > 0:
                        nested_link = nested_candidates.first
                        href_candidate = nested_link.get_attribute("href") or nested_link.get_attribute("data-url")
                        if href_candidate:
                            href_value = href_candidate
                        if not title_value:
                            try:
                                title_value = (nested_link.inner_text() or "").strip()
                            except Exception:
                                pass
                except Exception:
                    pass

            normalized_url = _normalize_link(current_url, href_value) if href_value else ""
            _append_result(results, title_value, normalized_url)

    # 1. 如果上层已经提供了 selector，则优先使用
    if selector:
        _extract_from_locator(selector, limit)

    # 2. 如果没有结果，再根据 URL 做搜索引擎页面的专用兜底
    if not results:
        try:
            # 百度搜索结果页
            if "www.baidu.com/s" in current_url:
                try:
                    page.wait_for_selector("#content_left", state="visible", timeout=5000)
                except TimeoutError:
                    # 容器未在超时时间内出现，直接返回空结果
                    return results

                container = page.locator("#content_left")
                link_selector = "h3 a[href], h3 > a[href]"
                link_elements = container.locator(link_selector)
                count = min(link_elements.count(), limit)
                for idx in range(count):
                    element = link_elements.nth(idx)
                    title = ""
                    href = ""
                    try:
                        title = (element.inner_text() or "").strip()
                    except Exception:
                        title = ""
                    try:
                        href = element.get_attribute("href") or element.get_attribute("data-url") or ""
                    except Exception:
                        href = ""

                    normalized_url = _normalize_link(current_url, href) if href else ""
                    _append_result(results, title, normalized_url)

            # 通用兜底：提取页面上其它可点击链接
            if not results:
                generic_links = page.locator("a[href]")
                count = min(generic_links.count(), limit)
                for idx in range(count):
                    element = generic_links.nth(idx)
                    title = ""
                    href = ""
                    try:
                        title = (element.inner_text() or "").strip()
                    except Exception:
                        title = ""
                    try:
                        href = element.get_attribute("href") or ""
                    except Exception:
                        href = ""
                    normalized_url = _normalize_link(current_url, href) if href else ""
                    _append_result(results, title, normalized_url)

        except Exception as e:
            print(f"[browser.search_results] Fallback extract_search_results failed: {e}")

    return results


