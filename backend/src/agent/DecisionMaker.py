# 文件: backend/src/agent/DecisionMaker.py

import os
import sys
import tempfile
import time
import uuid
from typing import Optional
from dotenv import load_dotenv

# --- 核心模块引入 ---
from backend.src.agent.Planner import DynamicExecutionGraph
from backend.src.services.LLMAdapter import LLMAdapter
from backend.src.visualization.VisualizationAdapter import VisualizationAdapter

# 工具层（本地工具）
from backend.src.tools.local_tools import launch_notepad
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

class DecisionMaker:
    """
    决策执行者 (DecisionMaker) - 工业级实现
    
    职责：
    1. 生命周期管理：负责 BrowserService 的初始化与安全销毁。
    2. 执行流编排：驱动 Planner 进行节点流转。
    3. 异常熔断：在关键路径失败时执行剪枝或终止策略。
    4. 可视化审计：在每一步操作后生成状态快照。
    """

    def __init__(self, task_goal: TaskGoal, headless: bool = True):
        """
        初始化决策引擎。
        
        :param task_goal: 任务目标对象。
        :param headless: 浏览器运行模式。生产环境通常为 True，调试环境可配置为 False。
        """
        self.task_goal = task_goal
        self.headless = headless
        
        # 初始化组件
        self.planner = DynamicExecutionGraph()
        self.browser_service: Optional[BrowserService] = None
        
        # 运行时状态
        self.is_running = False
        self.current_node: Optional[ExecutionNode] = None
        self.execution_counter = 0 

    def _init_browser(self):
        """延迟初始化浏览器资源，仅在 run 开始时调用。"""
        if not self.browser_service:
            try:
                print(f"--- [System] Initializing BrowserService (Headless: {self.headless}) ---")
                self.browser_service = BrowserService(headless=self.headless)
            except Exception as e:
                print(f"!!! [CRITICAL] Failed to initialize BrowserService: {e}")
                raise RuntimeError("Browser initialization failed.") from e

    def close(self):
        """资源清理钩子，确保浏览器进程不残留。"""
        if self.browser_service:
            print("--- [System] Closing BrowserService ---")
            try:
                self.browser_service.close()
            except Exception as e:
                print(f"[WARN] Error during browser closure: {e}")
            finally:
                self.browser_service = None

    def _execute_action(self, action: DecisionAction) -> WebObservation:
        """
        执行原子操作。
        """
        self.execution_counter += 1
        # 结构化日志
        print(f"\n>>> [STEP {self.execution_counter}] Executing Tool: [{action.tool_name}]")
        try:
            # 1. 纯本地工具：不需要浏览器（如 open_notepad）
            if action.tool_name == "open_notepad":
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
                            print(f"[LOCAL TOOL] Found resolved_output from node {nid} for notepad content.")
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

            else:
                # 2. 需要浏览器的工具：按需延迟初始化 BrowserService
                if not self.browser_service:
                    self._init_browser()

                observation = self.browser_service.execute_action(action)

            # 简单的结果摘要
            fb = observation.last_action_feedback
            status_icon = "✅" if fb and fb.status == "SUCCESS" else "❌"
            print(
                f"    {status_icon} Result: {fb.status if fb else 'NO FEEDBACK'} | "
                f"HTTP: {observation.http_status_code} | URL: {observation.current_url}"
            )

            if fb and fb.status == "FAILED":
                print(f"    ⚠️ Error Details: {fb.message}")

            return observation

        except Exception as e:
            print(f"!!! [CRITICAL] Unhandled Exception in Action Execution: {e}")
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
            print(f"    [PLAN] Node {node.node_id} COMPLETED. Graph updated.")
            return True
        
        # 2. 失败情况处理
        print(f"!!! [FAILURE] Node {node.node_id} failed. Reason: {feedback.message}")
        self.planner.prune_on_failure(node.node_id, feedback.message)
        
        # 检查节点的失败策略
        if node.action.on_failure_action == "STOP_TASK":
            print(f"!!! Strategy is STOP_TASK. Halting execution.")
            node.current_status = ExecutionNodeStatus.FAILED
            return False
            
        elif node.action.on_failure_action == "RE_EVALUATE":
            print(f"--- [RE-PLANNING] Initiating Dynamic Correction for Node {node.node_id} ---")
            
            # A. 构造纠错上下文
            # 我们创建一个临时的 Goal，明确告诉 LLM 发生了什么错误
            correction_goal = self.task_goal.model_copy() # 需要 Pydantic 的 copy 方法
            correction_goal.target_description = (
                f"ORIGINAL GOAL: {self.task_goal.target_description}\n"
                f"CONTEXT: The step '{node.action.tool_name}' FAILED.\n"
                f"ERROR MESSAGE: {feedback.message}\n"
                f"TASK: Generate a short corrective plan (1-3 steps) to fix this error and achieve the original goal."
            )
            
            # B. 调用 LLM 生成纠错片段
            # 注意：传入当前的 observation，这样 LLM 可以看到报错后的页面状态
            try:
                print(f"    [LLM] Requesting correction plan...")
                correction_nodes = LLMAdapter.generate_nodes(correction_goal, observation)
                
                if correction_nodes:
                    # C. 注入新计划
                    print(f"    [PLAN] Injecting {len(correction_nodes)} correction nodes...")
                    self.planner.inject_correction_plan(node.node_id, correction_nodes)
                    return True # 继续执行循环，下次会取到新注入的节点
                else:
                    print("    [LLM] Returned empty correction plan. Cannot recover.")
                    return False
                    
            except Exception as e:
                print(f"    [ERROR] Re-planning failed: {e}")
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
            print(f"[WARN] Visualization failed: {e}")

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
                print(f"--- [RESOLVE] Replaced '{value}' with captured output for '{key}'.")
        
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
        """主执行循环"""
        self.is_running = True
        try:
            # 1. 规划阶段 (Planning Phase)
            # 只有当计划为空时，才请求 LLM。支持 "Human-in-the-loop" 或 "Pre-loaded Plan" 模式。
            if not self.planner.nodes:
                print("\n--- Phase 1: Dynamic Planning (LLM) ---")
                self.planner.generate_initial_plan_with_llm(self.task_goal)
            else:
                print("\n--- Phase 1: Static Plan Loaded (Skipping LLM) ---")
            
            # 保存初始计划快照
            self._save_visualization("00_initial_plan")
            
            if not self.planner.nodes:
                print("[ERROR] Execution halted: Plan is empty after initialization.")
                return

            # 2. 执行阶段 (Execution Phase)
            print("\n--- Phase 2: Execution Loop ---")
            while self.is_running:
                
                # 获取下一个可执行节点 (Priority-based DFS)
                self.current_node = self.planner.get_next_node_to_execute()
                
                if self.current_node is None:
                    print("\n[FINISH] No more PENDING nodes. Task completed or path exhausted.")
                    break
                    
                # 状态流转: PENDING -> RUNNING
                self.current_node.current_status = ExecutionNodeStatus.RUNNING

                # 动态参数替换 (Dynamic Argument Resolution)
                try:
                    resolved_action = self._resolve_dynamic_args(self.current_node)
                    # 使用解析后的 action
                    self.current_node.action = resolved_action 
                except ValueError as e:
                    # 参数替换失败，节点直接标记为失败
                    print(f"!!! [ERROR] Dynamic Argument Resolution FAILED ({self.current_node.node_id}): {e}")
                    self.current_node.current_status = ExecutionNodeStatus.FAILED
                    # 构造一个失败的 Observation 来触发正常的失败处理流程
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
                    # [修改点 3] 赋值 last_observation
                    self.current_node.last_observation = observation
                    should_continue = self._handle_execution_result(self.current_node, observation)
                    self._save_visualization(f"step_{self.execution_counter:02d}_{self.current_node.node_id}_FAIL")
                    if not should_continue:
                        self.is_running = False
                        break
                    continue # 跳过本轮剩余部分，继续下一循环获取下一个节点
                    
                # 执行
                observation = self._execute_action(self.current_node.action)
                
                # 状态流转: RUNNING -> SUCCESS/FAILED & Pruning
                should_continue = self._handle_execution_result(self.current_node, observation)
                
                # [修改点 4] 结果捕获逻辑：使用直接赋值，因为 resolved_output 现在是模型的一部分。
                if self.current_node.current_status == ExecutionNodeStatus.SUCCESS and observation.last_action_feedback and observation.last_action_feedback.message:
                    self.current_node.resolved_output = observation.last_action_feedback.message
                
                # 快照审计
                self._save_visualization(f"step_{self.execution_counter:02d}_{self.current_node.node_id}")
                
                if not should_continue:
                    self.is_running = False
                    break
                
                # 硬性安全熔断 (防止无限循环)
                if self.execution_counter >= 50:
                    print("[ABORT] Reached max safety iteration limit (50).")
                    break
                    
        except KeyboardInterrupt:
            print("\n[USER ABORT] Execution interrupted by user.")
        except Exception as e:
            print(f"\n[FATAL ERROR] Unhandled exception in run loop: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 任务结束时调用总结报告
            self._generate_execution_summary() 
            
            self.close()
            print("--- DecisionMaker Terminated ---")


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
            "get_attribute",
            "open_notepad",
            "take_screenshot",
            "click_nth",
            "find_link_by_text",
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