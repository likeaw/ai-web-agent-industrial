# 文件: backend/src/agent/DecisionMaker.py

import json
import os
import sys
import tempfile
import time
import uuid
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Rich 进度条和输出
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn

# --- 核心模块引入 ---
from backend.src.agent.Planner import DynamicExecutionGraph
from backend.src.services.LLMAdapter import LLMAdapter
from backend.src.visualization.VisualizationAdapter import VisualizationAdapter

# 工具层（本地工具）
from backend.src.tools.local_tools import launch_notepad
# 系统操作工具
from backend.src.tools.system import (
    create_directory,
    delete_file_or_directory,
    list_directory,
    read_file_content,
    write_file_content,
    is_dangerous_operation,
    create_word_document,
    create_excel_document,
    create_powerpoint_document,
    create_office_document,
    resolve_user_path,
)
# 路径与临时文件管理
from backend.src.utils.path_utils import build_temp_file_path
# 引入真实浏览器服务
from backend.src.services.BrowserService import BrowserService

# --- 数据模型 ---
from backend.src.data_models.decision_engine.decision_models import (
    TaskGoal, WebObservation, ExecutionNode, ExecutionNodeStatus, DecisionAction, ActionFeedback
)

# 加载环境变量 (确保在任何逻辑执行前加载)
load_dotenv()

# Rich Console 实例
console = Console()

class DecisionMaker:
    """
    决策执行者 (DecisionMaker) - 工业级实现
    
    职责：
    1. 生命周期管理：负责 BrowserService 的初始化与安全销毁。
    2. 执行流编排：驱动 Planner 进行节点流转。
    3. 异常熔断：在关键路径失败时执行剪枝或终止策略。
    4. 可视化审计：在每一步操作后生成状态快照。
    """

    def __init__(self, task_goal: TaskGoal, headless: bool = True, confirm_callback=None):
        """
        初始化决策引擎。
        
        :param task_goal: 任务目标对象。
        :param headless: 浏览器运行模式。生产环境通常为 True，调试环境可配置为 False。
        :param confirm_callback: 危险操作确认回调函数，签名为 (tool_name: str, reason: str) -> bool。
        """
        self.task_goal = task_goal
        self.headless = headless
        self.confirm_callback = confirm_callback
        
        # 初始化组件
        self.planner = DynamicExecutionGraph()
        self.browser_service: Optional[BrowserService] = None
        
        # 运行时状态
        self.is_running = False
        self.current_node: Optional[ExecutionNode] = None
        self.execution_counter = 0
        
        # 失败节点历史记录，用于避免重复生成相同错误的节点
        self.failed_node_history: List[Dict[str, Any]] = [] 
        self.shared_context: Dict[str, Any] = {}

    def _init_browser(self):
        """延迟初始化浏览器资源，仅在 run 开始时调用。"""
        if not self.browser_service:
            try:
                console.print(f"[dim]Initializing BrowserService (Headless: {self.headless})...[/dim]")
                self.browser_service = BrowserService(headless=self.headless)
            except Exception as e:
                console.print(f"[red][CRITICAL] Failed to initialize BrowserService: {e}[/red]")
                raise RuntimeError("Browser initialization failed.") from e

    def close(self):
        """资源清理钩子，确保浏览器进程不残留。"""
        if self.browser_service:
            console.print("[dim]Closing BrowserService...[/dim]")
            try:
                self.browser_service.close()
            except Exception as e:
                console.print(f"[yellow][WARN] Error during browser closure: {e}[/yellow]")
            finally:
                self.browser_service = None

    def _build_local_observation(
        self,
        domain: str,
        feedback: ActionFeedback,
        memory_context: str,
        status_code: int = 400,
    ) -> WebObservation:
        """构造本地操作的观测对象。"""
        return WebObservation(
            observation_timestamp_utc=time.strftime("%Y-%m-%dT%H:%M:%S"),
            current_url=domain,
            http_status_code=status_code,
            page_load_time_ms=0,
            is_authenticated=False,
            key_elements=[],
            screenshot_available=False,
            last_action_feedback=feedback,
            memory_context=memory_context,
        )

    def _update_last_extracted_items(self, feedback: Optional[ActionFeedback]) -> None:
        """
        将 extract_data 的结果缓存下来，后续 create_excel_document 可直接复用。
        """
        if not feedback or feedback.status != "SUCCESS" or not feedback.message:
            self.shared_context.pop("last_extracted_items", None)
            return

        try:
            payload = json.loads(feedback.message)
        except (json.JSONDecodeError, TypeError):
            return

        if not isinstance(payload, dict):
            return

        if payload.get("result_type") != "link_list":
            return

        items = payload.get("items")
        if not isinstance(items, list):
            return

        cleaned: List[Dict[str, str]] = []
        for entry in items:
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("title", "")).strip()
            url = str(entry.get("url", "")).strip()
            if not title and not url:
                continue
            cleaned.append({"title": title, "url": url})

        if cleaned:
            self.shared_context["last_extracted_items"] = cleaned
        else:
            self.shared_context.pop("last_extracted_items", None)

    def _build_fallback_excel_rows(self) -> Optional[List[List[str]]]:
        """
        根据最近一次 extract_data 的缓存构造 Excel 行数据。
        """
        items = self.shared_context.get("last_extracted_items")
        if not isinstance(items, list):
            return None

        rows: List[List[str]] = []
        for entry in items:
            if not isinstance(entry, dict):
                continue
            title = entry.get("title", "")
            url = entry.get("url", "")
            if not title and not url:
                continue
            rows.append([title, url])

        return rows or None

    def _confirm_storage_operation(
        self,
        tool_name: str,
        raw_path: str,
        domain: str,
        context: str,
    ) -> Optional[WebObservation]:
        """
        存储/写入操作前的路径确认逻辑。

        如果 CLI 提供 confirm 回调，则展示实际写入路径并要求确认。
        """
        if not raw_path:
            fb = ActionFeedback(
                status="FAILED",
                error_code="PATH_REQUIRED",
                message="Storage operation requires a non-empty 'path' parameter.",
            )
            return self._build_local_observation(domain, fb, context)

        if not self.confirm_callback:
            # 无需确认（例如前端或 API 模式）
            return None

        try:
            resolved_path = resolve_user_path(raw_path)
        except ValueError as exc:
            fb = ActionFeedback(
                status="FAILED",
                error_code="INVALID_PATH",
                message=f"Invalid path: {exc}",
            )
            return self._build_local_observation(domain, fb, context)

        confirm_message = (
            "[STORAGE]\n"
            f"操作: {tool_name}\n"
            f"目标路径: {resolved_path}\n"
            "说明: 此操作会在本地创建/写入上述路径。"
        )
        confirmed = self.confirm_callback(tool_name, confirm_message)
        if not confirmed:
            fb = ActionFeedback(
                status="FAILED",
                error_code="USER_CANCELLED",
                message=f"User cancelled storage operation: {resolved_path}",
            )
            return self._build_local_observation(domain, fb, context, status_code=403)

        return None

    def _execute_action(self, action: DecisionAction) -> WebObservation:
        """
        执行原子操作。
        """
        self.execution_counter += 1
        try:
            # 1. 纯本地工具：不需要浏览器（如 open_notepad）
            # 1.1 系统操作工具（文件/文件夹操作）
            if action.tool_name in [
                "create_directory",
                "delete_file_or_directory",
                "list_directory",
                "read_file_content",
                "write_file_content",
            ]:
                # 检查是否为危险操作
                is_dangerous, danger_reason = is_dangerous_operation(action.tool_name, action.tool_args)
                
                if is_dangerous:
                    # 需要用户确认
                    if self.confirm_callback:
                        confirmed = self.confirm_callback(action.tool_name, danger_reason or "Unknown risk")
                        if not confirmed:
                            fb = ActionFeedback(
                                status="FAILED",
                                error_code="USER_CANCELLED",
                                message=f"User cancelled dangerous operation: {danger_reason}",
                            )
                            observation = WebObservation(
                                observation_timestamp_utc=time.strftime("%Y-%m-%dT%H:%M:%S"),
                                current_url="local://system",
                                http_status_code=403,
                                page_load_time_ms=0,
                                is_authenticated=False,
                                key_elements=[],
                                screenshot_available=False,
                                last_action_feedback=fb,
                                memory_context="System operation cancelled by user.",
                            )
                            return observation
                    else:
                        # 没有确认回调，直接拒绝危险操作
                        fb = ActionFeedback(
                            status="FAILED",
                            error_code="NO_CONFIRM_CALLBACK",
                            message=f"Dangerous operation requires confirmation, but no callback provided: {danger_reason}",
                        )
                        observation = WebObservation(
                            observation_timestamp_utc=time.strftime("%Y-%m-%dT%H:%M:%S"),
                            current_url="local://system",
                            http_status_code=403,
                            page_load_time_ms=0,
                            is_authenticated=False,
                            key_elements=[],
                            screenshot_available=False,
                            last_action_feedback=fb,
                            memory_context="System operation rejected (no confirmation).",
                        )
                        return observation

                storage_ops = {"create_directory", "write_file_content"}
                if action.tool_name in storage_ops and not is_dangerous:
                    confirmation_obs = self._confirm_storage_operation(
                        action.tool_name,
                        action.tool_args.get("path", ""),
                        "local://system",
                        f"System storage operation: {action.tool_name}",
                    )
                    if confirmation_obs:
                        return confirmation_obs

                # 执行系统操作
                if action.tool_name == "create_directory":
                    path = action.tool_args.get("path", "")
                    ok, msg = create_directory(path)
                    fb = ActionFeedback(
                        status="SUCCESS" if ok else "FAILED",
                        error_code="0" if ok else "CREATE_DIR_ERROR",
                        message=msg,
                    )
                elif action.tool_name == "delete_file_or_directory":
                    path = action.tool_args.get("path", "")
                    recursive = action.tool_args.get("recursive", False)
                    ok, msg = delete_file_or_directory(path, recursive=recursive)
                    fb = ActionFeedback(
                        status="SUCCESS" if ok else "FAILED",
                        error_code="0" if ok else "DELETE_ERROR",
                        message=msg,
                    )
                elif action.tool_name == "list_directory":
                    path = action.tool_args.get("path", ".")
                    show_hidden = action.tool_args.get("show_hidden", False)
                    ok, msg, items = list_directory(path, show_hidden=show_hidden)
                    if ok and items:
                        result_msg = f"{msg}\n\n" + "\n".join(items)
                    else:
                        result_msg = msg
                    fb = ActionFeedback(
                        status="SUCCESS" if ok else "FAILED",
                        error_code="0" if ok else "LIST_DIR_ERROR",
                        message=result_msg,
                    )
                elif action.tool_name == "read_file_content":
                    path = action.tool_args.get("path", "")
                    max_size = action.tool_args.get("max_size", 1024 * 1024)
                    ok, msg, content = read_file_content(path, max_size=max_size)
                    if ok and content:
                        result_msg = f"{msg}\n\nContent:\n{content}"
                    else:
                        result_msg = msg
                    fb = ActionFeedback(
                        status="SUCCESS" if ok else "FAILED",
                        error_code="0" if ok else "READ_FILE_ERROR",
                        message=result_msg,
                    )
                elif action.tool_name == "write_file_content":
                    path = action.tool_args.get("path", "")
                    content = action.tool_args.get("content", "")
                    append = action.tool_args.get("append", False)
                    ok, msg = write_file_content(path, content, append=append)
                    fb = ActionFeedback(
                        status="SUCCESS" if ok else "FAILED",
                        error_code="0" if ok else "WRITE_FILE_ERROR",
                        message=msg,
                    )
                else:
                    fb = ActionFeedback(
                        status="FAILED",
                        error_code="UNKNOWN_SYSTEM_TOOL",
                        message=f"Unknown system tool: {action.tool_name}",
                    )

                observation = WebObservation(
                    observation_timestamp_utc=time.strftime("%Y-%m-%dT%H:%M:%S"),
                    current_url="local://system",
                    http_status_code=200 if fb.status == "SUCCESS" else 500,
                    page_load_time_ms=0,
                    is_authenticated=False,
                    key_elements=[],
                    screenshot_available=False,
                    last_action_feedback=fb,
                    memory_context=f"System operation: {action.tool_name}",
                )

            elif action.tool_name == "open_notepad":
                file_path = action.tool_args.get("file_path")
                initial_content = action.tool_args.get("initial_content", "")

                # 统一获取“最近一次提取结果”的文本形式（每行一个标题）
                titles_text: Optional[str] = None
                if hasattr(self.planner, "nodes_execution_order"):
                    from ast import literal_eval

                    for nid in reversed(self.planner.nodes_execution_order):
                        node = self.planner.nodes.get(nid)
                        if not node:
                            continue
                        if getattr(node, "resolved_output", None):
                            raw_output = str(node.resolved_output)
                            if raw_output.startswith("Extracted") and ":" in raw_output:
                                try:
                                    list_part = raw_output.split(":", 1)[1].strip()
                                    titles = literal_eval(list_part)
                                    if isinstance(titles, list) and titles:
                                        titles_text = "\n".join(str(t) for t in titles)
                                    else:
                                        titles_text = raw_output
                                except Exception:
                                    titles_text = raw_output
                            else:
                                titles_text = raw_output
                            break

                # 逻辑简化：一旦有提取结果，就完全覆盖 initial_content，避免占位符残留
                if titles_text:
                    initial_content = titles_text

                # 统一：所有记事本类临时文件写入到项目根目录 temp/notes 下，按任务主题+时间命名
                if not file_path:
                    file_path = build_temp_file_path(
                        file_type="notes",
                        task_topic=self.task_goal.target_description,
                        extension=".txt",
                    )

                target_path, ok, msg = launch_notepad(file_path, initial_content)

                fb = ActionFeedback(
                    status="SUCCESS" if ok else "FAILED",
                    error_code="0" if ok else "NOTEPAD_LAUNCH_ERROR",
                    message=msg,
                )

                observation = WebObservation(
                    observation_timestamp_utc=time.strftime("%Y-%m-%dT%H:%M:%S"),
                    current_url="local://notepad",
                    http_status_code=200 if fb.status == "SUCCESS" else 500,
                    page_load_time_ms=0,
                    is_authenticated=False,
                    key_elements=[],
                    screenshot_available=False,
                    last_action_feedback=fb,
                    memory_context="Local tool execution (open_notepad).",
                )

            # 1.3 Office 文档操作工具
            elif action.tool_name in [
                "create_word_document",
                "create_excel_document",
                "create_powerpoint_document",
                "create_office_document",
            ]:
                # 检查是否为危险操作（覆盖已存在文件）
                is_dangerous, danger_reason = is_dangerous_operation(action.tool_name, action.tool_args)
                
                if is_dangerous:
                    if self.confirm_callback:
                        confirmed = self.confirm_callback(action.tool_name, danger_reason or "Unknown risk")
                        if not confirmed:
                            fb = ActionFeedback(
                                status="FAILED",
                                error_code="USER_CANCELLED",
                                message=f"User cancelled dangerous operation: {danger_reason}",
                            )
                            observation = WebObservation(
                                observation_timestamp_utc=time.strftime("%Y-%m-%dT%H:%M:%S"),
                                current_url="local://office",
                                http_status_code=403,
                                page_load_time_ms=0,
                                is_authenticated=False,
                                key_elements=[],
                                screenshot_available=False,
                                last_action_feedback=fb,
                                memory_context="Office document operation cancelled by user.",
                            )
                            return observation

                if not is_dangerous:
                    confirmation_obs = self._confirm_storage_operation(
                        action.tool_name,
                        action.tool_args.get("path", ""),
                        "local://office",
                        f"Office document operation: {action.tool_name}",
                    )
                    if confirmation_obs:
                        return confirmation_obs

                # 执行 Office 文档操作
                if action.tool_name == "create_word_document":
                    path = action.tool_args.get("path", "")
                    content = action.tool_args.get("content")
                    title = action.tool_args.get("title")
                    ok, msg = create_word_document(path, content=content, title=title)
                    fb = ActionFeedback(
                        status="SUCCESS" if ok else "FAILED",
                        error_code="0" if ok else "CREATE_WORD_ERROR",
                        message=msg,
                    )
                elif action.tool_name == "create_excel_document":
                    path = action.tool_args.get("path", "")
                    data = action.tool_args.get("data")  # List[List[Any]]
                    sheet_name = action.tool_args.get("sheet_name", "Sheet1")
                    headers = action.tool_args.get("headers")  # List[str]

                    if not data:
                        fallback_rows = self._build_fallback_excel_rows()
                        if fallback_rows:
                            data = fallback_rows
                            if not headers:
                                headers = ["标题", "URL"]

                    ok, msg = create_excel_document(path, data=data, sheet_name=sheet_name, headers=headers)
                    fb = ActionFeedback(
                        status="SUCCESS" if ok else "FAILED",
                        error_code="0" if ok else "CREATE_EXCEL_ERROR",
                        message=msg,
                    )
                elif action.tool_name == "create_powerpoint_document":
                    path = action.tool_args.get("path", "")
                    slides = action.tool_args.get("slides")  # List[Dict]
                    title = action.tool_args.get("title")
                    ok, msg = create_powerpoint_document(path, slides=slides, title=title)
                    fb = ActionFeedback(
                        status="SUCCESS" if ok else "FAILED",
                        error_code="0" if ok else "CREATE_PPT_ERROR",
                        message=msg,
                    )
                elif action.tool_name == "create_office_document":
                    file_type = action.tool_args.get("file_type", "")
                    path = action.tool_args.get("path", "")
                    # 传递其他参数
                    kwargs = {k: v for k, v in action.tool_args.items() if k not in ["file_type", "path"]}
                    ok, msg = create_office_document(file_type, path, **kwargs)
                    fb = ActionFeedback(
                        status="SUCCESS" if ok else "FAILED",
                        error_code="0" if ok else "CREATE_OFFICE_ERROR",
                        message=msg,
                    )
                else:
                    fb = ActionFeedback(
                        status="FAILED",
                        error_code="UNKNOWN_OFFICE_TOOL",
                        message=f"Unknown Office tool: {action.tool_name}",
                    )

                observation = WebObservation(
                    observation_timestamp_utc=time.strftime("%Y-%m-%dT%H:%M:%S"),
                    current_url="local://office",
                    http_status_code=200 if fb.status == "SUCCESS" else 500,
                    page_load_time_ms=0,
                    is_authenticated=False,
                    key_elements=[],
                    screenshot_available=False,
                    last_action_feedback=fb,
                    memory_context=f"Office document operation: {action.tool_name}",
                )

            else:
                # 2. 需要浏览器的工具：按需延迟初始化 BrowserService
                if not self.browser_service:
                    self._init_browser()

                observation = self.browser_service.execute_action(action)
                if action.tool_name == "extract_data":
                    self._update_last_extracted_items(observation.last_action_feedback)

            # 结果摘要（仅在失败时输出详细信息）
            fb = observation.last_action_feedback
            if fb and fb.status == "FAILED":
                console.print(f"[red]    ✗ {action.tool_name} failed: {fb.message}[/red]")

            return observation

        except Exception as e:
            console.print(f"[red][CRITICAL] Unhandled Exception in Action Execution: {e}[/red]")
            # 返回兜底的失败观测，防止程序崩溃，允许 Planner 尝试恢复
            return WebObservation(
                observation_timestamp_utc=time.strftime("%Y-%m-%dT%H:%M:%S"),
                current_url="unknown",
                http_status_code=500,
                page_load_time_ms=0,
                is_authenticated=False,
                key_elements=[],
                screenshot_available=False,
                memory_context="System Critical Failure",
                last_action_feedback=ActionFeedback(
                    status="FAILED", error_code="SYSTEM_EXCEPTION", message=str(e)
                ),
            )

    def _handle_execution_result(self, node: ExecutionNode, observation: WebObservation) -> bool:
        """
        处理执行结果：成功则继续，失败则触发 LLM 动态重规划 (Self-Correction)。
        """
        # [修改点 1] 直接赋值，现在 ExecutionNode 中已包含 last_observation 字段
        node.last_observation = observation # 存储最新的观测，用于可视化和重规划

        feedback = observation.last_action_feedback
        if not feedback:
            # 如果没有反馈，视为失败，防止空指针异常
            feedback = ActionFeedback(status="FAILED", error_code="NO_FEEDBACK", message="Action execution returned no feedback.")

        # 1. 成功情况
        if feedback.status == 'SUCCESS':
            node.current_status = ExecutionNodeStatus.SUCCESS
            return True
        
        # 2. 失败情况处理
        console.print(f"[yellow]Node {node.node_id} failed: {feedback.message}[/yellow]")
        self.planner.prune_on_failure(node.node_id, feedback.message)
        
        # 记录失败的节点到历史中
        failed_node_record = {
            "node_id": node.node_id,
            "tool_name": node.action.tool_name,
            "tool_args": node.action.tool_args.copy(),
            "error_message": feedback.message,
            "reasoning": node.action.reasoning,
        }
        self.failed_node_history.append(failed_node_record)
        console.print(f"[dim]Added node to failure history. Total failed nodes: {len(self.failed_node_history)}[/dim]")
        
        # 检查节点的失败策略
        if node.action.on_failure_action == "STOP_TASK":
            console.print("[red]Strategy is STOP_TASK. Halting execution.[/red]")
            node.current_status = ExecutionNodeStatus.FAILED
            return False
            
        elif node.action.on_failure_action == "RE_EVALUATE":
            console.print(f"[cyan]Re-planning: Generating correction plan for Node {node.node_id}...[/cyan]")
            
            # A. 构造纠错上下文
            correction_goal = self.task_goal.model_copy()
            correction_goal.target_description = (
                f"ORIGINAL GOAL: {self.task_goal.target_description}\n"
                f"CONTEXT: The step '{node.action.tool_name}' FAILED.\n"
                f"ERROR MESSAGE: {feedback.message}\n"
                f"TASK: Generate a short corrective plan (1-3 steps) to fix this error and achieve the original goal."
            )
            
            # B. 调用 LLM 生成纠错片段，并传递失败节点历史
            try:
                correction_nodes = LLMAdapter.generate_nodes(
                    correction_goal, 
                    observation,
                    failed_node_history=self.failed_node_history  # 传递失败历史
                )
                
                if correction_nodes:
                    self.planner.inject_correction_plan(node.node_id, correction_nodes)
                    console.print(f"[green]Injected {len(correction_nodes)} correction nodes.[/green]")
                    return True
                else:
                    console.print("[red]LLM returned empty correction plan. Cannot recover.[/red]")
                    return False
                    
            except Exception as e:
                console.print(f"[red]Re-planning failed: {e}[/red]")
                return False
                
        # 默认处理
        node.current_status = ExecutionNodeStatus.FAILED
        return True

    def _save_visualization(self, suffix: str):
        """生成可视化快照"""
        filename = f"plan_{self.task_goal.task_uuid}_{suffix}"
        try:
            # 渲染图
            output_dir = 'logs/graphs'
            os.makedirs(output_dir, exist_ok=True)
            content = VisualizationAdapter.render_graph_to_html_string(self.planner, filename)
            
            # 写入文件
            with open(os.path.join(output_dir, f"{filename}.html"), 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            console.print(f"[yellow][WARN] Visualization failed: {e}[/yellow]")

    def _resolve_dynamic_args(self, node: ExecutionNode) -> DecisionAction:
        """
        动态参数替换方法：将 {result_of:NODE_ID} 模式替换为实际的执行结果。
        此方法在执行前调用，处理动态依赖。
        """
        resolved_args = node.action.tool_args.copy()
        
        # 遍历所有参数，检查是否包含动态引用
        for key, value in node.action.tool_args.items():
            if isinstance(value, str) and value.startswith("{result_of:") and value.endswith("}"):
                source_node_id = value[len("{result_of:"):-1]
                
                # 检查源节点是否存在且已执行成功
                source_node = self.planner.nodes.get(source_node_id)
                if not source_node or source_node.current_status != ExecutionNodeStatus.SUCCESS:
                    raise ValueError(f"Dynamic argument source node '{source_node_id}' not found or not successful (Status: {source_node.current_status.name if source_node else 'Not Found'}).")
                
                # 从源节点中获取捕获的结果 (使用 resolved_output 属性)
                resolved_value = source_node.resolved_output
                if resolved_value is None:
                    raise ValueError(f"Dynamic argument source node '{source_node_id}' succeeded but has no captured output ('resolved_output').")

                resolved_args[key] = resolved_value
        
        # 返回一个新的 DecisionAction 实例
        return DecisionAction(
            tool_name=node.action.tool_name,
            tool_args=resolved_args,
            reasoning=node.action.reasoning,
            confidence_score=node.action.confidence_score,
            expected_outcome=node.action.expected_outcome,
            max_attempts=node.action.max_attempts,
            execution_timeout_seconds=node.action.execution_timeout_seconds,
            on_failure_action=node.action.on_failure_action,
            wait_for_condition_after=node.action.wait_for_condition_after
        )

    def _generate_execution_summary(self):
        """生成详细的执行报告，包括节点的最终状态和提取的结果。"""
        print("\n==================================================")
        print("          ✨ 任务执行总结报告 ✨")
        print("==================================================")
        
        # 统计结果
        total_nodes = len(self.planner.nodes)
        successful_nodes = 0
        
        # 遍历所有节点并打印信息
        for node_id in self.planner.nodes_execution_order:
            node = self.planner.nodes[node_id]
            
            # 颜色化状态
            status_map = {
                ExecutionNodeStatus.SUCCESS: "\033[92mSUCCESS\033[0m", # 绿色
                ExecutionNodeStatus.FAILED: "\033[91mFAILED\033[0m",   # 红色
                ExecutionNodeStatus.PENDING: "\033[93mPENDING\033[0m", # 黄色
                ExecutionNodeStatus.RUNNING: "\033[94mRUNNING\033[0m", # 蓝色
                ExecutionNodeStatus.SKIPPED: "\033[90mSKIPPED\033[0m", # 灰色
            }
            status_colored = status_map.get(node.current_status, node.current_status.name)
            
            summary_parts = [
                f"[{status_colored}] {node.node_id}",
                f"Tool: {node.action.tool_name}",
            ]
            
            # [修改点 2] 直接访问 resolved_output 属性
            resolved_output = node.resolved_output
            if resolved_output is not None:
                # 打印前80字符，并使用青色突出显示结果
                summary_parts.append(f"Output: \033[96m{resolved_output[:80]}{'...' if len(resolved_output) > 80 else ''}\033[0m") 
            
            # 检查是否有失败信息
            if node.current_status == ExecutionNodeStatus.FAILED and node.last_observation and node.last_observation.last_action_feedback:
                feedback = node.last_observation.last_action_feedback
                summary_parts.append(f"Error: \033[91m{feedback.error_code} - {feedback.message[:80]}{'...' if len(feedback.message) > 80 else ''}\033[0m")
            
            # 统计成功节点
            if node.current_status == ExecutionNodeStatus.SUCCESS:
                successful_nodes += 1

            print(f"| {' | '.join(summary_parts)}")

        print("==================================================")
        print(f"总节点数: {total_nodes} | 成功节点数: {successful_nodes}")
        print("==================================================")

    def run(self):
        """主执行循环（带 Rich 进度条）"""
        self.is_running = True
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            try:
                # 1. 规划阶段 (Planning Phase)
                planning_task = progress.add_task("[cyan]Phase 1: Planning...", total=None)
                
                if not self.planner.nodes:
                    progress.update(planning_task, description="[cyan]Phase 1: Generating plan with LLM...")
                    self.planner.generate_initial_plan_with_llm(self.task_goal, failed_node_history=self.failed_node_history)
                else:
                    progress.update(planning_task, description="[cyan]Phase 1: Using pre-loaded plan...")
                
                # 保存初始计划快照
                self._save_visualization("00_initial_plan")
                progress.update(planning_task, completed=True)
                
                if not self.planner.nodes:
                    console.print("[red][ERROR] Execution halted: Plan is empty after initialization.[/red]")
                    return

                # 统计总节点数（用于进度条）
                total_pending = sum(1 for n in self.planner.nodes.values() if n.current_status == ExecutionNodeStatus.PENDING)
                if total_pending == 0:
                    total_pending = len(self.planner.nodes)
                
                # 2. 执行阶段 (Execution Phase)
                execution_task = progress.add_task(
                    "[green]Phase 2: Executing actions...", 
                    total=total_pending
                )
                
                while self.is_running:
                    # 获取下一个可执行节点 (Priority-based DFS)
                    self.current_node = self.planner.get_next_node_to_execute()
                    
                    if self.current_node is None:
                        progress.update(execution_task, completed=total_pending, description="[green]Phase 2: Execution completed")
                        break
                    
                    # 更新进度条描述：显示当前执行的工具
                    progress.update(
                        execution_task, 
                        description=f"[green]Phase 2: Executing [{self.current_node.action.tool_name}] ({self.current_node.node_id})..."
                    )
                    
                    # 状态流转: PENDING -> RUNNING
                    self.current_node.current_status = ExecutionNodeStatus.RUNNING

                    # 动态参数替换 (Dynamic Argument Resolution)
                    try:
                        resolved_action = self._resolve_dynamic_args(self.current_node)
                        self.current_node.action = resolved_action 
                    except ValueError as e:
                        console.print(f"[red][ERROR] Dynamic Argument Resolution FAILED ({self.current_node.node_id}): {e}[/red]")
                        self.current_node.current_status = ExecutionNodeStatus.FAILED
                        observation = WebObservation(
                            current_url=self.browser_service.page.url if self.browser_service and self.browser_service.page else "unknown",
                            http_status_code=500,
                            page_load_time_ms=0,
                            key_elements=[],
                            memory_context="Dynamic Argument Resolution Failed",
                            last_action_feedback=ActionFeedback(
                                status="FAILED", error_code="ARG_RESOLVE_ERROR", message=str(e)
                            )
                        )
                        self.current_node.last_observation = observation
                        should_continue = self._handle_execution_result(self.current_node, observation)
                        self._save_visualization(f"step_{self.execution_counter:02d}_{self.current_node.node_id}_FAIL")
                        progress.advance(execution_task)
                        if not should_continue:
                            self.is_running = False
                            break
                        continue
                    
                    # 执行
                    observation = self._execute_action(self.current_node.action)
                    
                    # 状态流转: RUNNING -> SUCCESS/FAILED & Pruning
                    should_continue = self._handle_execution_result(self.current_node, observation)
                    
                    # 结果捕获逻辑
                    if self.current_node.current_status == ExecutionNodeStatus.SUCCESS and observation.last_action_feedback and observation.last_action_feedback.message:
                        self.current_node.resolved_output = observation.last_action_feedback.message
                    
                    # 快照审计
                    self._save_visualization(f"step_{self.execution_counter:02d}_{self.current_node.node_id}")
                    
                    # 更新进度条
                    progress.advance(execution_task)
                    
                    if not should_continue:
                        self.is_running = False
                        break
                    
                    # 硬性安全熔断 (防止无限循环)
                    if self.execution_counter >= 50:
                        console.print("[yellow][ABORT] Reached max safety iteration limit (50).[/yellow]")
                        break
                        
            except KeyboardInterrupt:
                console.print("\n[yellow][USER ABORT] Execution interrupted by user.[/yellow]")
            except Exception as e:
                console.print(f"\n[red][FATAL ERROR] Unhandled exception in run loop: {e}[/red]")
                import traceback
                traceback.print_exc()
            finally:
                # 任务结束时调用总结报告
                self._generate_execution_summary() 
                
                self.close()
                console.print("[dim]--- DecisionMaker Terminated ---[/dim]")


# ----------------------------------------------------------------------
# 工业级入口点 (Entry Point)
# ----------------------------------------------------------------------
        
if __name__ == '__main__':
    # 1. 环境完整性检查
    llm_key = os.getenv("LLM_API_KEY")
    # 定义一个标准测试计划路径
    default_json_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..', '..', 'data', 'complex_plan.json'
    ))
    
    # 2. 模式判定 (Mode Selection)
    target_json_file = default_json_path if os.path.exists(default_json_path) else None
    
    # 3. 构造任务上下文 (Task Context)
    goal = TaskGoal(
        task_uuid=f"TASK-{str(uuid.uuid4())[:8]}",
        step_id="INIT",
        target_description="Execute industrial automation task.",
        priority_level=1,
        max_execution_time_seconds=120,
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
            "click_nth",
            "find_link_by_text",
            "download_page",
            "download_link",
        ],
    )
    
    # 4. 初始化 DecisionMaker
    is_headless = os.getenv("BROWSER_HEADLESS", "False").lower() == "true"
    maker = DecisionMaker(goal, headless=is_headless)

    print("==================================================")
    print("    AI Web Agent - Industrial Decision Engine")
    print("==================================================")

    # 5. 执行分支 (Strict Branching)
    if target_json_file:
        print(f"[MODE] Replay/Test Mode")
        print(f"[INFO] Loading static plan from: {target_json_file}")
        
        # 假设 DynamicExecutionGraph 有 load_plan_from_json 方法
        try:
            maker.planner.load_plan_from_json(target_json_file)
        except AttributeError:
            print("[FATAL] Planner class is missing 'load_plan_from_json' method. Exiting.")
            sys.exit(1)
        
        if not maker.planner.nodes:
            print("[FATAL] JSON file loaded but contained no valid nodes. Exiting.")
            sys.exit(1)
            
        maker.run()
        
    elif llm_key:
        print(f"[MODE] Dynamic Generative Mode")
        print(f"[INFO] LLM API Key detected. Agent will generate plan dynamically.")
        
        # 在动态模式下，必须有明确的任务描述。
        user_intent = "Go to bing.com and search for 'Industrial AI Agent'"
        print(f"[GOAL] {user_intent}")
        maker.task_goal.target_description = user_intent
        
        maker.run()
        
    else:
        # 既无 JSON 也无 Key -> 无法运行 -> 报错退出
        print("[FATAL ERROR] System Configuration Incomplete.")
        print("Reason: No 'complex_plan.json' found in data/ AND no 'LLM_API_KEY' in environment.")
        print("Action: Please provide a static plan file OR configure your LLM credentials.")
        sys.exit(1)