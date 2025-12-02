"""
文件系统操作工具（安全版本）。

提供安全的文件/文件夹操作，包括：
- 创建目录
- 删除文件/目录（带安全检查）
- 列出目录内容
- 读取文件内容
- 写入文件内容

安全机制：
- 禁止操作系统关键目录（如 C:\Windows、C:\Program Files 等）
- 危险操作（删除、覆盖写入）需要用户确认
- 允许操作系统范围内的其他文件操作（如桌面、用户目录等）
"""

import os
import shutil
import re
from pathlib import Path
from typing import List, Tuple, Optional

try:
    import ctypes
    from ctypes import wintypes
except Exception:  # pragma: no cover - 非 Windows 环境无需 ctypes
    ctypes = None


def _get_system_directories() -> List[str]:
    """
    动态获取系统关键目录路径（使用环境变量和系统 API）。
    
    这样可以适配不同的系统配置（如用户目录不在 C 盘的情况）。
    """
    dangerous_paths = []
    
    # Windows 系统目录（通过环境变量获取）
    windir = os.environ.get("WINDIR", r"C:\Windows")
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    program_data = os.environ.get("ProgramData", r"C:\ProgramData")
    
    dangerous_paths.extend([
        os.path.abspath(windir),
        os.path.abspath(program_files),
        os.path.abspath(program_files_x86),
        os.path.abspath(program_data),
    ])
    
    # 系统卷信息（通常在系统盘根目录）
    system_drive = os.environ.get("SystemDrive", "C:")
    dangerous_paths.extend([
        os.path.join(system_drive, "System Volume Information"),
        os.path.join(system_drive, "$Recycle.Bin"),
    ])
    
    # 用户系统关键目录（通过环境变量获取用户目录）
    userprofile = os.environ.get("USERPROFILE", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    temp_dir = os.environ.get("TEMP", "")
    
    if userprofile:
        # 保护用户系统目录
        windows_local = os.path.join(localappdata, "Microsoft", "Windows") if localappdata else None
        windows_roaming = os.path.join(appdata, "Microsoft", "Windows") if appdata else None
        
        if windows_local and os.path.exists(windows_local):
            dangerous_paths.append(os.path.abspath(windows_local))
        if windows_roaming and os.path.exists(windows_roaming):
            dangerous_paths.append(os.path.abspath(windows_roaming))
    
    # 系统临时目录
    if temp_dir and os.path.exists(temp_dir):
        dangerous_paths.append(os.path.abspath(temp_dir))
    
    return [p.lower() for p in dangerous_paths if p]


# 危险路径模式（动态获取，适配不同系统配置）
def _get_dangerous_patterns() -> List[str]:
    """获取危险路径列表（动态生成，适配系统配置）。"""
    return _get_system_directories()

# 危险操作关键词（用于检测）
DANGEROUS_KEYWORDS = [
    "format",
    "del /f /s /q",
    "rm -rf /",
    "rd /s /q",
    "shutdown",
    "restart",
    "reboot",
    "reg delete",
    "reg add",
]


def get_project_root() -> str:
    """获取项目根目录（用于判断是否为项目内操作）。"""
    # 从当前文件位置向上推断：backend/src/tools/system -> 项目根
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def _get_user_home() -> Path:
    """获取用户主目录（优先 USERPROFILE，其次 Path.home）。"""
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        return Path(userprofile)
    return Path.home()


def _get_desktop_directory() -> Path:
    """获取桌面目录（兼容中文/英文目录名），找不到则返回用户主目录。"""
    # 优先使用 Windows shell32 提供的桌面路径，准确性最高
    if os.name == "nt" and ctypes:
        try:
            CSIDL_DESKTOPDIRECTORY = 0x0010
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            result = ctypes.windll.shell32.SHGetFolderPathW(
                None, CSIDL_DESKTOPDIRECTORY, None, 0, buf
            )
            if result == 0:
                desktop = Path(buf.value)
                if desktop.exists():
                    return desktop
        except Exception:
            pass

    home = _get_user_home()
    candidates = [
        home / "Desktop",
        home / "桌面",
        Path.home() / "Desktop",
        Path.home() / "桌面",
        Path(os.environ.get("PUBLIC", "")) / "Desktop" if os.environ.get("PUBLIC") else None,
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    return home


def _get_default_workspace_base() -> Path:
    """
    获取默认的文件操作基准目录。

    为避免污染项目目录，默认将相对路径映射到用户主目录下的 AIWebAgentOutputs。
    """
    base = _get_user_home() / "AIWebAgentOutputs"
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return base


def resolve_user_path(path: str) -> str:
    """
    将用户提供的路径解析为绝对路径。

    规则：
    - 如果路径为绝对路径，直接返回其绝对化结果。
    - 如果包含“桌面”/“desktop”/"{desktop}"，将其映射到桌面目录。
    - 其他相对路径映射到用户主目录下的 AIWebAgentOutputs。
    """
    if path is None:
        raise ValueError("Path cannot be None.")

    raw = str(path).strip()
    if not raw:
        raise ValueError("Path cannot be empty.")

    expanded = os.path.expandvars(os.path.expanduser(raw))
    normalized = expanded.replace("/", os.sep)

    if os.path.isabs(normalized):
        return os.path.abspath(normalized)

    normalized_lower = normalized.lower()
    desktop_tokens = ["{desktop}", "桌面", "desktop"]
    contains_desktop = any(token in normalized_lower for token in desktop_tokens)

    sanitized = normalized
    if contains_desktop:
        sanitized = re.sub(r"(?i)\{desktop\}|桌面|desktop", "", sanitized)

    sanitized = sanitized.strip().lstrip("\\/").replace("/", os.sep)

    base_dir = _get_desktop_directory() if contains_desktop else _get_default_workspace_base()

    target = os.path.join(base_dir, sanitized) if sanitized else str(base_dir)
    return os.path.abspath(target)


def check_path_safety(path: str, operation: str = "access") -> Tuple[bool, Optional[str]]:
    """
    检查路径是否安全，仅防止操作系统关键目录。

    注意：不再限制项目根目录，允许操作系统范围内的文件操作。
    但会保护系统关键目录（通过环境变量动态获取，适配不同系统配置）。

    :param path: 要检查的路径（绝对路径或相对路径）。
    :param operation: 操作类型（"read", "write", "delete"）。
    :return: (是否安全, 错误消息（如果不安全）)
    """
    try:
        abs_path = os.path.abspath(path)
        path_lower = abs_path.lower()
    except Exception:
        return False, f"Invalid path format: {path}"

    # 获取系统关键目录列表（动态适配）
    dangerous_paths = _get_dangerous_patterns()
    
    # 检查路径是否在系统关键目录内
    for dangerous_path in dangerous_paths:
        # 精确匹配：检查路径是否以系统关键目录开头
        if path_lower.startswith(dangerous_path):
            # 进一步检查：确保是真正的子目录，而不是只是路径前缀相同
            # 例如：C:\Windows 应该匹配 C:\Windows\System32，但不应该匹配 C:\WindowsBackup
            if path_lower == dangerous_path or path_lower.startswith(dangerous_path + os.sep):
                return False, f"Path is within protected system directory: {dangerous_path}"

    return True, None


def is_dangerous_operation(tool_name: str, tool_args: dict) -> Tuple[bool, Optional[str]]:
    """
    检查操作是否危险，需要用户确认。

    危险操作包括：
    - 删除操作（除了项目内的 temp/ 和 logs/ 目录）
    - 覆盖写入已存在的文件
    - 包含危险关键词的操作

    :param tool_name: 工具名称。
    :param tool_args: 工具参数。
    :return: (是否危险, 危险原因描述)
    """
    # 删除操作：除了项目内的 temp/ 和 logs/ 目录，其他都需要确认
    if tool_name == "delete_file_or_directory":
        path = tool_args.get("path", "")
        if path:
            abs_path = os.path.abspath(path)
            project_root = get_project_root()
            # 如果删除的是项目内 temp/ 或 logs/ 目录下的内容，相对安全，不需要确认
            if abs_path.startswith(project_root):
                if "temp" in abs_path or "logs" in abs_path:
                    return False, None
            # 其他删除操作需要确认
            return True, f"Delete operation on: {abs_path}"

    # 写入操作：如果覆盖已存在的文件，需要确认
    if tool_name == "write_file_content":
        path = tool_args.get("path", "")
        if path:
            try:
                abs_path = resolve_user_path(path)
            except ValueError:
                abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                return True, f"Overwrite existing file: {abs_path}"

    # 检查参数中是否包含危险关键词
    args_str = str(tool_args).lower()
    for keyword in DANGEROUS_KEYWORDS:
        if keyword.lower() in args_str:
            return True, f"Operation contains dangerous keyword: {keyword}"

    return False, None


def create_directory(path: str) -> Tuple[bool, str]:
    """
    创建目录（如果不存在）。

    :param path: 目录路径（相对或绝对）。
    :return: (是否成功, 结果消息)
    """
    try:
        abs_path = resolve_user_path(path)
    except ValueError as exc:
        return False, f"Invalid path: {exc}"

    is_safe, error_msg = check_path_safety(abs_path, "write")
    if not is_safe:
        return False, f"Safety check failed: {error_msg}"

    try:
        os.makedirs(abs_path, exist_ok=True)
        return True, f"Directory created (or already exists): {abs_path}"
    except Exception as e:
        return False, f"Failed to create directory: {e}"


def delete_file_or_directory(path: str, recursive: bool = False) -> Tuple[bool, str]:
    """
    删除文件或目录（带安全检查）。

    :param path: 文件/目录路径。
    :param recursive: 是否递归删除目录（仅对目录有效）。
    :return: (是否成功, 结果消息)
    """
    is_safe, error_msg = check_path_safety(path, "delete")
    if not is_safe:
        return False, f"Safety check failed: {error_msg}"

    try:
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return False, f"Path does not exist: {abs_path}"

        if os.path.isdir(abs_path):
            if recursive:
                shutil.rmtree(abs_path)
                return True, f"Directory deleted (recursive): {abs_path}"
            else:
                # 非递归删除：只删除空目录
                os.rmdir(abs_path)
                return True, f"Empty directory deleted: {abs_path}"
        else:
            os.remove(abs_path)
            return True, f"File deleted: {abs_path}"
    except Exception as e:
        return False, f"Failed to delete: {e}"


def list_directory(path: str, show_hidden: bool = False) -> Tuple[bool, str, Optional[List[str]]]:
    """
    列出目录内容。

    :param path: 目录路径。
    :param show_hidden: 是否显示隐藏文件。
    :return: (是否成功, 结果消息, 文件列表（如果成功）)
    """
    is_safe, error_msg = check_path_safety(path, "read")
    if not is_safe:
        return False, f"Safety check failed: {error_msg}", None

    try:
        abs_path = os.path.abspath(path)
        if not os.path.isdir(abs_path):
            return False, f"Path is not a directory: {abs_path}", None

        items = []
        for item in os.listdir(abs_path):
            if not show_hidden and item.startswith("."):
                continue
            item_path = os.path.join(abs_path, item)
            item_type = "DIR" if os.path.isdir(item_path) else "FILE"
            items.append(f"{item_type:4s}  {item}")

        return True, f"Listed {len(items)} items in: {abs_path}", items
    except Exception as e:
        return False, f"Failed to list directory: {e}", None


def read_file_content(path: str, max_size: int = 1024 * 1024) -> Tuple[bool, str, Optional[str]]:
    """
    读取文件内容（限制最大大小，防止读取过大文件）。

    :param path: 文件路径。
    :param max_size: 最大文件大小（字节），默认 1MB。
    :return: (是否成功, 结果消息, 文件内容（如果成功）)
    """
    is_safe, error_msg = check_path_safety(path, "read")
    if not is_safe:
        return False, f"Safety check failed: {error_msg}", None

    try:
        abs_path = os.path.abspath(path)
        if not os.path.isfile(abs_path):
            return False, f"Path is not a file: {abs_path}", None

        file_size = os.path.getsize(abs_path)
        if file_size > max_size:
            return False, f"File too large ({file_size} bytes, max {max_size} bytes)", None

        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        return True, f"Read {len(content)} characters from: {abs_path}", content
    except Exception as e:
        return False, f"Failed to read file: {e}", None


def write_file_content(path: str, content: str, append: bool = False) -> Tuple[bool, str]:
    """
    写入文件内容。

    :param path: 文件路径。
    :param content: 要写入的内容。
    :param append: 是否追加模式（False 为覆盖）。
    :return: (是否成功, 结果消息)
    """
    try:
        abs_path = resolve_user_path(path)
    except ValueError as exc:
        return False, f"Invalid path: {exc}"

    is_safe, error_msg = check_path_safety(abs_path, "write")
    if not is_safe:
        return False, f"Safety check failed: {error_msg}"

    try:
        # 确保父目录存在
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        mode = "a" if append else "w"
        with open(abs_path, mode, encoding="utf-8") as f:
            f.write(content)

        action = "appended to" if append else "written to"
        return True, f"Content {action}: {abs_path}"
    except Exception as e:
        return False, f"Failed to write file: {e}"

