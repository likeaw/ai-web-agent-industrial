"""
通用截图工具。

封装 Page 的截图能力，便于后续在决策图中以工具形式调用。
"""

import os
from typing import Optional

from playwright.sync_api import Page

from backend.src.utils.path_utils import build_temp_file_path


def take_screenshot(
    page: Page,
    task_topic: str,
    filename: Optional[str] = None,
    full_page: bool = True,
    custom_path: Optional[str] = None,
) -> str:
    """
    对当前页面进行截图，并返回截图的完整文件路径。

    - 如果指定 custom_path，则直接使用该路径（调用方需保证路径合法）；
    - 否则若提供 filename，则将其保存在 temp/screenshots 目录下；
    - 如果两者都未提供，则根据任务主题自动生成文件名：temp/screenshots/{topic}_{ts}.png。
    """
    if custom_path:
        path = os.path.abspath(custom_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
    elif filename:
        base_dir = os.path.dirname(
            build_temp_file_path("screenshots", task_topic=task_topic, extension=".png")
        )
        os.makedirs(base_dir, exist_ok=True)
        path = os.path.join(base_dir, filename)
    else:
        path = build_temp_file_path("screenshots", task_topic=task_topic, extension=".png")

    page.screenshot(path=path, full_page=full_page)
    return os.path.abspath(path)


