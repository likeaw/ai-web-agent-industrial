"""
下载相关浏览器工具。

支持：
- 保存当前页面 HTML 到本地（download_page）
- 通过链接 URL 或页面元素下载资源内容（download_link）
"""

import os
import mimetypes
from typing import Optional

import requests
from playwright.sync_api import Page

from backend.src.utils.path_utils import build_temp_file_path


def save_current_page_html(page: Page, task_topic: str) -> str:
    """
    将当前页面完整 HTML 保存到 temp/downloads/ 目录中，并返回文件路径。
    """
    html = page.content()
    path = build_temp_file_path("downloads", task_topic=task_topic, extension=".html")
    with open(path, "w", encoding="utf-8-sig") as f:
        f.write(html)
    return os.path.abspath(path)


def download_from_link(
    page: Page,
    task_topic: str,
    url: Optional[str] = None,
    selector: Optional[str] = None,
) -> str:
    """
    下载链接内容到 temp/downloads/ 目录：
    - 若传入 url，则直接下载该 URL；
    - 否则使用 selector 在页面上查找元素并读取其 href 属性。

    返回保存文件的绝对路径。
    """
    if not url and not selector:
        raise ValueError("download_link requires either 'url' or 'selector' in tool_args.")

    if not url and selector:
        # 从页面元素中提取 href
        el = page.locator(selector).first
        href = el.get_attribute("href")
        if not href:
            raise ValueError(f"download_link: no href found for selector {selector}")
        url = href

    assert url is not None

    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()

    # 根据 URL 和 Content-Type 推断扩展名
    extension = None
    # 1) 尝试从 URL 推断
    guess_from_url = mimetypes.guess_extension(mimetypes.guess_type(url)[0] or "")
    if guess_from_url:
        extension = guess_from_url
    # 2) 再尝试从响应头猜测
    if not extension:
        ctype = resp.headers.get("Content-Type", "").split(";")[0]
        extension = mimetypes.guess_extension(ctype) or ".bin"

    path = build_temp_file_path("downloads", task_topic=task_topic, extension=extension)
    with open(path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return os.path.abspath(path)


