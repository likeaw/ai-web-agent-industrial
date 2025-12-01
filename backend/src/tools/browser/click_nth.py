"""
点击第 N 个匹配元素的工具。

用于诸如“点击第 1 条搜索结果”这类操作。
"""

from playwright.sync_api import Page, TimeoutError


def click_nth_match(
    page: Page,
    selector: str,
    index: int = 0,
    timeout_ms: int = 10000,
) -> None:
    """
    点击匹配 selector 的第 index 个元素（从 0 开始）。
    """
    if index < 0:
        raise ValueError("index must be non-negative.")

    page.wait_for_selector(selector, state="visible", timeout=timeout_ms)
    elements = page.locator(selector).all()

    if index >= len(elements):
        raise TimeoutError(f"click_nth_match: only {len(elements)} elements matched, index={index}")

    elements[index].click(timeout=timeout_ms)


