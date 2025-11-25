# 文件: backend/src/agent/DecisionMaker.py

import time
import uuid
import os
import sys
from typing import Optional
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
        
        if not self.browser_service:
            raise RuntimeError("BrowserService is not initialized.")

        try:
            # 调用底层服务
            observation = self.browser_service.execute_action(action)
            
            # 简单的结果摘要
            fb = observation.last_action_feedback
            status_icon = "✅" if fb.status == "SUCCESS" else "❌"
            print(f"    {status_icon} Result: {fb.status} | HTTP: {observation.http_status_code} | URL: {observation.current_url}")
            
            if fb.status == "FAILED":
                print(f"    ⚠️ Error Details: {fb.message}")
                
            return observation
            
        except Exception as e:
            print(f"!!! [CRITICAL] Unhandled Exception in Action Execution: {e}")
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
        处理执行结果，更新图状态，触发剪枝逻辑。
        :return: bool (是否继续执行)
        """
        feedback = observation.last_action_feedback
        
        if feedback and feedback.status == 'FAILED':
            # 失败处理逻辑
            self.planner.prune_on_failure(node.node_id, feedback.message)
            
            # 检查节点的失败策略配置
            if node.action.on_failure_action == "STOP_TASK":
                print(f"!!! Node {node.node_id} triggers STOP_TASK. Halting execution.")
                node.current_status = ExecutionNodeStatus.FAILED
                return False
            elif node.action.on_failure_action == "RE_EVALUATE":
                # TODO: 未来可在此处触发 LLM 重新规划 (Re-planning)
                print(f"!!! Node {node.node_id} failed (RE_EVALUATE). Pruning children.")
                node.current_status = ExecutionNodeStatus.FAILED
                # 暂时策略：如果没有备选路径，规划器将返回 None，循环自然结束
                return True 
        else:
            # 成功处理逻辑
            node.current_status = ExecutionNodeStatus.SUCCESS
            return True
        
        return True

    def _save_visualization(self, suffix: str):
        """生成可视化快照"""
        filename = f"plan_{self.task_goal.task_uuid}_{suffix}"
        try:
            VisualizationAdapter.render_graph_to_html_string(self.planner, output_filename=filename)
            # 注意：实际写入文件的逻辑若在 VisualizationAdapter 中被移除，需在此处补全或确保 Adapter 只是渲染
            # 这里假设 Adapter 依然负责渲染字符串，文件写入由调用方负责（如之前代码所示）
            # 为了代码整洁，这里复用之前的写入逻辑：
            output_dir = 'logs/graphs'
            os.makedirs(output_dir, exist_ok=True)
            content = VisualizationAdapter.render_graph_to_html_string(self.planner, filename)
            with open(os.path.join(output_dir, f"{filename}.html"), 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            print(f"[WARN] Visualization failed: {e}")

    def run(self):
        """主执行循环"""
        self.is_running = True
        self._init_browser()
        
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
                
                # 执行
                observation = self._execute_action(self.current_node.action)
                
                # 状态流转: RUNNING -> SUCCESS/FAILED & Pruning
                should_continue = self._handle_execution_result(self.current_node, observation)
                
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
            self.close()
            print("--- DecisionMaker Terminated ---")


# ----------------------------------------------------------------------
# 工业级入口点 (Entry Point)
# ----------------------------------------------------------------------
        
if __name__ == '__main__':
    # 1. 环境完整性检查
    # 检查 .env 是否包含关键配置，不依赖默认值，防止误操作
    llm_key = os.getenv("LLM_API_KEY")
    # 定义一个标准测试计划路径
    default_json_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..', '..', 'data', 'complex_plan.json'
    ))
    
    # 2. 模式判定 (Mode Selection)
    target_json_file = default_json_path if os.path.exists(default_json_path) else None
    
    # 3. 构造任务上下文 (Task Context)
    # 即使是重放模式，也需要基本的 Goal 定义
    goal = TaskGoal(
        task_uuid=f"TASK-{str(uuid.uuid4())[:8]}",
        step_id="INIT",
        target_description="Execute industrial automation task.", 
        priority_level=1,
        max_execution_time_seconds=120,
        allowed_actions=["navigate_to", "click_element", "type_text", "scroll", "wait", "extract_data"]
    )
    
    # 4. 初始化 DecisionMaker
    # 开发环境下 headless=False 以便观察，生产环境应读取环境变量配置
    is_headless = os.getenv("BROWSER_HEADLESS", "False").lower() == "true"
    maker = DecisionMaker(goal, headless=is_headless)

    print("==================================================")
    print("   AI Web Agent - Industrial Decision Engine")
    print("==================================================")

    # 5. 执行分支 (Strict Branching)
    if target_json_file:
        print(f"[MODE] Replay/Test Mode")
        print(f"[INFO] Loading static plan from: {target_json_file}")
        maker.planner.load_plan_from_json(target_json_file)
        
        if not maker.planner.nodes:
            print("[FATAL] JSON file loaded but contained no valid nodes. Exiting.")
            sys.exit(1)
            
        maker.run()
        
    elif llm_key:
        print(f"[MODE] Dynamic Generative Mode")
        print(f"[INFO] LLM API Key detected. Agent will generate plan dynamically.")
        
        # 在动态模式下，必须有明确的任务描述。
        # 这里模拟从上游（如 API 请求或 CLI 参数）获取的任务。
        # 在实际部署中，这里不应是硬编码，而是 sys.argv 或 API payload
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