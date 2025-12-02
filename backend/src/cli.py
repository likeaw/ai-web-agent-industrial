"""
命令行入口：基于 rich 的工业级 Web Agent 互动壳层

功能：
- 在终端里提供一个对话式界面，用户用自然语言下达任务
- 为每个任务构造 TaskGoal，并调用内部的 DecisionMaker 执行
- 通过 BrowserService 等已有组件实现“打开网站、操作页面”等动作

用法（示例）：
    python -m backend.src.cli
"""

import os
import sys
import uuid
from typing import List
from datetime import datetime

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.layout import Layout
from rich.columns import Columns
from rich.text import Text
from rich.align import Align
from rich import box

from backend.src.data_models.decision_engine.decision_models import TaskGoal
from backend.src.agent.DecisionMaker import DecisionMaker


console = Console()


def _print_banner() -> None:
    """打印精美的启动横幅。"""
    banner_text = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     █████╗ ██╗    ██╗    ██╗███████╗██████╗                 ║
║    ██╔══██╗██║    ██║    ██║██╔════╝██╔══██╗                ║
║    ███████║██║ █╗ ██║ █╗ ██║█████╗  ██████╔╝                ║
║    ██╔══██║██║███╗██║███╗██║██╔══╝  ██╔══██╗                ║
║    ██║  ██║╚███╔███╔╝╚███╔╝███████╗██████╔╝                ║
║    ╚═╝  ╚═╝ ╚══╝╚══╝  ╚══╝ ╚══════╝╚═════╝                 ║
║                                                              ║
║          [bold cyan]Industrial Web Agent Platform[/bold cyan]              ║
║         [green]Intelligent Automation & Decision Engine[/green]            ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    
    console.print(banner_text, style="bold cyan")
    
    info_panel = Panel(
        "[bold green]✨ 与 AI 对话，下达自动化浏览任务[/bold green]\n"
        "[dim]支持浏览器操作、文件管理、Office 文档创建等功能[/dim]\n"
        "[yellow]输入 `exit` / `quit` / `q` 退出程序[/yellow]",
        border_style="green",
        box=box.ROUNDED,
        padding=(1, 2),
    )
    console.print(info_panel)
    console.print()


def _print_env_status() -> None:
    """展示精美的环境配置状态面板。"""
    llm_key = os.getenv("LLM_API_KEY")
    model_name = os.getenv("LLM_MODEL_NAME", "deepseek-chat")
    api_url = os.getenv("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions")
    headless_env = os.getenv("BROWSER_HEADLESS", "False")
    
    # Python 版本信息
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    python_path = sys.executable

    # 创建布局
    layout = Layout()
    layout.split_column(
        Layout(name="config", size=10),
        Layout(name="warning", size=4),
    )

    # 配置表格
    config_table = Table(
        title="[bold cyan]⚙️  运行环境配置[/bold cyan]",
        show_header=True,
        header_style="bold magenta",
        box=box.ROUNDED,
        border_style="cyan",
        show_lines=True,
    )
    config_table.add_column("配置项", style="bold white", width=25)
    config_table.add_column("状态/值", style="bright_white", width=50)

    # LLM 配置状态
    llm_status = "[bold green]✓ 已配置[/bold green]" if llm_key else "[bold red]✗ 未配置[/bold red]"
    config_table.add_row("🤖 LLM API Key", llm_status)
    config_table.add_row("📝 LLM Model", f"[cyan]{model_name}[/cyan]")
    config_table.add_row("🌐 API URL", f"[dim]{api_url[:50]}...[/dim]" if len(api_url) > 50 else f"[dim]{api_url}[/dim]")
    config_table.add_row("🌍 Browser Mode", f"[yellow]{'无头模式' if headless_env.lower() == 'true' else '可见模式'}[/yellow]")
    config_table.add_row("🐍 Python Version", f"[green]{python_version}[/green]")
    config_table.add_row("📂 Python Path", f"[dim]{python_path[:45]}...[/dim]" if len(python_path) > 45 else f"[dim]{python_path}[/dim]")

    layout["config"].update(Panel(config_table, border_style="cyan", box=box.ROUNDED))

    # 警告信息
    if not llm_key:
        warning_panel = Panel(
            "[bold red]⚠️  警告[/bold red]\n\n"
            "[yellow]未检测到 LLM_API_KEY，动态规划模式将无法工作。[/yellow]\n"
            "[dim]你仍然可以在有预置 JSON 计划的情况下回放执行，但无法让 AI 自动规划步骤。[/dim]",
            border_style="red",
            box=box.ROUNDED,
        )
        layout["warning"].update(warning_panel)
    else:
        layout["warning"].update("")

    console.print(layout)
    console.print()


def _create_task_goal(description: str) -> TaskGoal:
    """根据用户自然语言描述构造一个 TaskGoal。"""
    task_uuid = f"TASK-{str(uuid.uuid4())[:8]}"
    return TaskGoal(
        task_uuid=task_uuid,
        step_id="INIT",
        target_description=description,
        priority_level=5,
        max_execution_time_seconds=180,
        # 允许使用的工具集合，可根据需要逐步扩展
        allowed_actions=[
            "navigate_to",
            "click_element",
            "type_text",
            "scroll",
            "wait",
            "extract_data",
            "get_element_attribute",
            "open_notepad",
            "take_screenshot",
            "click_nth",
            "find_link_by_text",
            "download_page",
            "download_link",
            # 系统操作工具
            "create_directory",
            "delete_file_or_directory",
            "list_directory",
            "read_file_content",
            "write_file_content",
            # Office 文档工具
            "create_word_document",
            "create_excel_document",
            "create_powerpoint_document",
            "create_office_document",
        ],
    )


def _confirm_dangerous_operation(tool_name: str, reason: str) -> bool:
    """
    用户确认操作的回调函数（兼容危险/存储两种场景），采用 IRM 风格的纯文本交互，
    避免 CMD 控制台出现乱码或无法输入的情况。
    """
    storage_prefix = "[STORAGE]"
    is_storage_operation = reason.startswith(storage_prefix)
    display_reason = reason[len(storage_prefix):].strip() if is_storage_operation else reason

    header = "存储操作确认" if is_storage_operation else "危险操作确认"
    border = "=" * 60
    prompt = "继续执行? (Y/n): " if is_storage_operation else "继续执行? (y/N): "
    default_answer = True if is_storage_operation else False

    print("\n" + border)
    print(header)
    print(border)
    print(f"工具: {tool_name}")
    print(display_reason)
    print(border)

    while True:
        answer = input(prompt).strip().lower()
        if not answer:
            return default_answer
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("请输入 y 或 n 并按回车确认。")


def _run_single_task(description: str, headless: bool) -> None:
    """执行单个用户任务：构造 TaskGoal -> 创建 DecisionMaker -> run。"""
    goal = _create_task_goal(description)

    # 精美的任务信息面板
    task_info = f"""
[bold cyan]📋 任务 ID:[/bold cyan] [yellow]{goal.task_uuid}[/yellow]
[bold cyan]📝 任务描述:[/bold cyan] [green]{goal.target_description}[/green]
[bold cyan]⏱️  创建时间:[/bold cyan] [dim]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]
"""
    
    console.print(
        Panel(
            task_info,
            title="[bold yellow]🚀 新任务启动[/bold yellow]",
            border_style="yellow",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()

    maker = DecisionMaker(goal, headless=headless, confirm_callback=_confirm_dangerous_operation)
    maker.run()
    
    # 任务完成提示
    console.print()
    console.print(
        Panel(
            "[bold green]✓ 任务执行完成[/bold green]",
            border_style="green",
            box=box.ROUNDED,
        )
    )
    console.print()


def main() -> None:
    """Rich 驱动的交互式命令行主函数。"""
    # 1. 加载环境变量
    load_dotenv()

    # 2. 界面与环境展示
    _print_banner()
    _print_env_status()

    # 3. 询问是否使用无头浏览器（默认沿用环境变量设置）
    env_headless = os.getenv("BROWSER_HEADLESS", "False").lower() == "true"
    
    browser_mode_panel = Panel(
        "[bold cyan]🌐 浏览器运行模式配置[/bold cyan]\n\n"
        "[dim]无头模式：浏览器在后台运行，不显示窗口（适合生产环境）[/dim]\n"
        "[dim]可见模式：浏览器窗口可见，便于调试和观察（适合开发环境）[/dim]",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(1, 2),
    )
    console.print(browser_mode_panel)
    
    headless = Confirm.ask(
        f"\n[bold cyan]是否以无头模式运行浏览器?[/bold cyan] "
        f"(当前 env 默认: {'[green]是[/green]' if env_headless else '[yellow]否[/yellow]'} )",
        default=env_headless,
    )
    console.print()

    # 4. 主对话循环
    task_count = 0
    while True:
        console.print()
        
        # 精美的输入提示
        input_panel = Panel(
            "[bold cyan]💬 请输入要交给 AI 的任务描述[/bold cyan]\n\n"
            "[dim]示例任务：[/dim]\n"
            "[dim]  • 打开 bing.com 搜索 工业 AI Agent 并提取前三条结果标题[/dim]\n"
            "[dim]  • 在桌面创建一个名为 test 的文件夹[/dim]\n"
            "[dim]  • 创建一个 Word 文档，标题为'报告'，内容为'测试内容'[/dim]\n"
            "[dim]  • 删除 temp 目录下的所有文件[/dim]\n",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2),
        )
        console.print(input_panel)
        
        user_input = Prompt.ask(
            "\n[bold bright_white]You[/bold bright_white]",
            default="",
        ).strip()

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit", "q"}:
            console.print()
            console.print(
                Panel(
                    f"[bold green]👋 感谢使用 AI Web Agent！[/bold green]\n"
                    f"[dim]本次会话共执行了 {task_count} 个任务[/dim]",
                    border_style="green",
                    box=box.ROUNDED,
                )
            )
            console.print()
            break

        task_count += 1
        # 这里可以在未来扩展为多轮对话，将上文记忆传入 LLMAdapter；
        # 目前先按“单轮任务 -> 执行完整决策循环”的模式实现。
        _run_single_task(user_input, headless=headless)


if __name__ == "__main__":
    main()


