"""
本地系统工具集合（与浏览器无关的操作）。

当前实现：
    - launch_notepad: 打开 Windows 记事本，并写入初始内容。
"""

import os
import sys
import tempfile
from typing import Optional, Tuple


def launch_notepad(file_path: Optional[str], initial_content: str) -> Tuple[str, bool, str]:
    """
    打开 Windows 记事本，并写入初始内容。

    :param file_path: 目标文件路径；如果为 None，则创建临时文件。
    :param initial_content: 要写入文件的文本内容（可为空字符串）。
    :return: (目标文件路径, 是否成功, 结果消息)
    """
    if file_path:
        target_path = os.path.abspath(file_path)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
    else:
        fd, temp_path = tempfile.mkstemp(prefix="agent_note_", suffix=".txt")
        os.close(fd)
        target_path = temp_path

    # 写入内容（如果有）
    if initial_content:
        # 使用 UTF-8 BOM，保证 Windows 记事本正确识别编码
        with open(target_path, "w", encoding="utf-8-sig") as f:
            f.write(initial_content)

    try:
        if sys.platform.startswith("win"):
            import subprocess

            DETACHED = getattr(os, "DETACHED_PROCESS", 0x00000008)
            subprocess.Popen(
                ["notepad.exe", target_path],
                creationflags=DETACHED,
            )
        else:
            # 非 Windows 环境仅提示路径，不真正打开应用
            print(f"[LOCAL TOOL] Notepad launch is only fully supported on Windows. File: {target_path}")

        return target_path, True, f"Notepad opened for file: {target_path}"
    except Exception as exc:
        return target_path, False, f"Failed to open Notepad: {exc}"


