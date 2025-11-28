# 文件: backend/src/agent/DecisionMaker.py

import time
import uuid
import os
import sys
import asyncio # 新增: 引入异步库
from typing import Optional, Callable, Awaitable, Dict, Any, List # 新增: 异步和字典类型提示
from dotenv import load_dotenv

# --- 核心模块引入 ---
from backend.src.agent.Planner import DynamicExecutionGraph
from backend.src.services.LLMAdapter import LLMAdapter
from backend.src.visualization.VisualizationAdapter import VisualizationAdapter
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

    def __init__(self, 
                 task_goal: TaskGoal, 
                 # 新增: 异步回调函数，用于推送状态给前端
                 status_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None, 
                 headless: bool = True):
        """
        初始化决策引擎。
        
        :param task_goal: 任务目标对象。
        :param status_callback: 异步回调函数，用于推送状态给前端。
        :param headless: 浏览器运行模式。生产环境通常为 True，调试环境可配置为 False。
        """
        self.task_goal = task_goal
        self.headless = headless
        self.status_callback = status_callback # 保存回调函数
        
        # 初始化组件
        self.planner = DynamicExecutionGraph()
        self.browser_service: Optional[BrowserService] = None
        
        # 运行时状态
        self.is_running = False
        self.current_node: Optional[ExecutionNode] = None
        self.execution_counter = 0 
        
        # 线程环境下的事件循环 (在 run() 中初始化)
        self._loop: Optional[asyncio.AbstractEventLoop] = None


    # --- 新增: 状态报告方法 (封装线程安全调用) ---
    def _report_status(self, data: Dict[str, Any]):
        """
        内部方法：安全地在 DecisionMaker 线程中调用异步回调函数。
        这个方法将任务提交给主线程的事件循环，并阻塞等待完成。
        """
        if self.status_callback and self._loop:
            # 确保包含任务ID
            data["task_id"] = self.task_goal.task_uuid
            
            # 使用 run_coroutine_threadsafe 提交到主事件循环
            future = asyncio.run_coroutine_threadsafe(self.status_callback(data), self._loop)
            try:
                # 阻塞直到回调完成 (确保前端收到状态)
                future.result(timeout=5) # 设置超时，避免死锁
            except Exception as e:
                # 打印警告，但允许 Agent 继续执行
                print(f"[WARN] Failed to broadcast status via callback: {type(e).__name__}: {e}")
        elif self.status_callback and not self._loop:
            # 这种情况不应该发生，除非 run() 没有正确初始化 _loop
            print("[WARN] Callback is set but event loop is missing. Cannot report status.")


    def _init_browser(self):
        """延迟初始化浏览器资源，仅在 run 开始时调用。"""
        if not self.browser_service:
            try:
                print(f"--- [System] Initializing BrowserService (Headless: {self.headless}) ---")
                self.browser_service = BrowserService(headless=self.headless)
                # 新增状态报告
                self._report_status({
                    "type": "STATUS", 
                    "message": "BrowserService initialized successfully.", 
                    "level": "INFO"
                })
            except Exception as e:
                print(f"!!! [CRITICAL] Failed to initialize BrowserService: {e}")
                # 新增错误报告
                self._report_status({
                    "type": "STATUS", 
                    "message": f"Browser initialization failed: {str(e)}", 
                    "level": "ERROR"
                })
                raise RuntimeError("Browser initialization failed.") from e

    def close(self):
        """资源清理钩子，确保浏览器进程不残留。"""
        if self.browser_service:
            print("--- [System] Closing BrowserService ---")
            # 新增状态报告
            self._report_status({
                "type": "STATUS", 
                "message": "BrowserService closing.", 
                "level": "INFO"
            })
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
        
        # 新增: 节点 RUNNING 状态报告
        self._report_status({
            "type": "NODE_UPDATE",
            "node_id": self.current_node.node_id if self.current_node else "N/A",
            "status": ExecutionNodeStatus.RUNNING.value,
            "tool": action.tool_name,
            "reasoning": action.reasoning,
            "message": f"Executing tool: {action.tool_name}"
        })
        
        if not self.browser_service:
            raise RuntimeError("BrowserService is not initialized.")

        try:
            # 调用底层服务
            observation = self.browser_service.execute_action(action)
            
            # 简单的结果摘要
            fb = observation.last_action_feedback
            status_icon = "✅" if fb and fb.status == "SUCCESS" else "❌"
            print(f"    {status_icon} Result: {fb.status if fb else 'NO FEEDBACK'} | HTTP: {observation.http_status_code} | URL: {observation.current_url}")
            
            if fb and fb.status == "FAILED":
                print(f"    ⚠️ Error Details: {fb.message}")
                
            return observation
            
        except Exception as e:
            print(f"!!! [CRITICAL] Unhandled Exception in Action Execution: {e}")
            
            # 新增: 报告执行时致命错误
            self._report_status({
                "type": "STATUS",
                "message": f"Critical execution error during action: {str(e)}",
                "level": "ERROR"
            })
            
            # 返回兜底的失败观测，防止程序崩溃，允许 Planner 尝试恢复
            return WebObservation(
                current_url="unknown",
                http_status_code=500,
                page_load_time_ms=0,
                key_elements=[],
                memory_context="System Critical Failure",
                last_action_feedback=ActionFeedback(
                    status="FAILED", error_code="SYSTEM_EXCEPTION", message=str(e)
                )
            )

    def _handle_execution_result(self, node: ExecutionNode, observation: WebObservation) -> bool:
        """
        处理执行结果：成功则继续，失败则触发 LLM 动态重规划 (Self-Correction)。
        """
        node.last_observation = observation # 存储最新的观测，用于可视化和重规划

        feedback = observation.last_action_feedback
        if not feedback:
            # 如果没有反馈，视为失败，防止空指针异常
            feedback = ActionFeedback(status="FAILED", error_code="NO_FEEDBACK", message="Action execution returned no feedback.")

        # 1. 成功情况
        if feedback.status == 'SUCCESS':
            node.current_status = ExecutionNodeStatus.SUCCESS
            print(f"    [PLAN] Node {node.node_id} COMPLETED. Graph updated.")
            
            # 新增: 报告节点 SUCCESS 状态
            self._report_status({
                "type": "NODE_UPDATE",
                "node_id": node.node_id,
                "status": ExecutionNodeStatus.SUCCESS.value,
                "tool": node.action.tool_name,
                "url": observation.current_url,
                "result": feedback.message
            })
            return True
        
        # 2. 失败情况处理
        print(f"!!! [FAILURE] Node {node.node_id} failed. Reason: {feedback.message}")
        
        # 新增: 报告节点 FAILED 状态 (在重规划前报告，确保状态被捕获)
        self._report_status({
            "type": "NODE_UPDATE",
            "node_id": node.node_id,
            "status": ExecutionNodeStatus.FAILED.value,
            "tool": node.action.tool_name,
            "url": observation.current_url,
            "error_message": feedback.message
        })

        self.planner.prune_on_failure(node.node_id, feedback.message)
        
        # 检查节点的失败策略 (RE_EVALUATE 逻辑保持不变)
        if node.action.on_failure_action == "STOP_TASK":
            print(f"!!! Strategy is STOP_TASK. Halting execution.")
            node.current_status = ExecutionNodeStatus.FAILED
            # 报告停止状态
            self._report_status({
                "type": "STATUS",
                "message": f"Task stopped due to STOP_TASK failure strategy on node {node.node_id}.",
                "level": "ERROR"
            })
            return False
            
        elif node.action.on_failure_action == "RE_EVALUATE":
            print(f"--- [RE-PLANNING] Initiating Dynamic Correction for Node {node.node_id} ---")
            
            # 报告重规划开始
            self._report_status({
                "type": "STATUS",
                "message": f"Initiating dynamic re-evaluation for node {node.node_id}.",
                "level": "WARNING"
            })

            # A. 构造纠错上下文 (保持不变)
            correction_goal = self.task_goal.model_copy() 
            correction_goal.target_description = (
                f"ORIGINAL GOAL: {self.task_goal.target_description}\n"
                f"CONTEXT: The step '{node.action.tool_name}' FAILED.\n"
                f"ERROR MESSAGE: {feedback.message}\n"
                f"TASK: Generate a short corrective plan (1-3 steps) to fix this error and achieve the original goal."
            )
            
            # B. 调用 LLM 生成纠错片段 (保持不变)
            try:
                print(f"    [LLM] Requesting correction plan...")
                correction_nodes: List[ExecutionNode] = LLMAdapter.generate_nodes(correction_goal, observation)
                
                if correction_nodes:
                    # C. 注入新计划 (保持不变)
                    print(f"    [PLAN] Injecting {len(correction_nodes)} correction nodes...")
                    self.planner.inject_correction_plan(node.node_id, correction_nodes)
                    return True 
                else:
                    print("    [LLM] Returned empty correction plan. Cannot recover.")
                    return False
                    
            except Exception as e:
                print(f"    [ERROR] Re-planning failed: {e}")
                # 报告重规划失败
                self._report_status({
                    "type": "STATUS",
                    "message": f"Re-planning failed after node {node.node_id}: {str(e)}",
                    "level": "ERROR"
                })
                return False
                
        # 默认处理
        node.current_status = ExecutionNodeStatus.FAILED
        return True

    def _save_visualization(self, suffix: str):
        """生成可视化快照，并向 WebSocket 推送 HTML 内容。"""
        filename = f"plan_{self.task_goal.task_uuid}_{suffix}"
        
        try:
            # 渲染图
            output_dir = 'logs/graphs'
            os.makedirs(output_dir, exist_ok=True)
            content = VisualizationAdapter.render_graph_to_html_string(self.planner, filename)
            
            # 写入文件 (保留原有的文件保存逻辑)
            with open(os.path.join(output_dir, f"{filename}.html"), 'w', encoding='utf-8') as f:
                f.write(content)
                
            # 新增: 推送可视化 HTML 给前端
            self._report_status({
                "type": "VISUALIZATION",
                "html": content,
                "level": "REPORT"
            })
            
        except Exception as e:
            print(f"[WARN] Visualization failed: {e}")
            self._report_status({
                "type": "STATUS",
                "message": f"Visualization generation failed: {str(e)}",
                "level": "WARNING"
            })

    def _resolve_dynamic_args(self, node: ExecutionNode) -> DecisionAction:
        """动态参数替换方法 (保持不变)"""
        resolved_args = node.action.tool_args.copy()
        
        for key, value in node.action.tool_args.items():
            if isinstance(value, str) and value.startswith("{result_of:") and value.endswith("}"):
                source_node_id = value[len("{result_of:"):-1]
                
                source_node = self.planner.nodes.get(source_node_id)
                if not source_node or source_node.current_status != ExecutionNodeStatus.SUCCESS:
                    raise ValueError(f"Dynamic argument source node '{source_node_id}' not found or not successful (Status: {source_node.current_status.name if source_node else 'Not Found'}).")
                
                resolved_value = source_node.resolved_output
                if resolved_value is None:
                    raise ValueError(f"Dynamic argument source node '{source_node_id}' succeeded but has no captured output ('resolved_output').")

                resolved_args[key] = resolved_value
                print(f"--- [RESOLVE] Replaced '{value}' with captured output for '{key}'.")
        
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
        """生成详细的执行报告 (保持原有的打印逻辑，并新增报告开始/结束状态)"""
        
        # 新增: 报告任务总结开始
        self._report_status({
            "type": "STATUS",
            "message": "Generating final execution summary report...",
            "level": "REPORT"
        })
        
        # (原有的打印逻辑保持不变)
        print("\n==================================================")
        print("          ✨ 任务执行总结报告 ✨")
        print("==================================================")
        
        total_nodes = len(self.planner.nodes)
        successful_nodes = 0
        
        for node_id in self.planner.nodes_execution_order:
            node = self.planner.nodes[node_id]
            
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
            
            resolved_output = node.resolved_output
            if resolved_output is not None:
                summary_parts.append(f"Output: \033[96m{resolved_output[:80]}{'...' if len(resolved_output) > 80 else ''}\033[0m") 
            
            if node.current_status == ExecutionNodeStatus.FAILED and node.last_observation and node.last_observation.last_action_feedback:
                feedback = node.last_observation.last_action_feedback
                summary_parts.append(f"Error: \033[91m{feedback.error_code} - {feedback.message[:80]}{'...' if len(feedback.message) > 80 else ''}\033[0m")
            
            if node.current_status == ExecutionNodeStatus.SUCCESS:
                successful_nodes += 1

            print(f"| {' | '.join(summary_parts)}")

        print("==================================================")
        print(f"总节点数: {total_nodes} | 成功节点数: {successful_nodes}")
        print("==================================================")
        
        # 新增: 报告任务总结完成
        self._report_status({
            "type": "STATUS",
            "message": f"Summary generated: {successful_nodes}/{total_nodes} nodes successful.",
            "level": "REPORT"
        })

    def run(self):
        """主执行循环"""
        
        # --- 核心修改: 线程事件循环初始化 ---
        try:
            # 尝试获取当前线程的事件循环（如果 DecisionMaker 是在 asyncio.run 中启动的）
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            # 如果是 threading.Thread 启动，创建一个新的事件循环
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
        self.is_running = True
        self._init_browser()
        
        # 新增: 报告任务启动状态
        self._report_status({
            "type": "STATUS",
            "message": f"Agent starting execution loop for: {self.task_goal.target_description}",
            "level": "INFO"
        })
        
        try:
            # 1. 规划阶段 (Planning Phase)
            # ... 保持不变 ...
            if not self.planner.nodes:
                print("\n--- Phase 1: Dynamic Planning (LLM) ---")
                
                # 新增: 报告规划开始
                self._report_status({
                    "type": "STATUS",
                    "message": "Starting LLM dynamic planning phase...",
                    "level": "INFO"
                })

                self.planner.generate_initial_plan_with_llm(self.task_goal)
            else:
                print("\n--- Phase 1: Static Plan Loaded (Skipping LLM) ---")
            
            # 保存初始计划快照 (现在会触发 WebSocket 推送)
            self._save_visualization("00_initial_plan")
            
            if not self.planner.nodes:
                print("[ERROR] Execution halted: Plan is empty after initialization.")
                # 新增: 报告空计划错误
                self._report_status({
                    "type": "STATUS",
                    "message": "Execution halted: Plan is empty after initialization.",
                    "level": "ERROR"
                })
                return

            # 2. 执行阶段 (Execution Phase)
            print("\n--- Phase 2: Execution Loop ---")
            while self.is_running:
                
                self.current_node = self.planner.get_next_node_to_execute()
                
                if self.current_node is None:
                    print("\n[FINISH] No more PENDING nodes. Task completed or path exhausted.")
                    break
                    
                self.current_node.current_status = ExecutionNodeStatus.RUNNING

                # 动态参数替换
                try:
                    resolved_action = self._resolve_dynamic_args(self.current_node)
                    self.current_node.action = resolved_action 
                except ValueError as e:
                    print(f"!!! [ERROR] Dynamic Argument Resolution FAILED ({self.current_node.node_id}): {e}")
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
                    
                    # 报告参数解析失败状态
                    self._report_status({
                        "type": "NODE_UPDATE",
                        "node_id": self.current_node.node_id,
                        "status": ExecutionNodeStatus.FAILED.value,
                        "tool": self.current_node.action.tool_name,
                        "error_message": f"Argument resolution failed: {str(e)}"
                    })
                    
                    should_continue = self._handle_execution_result(self.current_node, observation)
                    self._save_visualization(f"step_{self.execution_counter:02d}_{self.current_node.node_id}_FAIL")
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
                
                # 快照审计 (现在会触发 WebSocket 推送)
                self._save_visualization(f"step_{self.execution_counter:02d}_{self.current_node.node_id}")
                
                if not should_continue:
                    self.is_running = False
                    break
                
                # 硬性安全熔断 
                if self.execution_counter >= 50:
                    print("[ABORT] Reached max safety iteration limit (50).")
                    # 新增: 报告熔断状态
                    self._report_status({
                        "type": "STATUS",
                        "message": "Execution aborted: Reached max safety iteration limit (50).",
                        "level": "ERROR"
                    })
                    break
                    
        except KeyboardInterrupt:
            print("\n[USER ABORT] Execution interrupted by user.")
            # 新增: 报告中断状态
            self._report_status({
                "type": "STATUS",
                "message": "Execution interrupted by user.",
                "level": "WARNING"
            })
        except Exception as e:
            print(f"\n[FATAL ERROR] Unhandled exception in run loop: {e}")
            import traceback
            traceback.print_exc()
            # 新增: 报告致命错误
            self._report_status({
                "type": "STATUS",
                "message": f"FATAL ERROR in run loop: {type(e).__name__}: {e}",
                "level": "ERROR"
            })
        finally:
            # 任务结束时调用总结报告
            self._generate_execution_summary() 
            
            self.close()
            
            # 新增: 报告任务最终完成
            self._report_status({
                "type": "STATUS",
                "message": "Task execution loop finished. System shutdown.",
                "level": "SUCCESS"
            })
            
            print("--- DecisionMaker Terminated ---")


# ----------------------------------------------------------------------
# 工业级入口点 (Entry Point) - 仅保留配置逻辑，移除 run() 调用
# ----------------------------------------------------------------------
        
if __name__ == '__main__':
    # 警告：此入口点仅用于配置测试，在 FastAPI 模式下，DecisionMaker.run() 
    # 应由 main_server.py 在独立线程中调用。
    
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
        allowed_actions=["navigate_to", "click_element", "type_text", "scroll", "wait", "extract_data", "get_attribute"]
    )
    
    # 4. 初始化 DecisionMaker (注意：不传入 status_callback，因为它不需要在此模式下报告)
    is_headless = os.getenv("BROWSER_HEADLESS", "False").lower() == "true"
    maker = DecisionMaker(goal, headless=is_headless)

    print("==================================================")
    print("    AI Web Agent - Industrial Decision Engine")
    print("==================================================")

    # 5. 执行分支 
    if target_json_file:
        print(f"[MODE] Replay/Test Mode")
        print(f"[INFO] Loading static plan from: {target_json_file}")
        
        try:
            maker.planner.load_plan_from_json(target_json_file)
        except AttributeError:
            print("[FATAL] Planner class is missing 'load_plan_from_json' method. Exiting.")
            sys.exit(1)
        
        if not maker.planner.nodes:
            print("[FATAL] JSON file loaded but contained no valid nodes. Exiting.")
            sys.exit(1)
            
        # maker.run() # <--- 关键修改：不再在此处运行，而是等待 main_server.py 导入并调用

        
    elif llm_key:
        print(f"[MODE] Dynamic Generative Mode")
        print(f"[INFO] LLM API Key detected. Agent will generate plan dynamically.")
        
        user_intent = "Go to bing.com and search for 'Industrial AI Agent'"
        print(f"[GOAL] {user_intent}")
        maker.task_goal.target_description = user_intent
        
        # maker.run() # <--- 关键修改：不再在此处运行

    else:
        print("[FATAL ERROR] System Configuration Incomplete.")
        print("Reason: No 'complex_plan.json' found in data/ AND no 'LLM_API_KEY' in environment.")
        print("Action: Please provide a static plan file OR configure your LLM credentials.")
        sys.exit(1)