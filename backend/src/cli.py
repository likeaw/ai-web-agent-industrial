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
import uuid
from typing import List

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

from backend.src.data_models.decision_engine.decision_models import TaskGoal
from backend.src.agent.DecisionMaker import DecisionMaker


console = Console()


def _print_banner() -> None:
    """打印启动横幅。"""
    console.print(
        Panel.fit(
            "[bold cyan]AI Web Agent - 工业级网站自动巡查 CLI[/bold cyan]\n"
            "[green]与 AI 对话，下达自动化浏览任务。输入 `exit` / `quit` 退出。[/green]",
            border_style="cyan",
        )
    )


def _print_env_status() -> None:
    """展示与 LLM/浏览器相关的基础配置状态。"""
    llm_key = os.getenv("LLM_API_KEY")
    model_name = os.getenv("LLM_MODEL_NAME", "deepseek-chat")
    api_url = os.getenv("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions")
    headless_env = os.getenv("BROWSER_HEADLESS", "False")

    table = Table(title="运行环境概览", show_lines=True)
    table.add_column("配置项", style="bold")
    table.add_column("值", style="magenta")

    table.add_row("LLM_API_KEY 是否配置", "是" if llm_key else "[red]否[/red]")
    table.add_row("LLM_MODEL_NAME", model_name)
    table.add_row("LLM_API_URL", api_url)
    table.add_row("BROWSER_HEADLESS (env)", headless_env)

    console.print(table)

    if not llm_key:
        console.print(
            Panel(
                "[bold red]警告：未检测到 LLM_API_KEY，动态规划模式将无法工作。[/bold red]\n"
                "你仍然可以在有预置 JSON 计划的情况下回放执行，但无法让 AI 自动规划步骤。",
                border_style="red",
            )
        )


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
        ],
    )


def _run_single_task(description: str, headless: bool) -> None:
    """执行单个用户任务：构造 TaskGoal -> 创建 DecisionMaker -> run。"""
    goal = _create_task_goal(description)

    console.print(
        Panel.fit(
            f"[bold yellow]新任务[/bold yellow]\n"
            f"ID: [cyan]{goal.task_uuid}[/cyan]\n"
            f"描述: [green]{goal.target_description}[/green]",
            border_style="yellow",
        )
    )

    maker = DecisionMaker(goal, headless=headless)
    maker.run()


def main() -> None:
    """Rich 驱动的交互式命令行主函数。"""
    # 1. 加载环境变量
    load_dotenv()

    # 2. 界面与环境展示
    _print_banner()
    _print_env_status()

    # 3. 询问是否使用无头浏览器（默认沿用环境变量设置）
    env_headless = os.getenv("BROWSER_HEADLESS", "False").lower() == "true"
    headless = Confirm.ask(
        "[bold cyan]是否以无头模式运行浏览器?[/bold cyan] "
        f"(当前 env 默认: {'[green]是[/green]' if env_headless else '[yellow]否[/yellow]'} )",
        default=env_headless,
    )

    # 4. 主对话循环
    while True:
        console.print()
        user_input = Prompt.ask(
            "[bold cyan]请输入本轮要交给 AI 的任务描述[/bold cyan]\n"
            "[dim](示例：\"打开 bing.com 搜索 工业 AI Agent 并提取前三条结果标题\")[/dim]\n"
            "[bold]You[/bold]"
        ).strip()

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit", "q"}:
            console.print("[bold green]已退出 CLI，对话结束。[/bold green]")
            break

        # 这里可以在未来扩展为多轮对话，将上文记忆传入 LLMAdapter；
        # 目前先按“单轮任务 -> 执行完整决策循环”的模式实现。
        _run_single_task(user_input, headless=headless)


if __name__ == "__main__":
    main()


