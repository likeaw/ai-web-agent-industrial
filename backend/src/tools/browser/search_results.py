"""
搜索结果提取相关工具。

当前支持：
- 从指定 selector 提取文本/属性
- 对百度搜索结果页做结构化兜底提取
"""

from typing import List, Optional

from playwright.sync_api import Page, TimeoutError


def extract_search_results(
    page: Page,
    current_url: str,
    selector: Optional[str],
    attribute: str = "text",
    limit: int = 3,
) -> List[str]:
    """
    通用的数据提取工具，当前重点支持搜索结果场景（如百度搜索）。

    返回提取到的字符串列表（已 strip），若无结果则为空列表。
    """
    results: List[str] = []

    # 1. 如果上层已经提供了 selector，则优先使用
    if selector:
        elements = page.locator(selector).all()
        for i, element in enumerate(elements):
            if i >= limit:
                break
            if attribute == "text":
                content = element.inner_text()
            else:
                content = element.get_attribute(attribute)
            if content:
                results.append(content.strip())

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
                # 兼容多种结构：标题一般在 h3 下
                title_elements = container.locator("h3").all()
                for i, element in enumerate(title_elements):
                    if i >= limit:
                        break
                    title = element.inner_text()
                    if title:
                        results.append(title.strip())

        except Exception as e:
            print(f"[browser.search_results] Fallback extract_search_results failed: {e}")

    return results


