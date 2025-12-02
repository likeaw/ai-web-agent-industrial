"""
系统操作工具命名空间。

每个系统操作作为一个独立模块，便于工业级项目结构下的维护与拓展。
"""

from .file_operations import (
    create_directory,
    delete_file_or_directory,
    list_directory,
    read_file_content,
    write_file_content,
    check_path_safety,
    is_dangerous_operation,
    resolve_user_path,
)
from .office_documents import (
    create_word_document,
    create_excel_document,
    create_powerpoint_document,
    create_office_document,
)

__all__ = [
    "create_directory",
    "delete_file_or_directory",
    "list_directory",
    "read_file_content",
    "write_file_content",
    "check_path_safety",
    "is_dangerous_operation",
    "resolve_user_path",
    "create_word_document",
    "create_excel_document",
    "create_powerpoint_document",
    "create_office_document",
]

