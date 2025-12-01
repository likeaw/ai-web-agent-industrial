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
) -> str:
    """
    对当前页面进行截图，并返回截图的完整文件路径。

    - 如果未指定 filename，则根据任务主题和时间生成：temp/screenshots/{topic}_{ts}.png
    """
    if filename:
        # 如果调用方给了明确的文件名，则仍然放在 screenshots 目录下
        base_dir = os.path.dirname(
            build_temp_file_path("screenshots", task_topic=task_topic, extension=".png")
        )
        os.makedirs(base_dir, exist_ok=True)
        path = os.path.join(base_dir, filename)
    else:
        path = build_temp_file_path("screenshots", task_topic=task_topic, extension=".png")

    page.screenshot(path=path, full_page=full_page)
    return os.path.abspath(path)


