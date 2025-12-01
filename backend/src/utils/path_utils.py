"""
路径与临时文件管理工具。

约定：
- 所有临时文件统一存放在项目根目录下的 `temp/` 目录中；
- 不同类型的临时文件按子目录分类，例如：
    - temp/notes/        记事本/文本类
    - temp/screenshots/  页面截图
    - temp/downloads/    下载文件
- 文件名由任务主题 + 时间戳 + 扩展名组成，便于审计和追踪。
"""

import os
import re
from datetime import datetime
from typing import Literal


TempFileType = Literal["notes", "screenshots", "downloads", "other"]


def get_project_root() -> str:
    """
    推断项目根目录。

    约定：本工具文件位于 backend/src/utils/path_utils.py，
    项目根目录为该文件向上三级目录。
    """
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def slugify(text: str, max_len: int = 40) -> str:
    """
    将任务主题转换为适合作为文件名的一部分：
    - 替换空白为下划线
    - 移除不安全字符（/ \\ : * ? " < > |）
    - 截断到指定长度
    """
    # 先替换空白
    text = re.sub(r"\s+", "_", text.strip())
    # 移除 Windows 不允许的字符
    text = re.sub(r'[\\/:\*\?"<>|]', "", text)
    if not text:
        text = "task"
    if len(text) > max_len:
        text = text[:max_len]
    return text


def get_temp_dir(file_type: TempFileType) -> str:
    """
    获取指定类型的临时文件目录，并确保其存在。
    """
    root = get_project_root()
    temp_root = os.path.join(root, "temp", file_type)
    os.makedirs(temp_root, exist_ok=True)
    return temp_root


def build_temp_file_path(
    file_type: TempFileType,
    task_topic: str,
    extension: str,
) -> str:
    """
    根据文件类型、任务主题和扩展名生成临时文件路径。
    """
    base_dir = get_temp_dir(file_type)
    safe_topic = slugify(task_topic or "task")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not extension.startswith("."):
        extension = "." + extension
    filename = f"{safe_topic}_{ts}{extension}"
    return os.path.join(base_dir, filename)


