"""
根据文本模糊匹配链接的工具。

用于在页面上找到包含指定文本的 <a> 链接，并返回它们的 href 和可见文本。
"""

from typing import List, Dict

from playwright.sync_api import Page


def find_link_by_text(
    page: Page,
    keyword: str,
    limit: int = 5,
) -> List[Dict[str, str]]:
    """
    在页面上查找包含关键字的 <a> 标签。

    :return: 形如 [{'text': '链接文本', 'href': 'https://...'}, ...] 的列表。
    """
    results: List[Dict[str, str]] = []

    # 使用 contains(text) 的 XPath 做一个粗略匹配
    xpath = f"//a[contains(normalize-space(string(.)), '{keyword}')]"
    elements = page.locator(f"xpath={xpath}").all()

    for i, el in enumerate(elements):
        if i >= limit:
            break
        text = el.inner_text().strip()
        href = el.get_attribute("href") or ""
        if text or href:
            results.append({"text": text, "href": href})

    return results


