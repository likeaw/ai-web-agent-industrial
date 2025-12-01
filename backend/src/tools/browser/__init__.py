"""
browser 工具命名空间。

每个浏览器操作作为一个独立模块，便于工业级项目结构下的维护与拓展。
"""

from .search_results import extract_search_results  # noqa: F401
from .screenshot import take_screenshot  # noqa: F401
from .click_nth import click_nth_match  # noqa: F401
from .find_link_by_text import find_link_by_text  # noqa: F401
from .downloads import save_current_page_html, download_from_link  # noqa: F401


