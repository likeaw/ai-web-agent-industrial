# 文件: backend/src/agent/DecisionMaker.py

import time
import uuid
import os # 导入 os 用于文件操作
from typing import Optional
from backend.src.agent.Planner import DynamicExecutionGraph # <-- 核心依赖
from backend.src.services.LLMAdapter import LLMAdapter
from backend.src.data_models.decision_engine.decision_models import (
    TaskGoal, WebObservation, ExecutionNode, ExecutionNodeStatus, DecisionAction, ActionFeedback
)
from backend.src.visualization.VisualizationAdapter import VisualizationAdapter 
# *************************************************

# ----------------------------------------------------------------------
# 辅助类定义 

class MockBrowserDriver:
    """模拟浏览器驱动器的最小接口"""
    def __init__(self, initial_url="about:blank"):
        self._url = initial_url
    
    def get_current_url(self):
        return self._url
    
    def navigate(self, url):
        self._url = url

# ----------------------------------------------------------------------

class DecisionMaker:
    """
    决策执行者 (DecisionMaker)
    负责驱动整个 Agent 的执行流，并协调规划、执行和反馈。
    """

    def __init__(self, task_goal: TaskGoal, browser_driver: MockBrowserDriver):
        self.task_goal = task_goal
        self.browser_driver = browser_driver  
        self.planner = DynamicExecutionGraph() # <-- 实例化 Planner 模块
        self.is_running = False
        self.current_node: Optional[ExecutionNode] = None
        self.execution_counter = 0 

    def _execute_action(self, action: DecisionAction) -> WebObservation:
        """执行动作桩函数 (逻辑不变)"""
        self.execution_counter += 1
        print(f"\n[ACTION] Executing: {action.tool_name} with args: {action.tool_args}")
        
        success = True
        if self.execution_counter == 3 and action.tool_name == "click_element":
            success = False
            
        time.sleep(1) 
            
        current_url = self.browser_driver.get_current_url()
            
        if success:
            return WebObservation(
                observation_timestamp_utc=str(time.time()),
                current_url=current_url,
                http_status_code=200,
                page_load_time_ms=500,
                is_authenticated=False,
                key_elements=[], 
                screenshot_available=True,
                last_action_feedback=ActionFeedback(status='SUCCESS', error_code='N/A', message='Action executed successfully.'),
                memory_context="Action succeeded."
            )
        else:
            print("Action execution FAILED (Simulated Failure).")
            return WebObservation(
                observation_timestamp_utc=str(time.time()),
                current_url=current_url,
                http_status_code=500,
                page_load_time_ms=0,
                is_authenticated=False,
                key_elements=[],
                screenshot_available=False,
                last_action_feedback=ActionFeedback(status='FAILED', error_code='E_TIMEOUT', message='Simulated timeout during click.'),
                memory_context="Action failed due to error."
            )

    def _handle_execution_result(self, node: ExecutionNode, observation: WebObservation):
        """处理执行结果 (逻辑不变)"""
        feedback = observation.last_action_feedback
        
        if feedback and feedback.status == 'FAILED':
            print(f"!!! Node {node.node_id} FAILED. Reason: {feedback.message}")
            
            # 核心：调用 Planner 模块进行剪枝
            self.planner.prune_on_failure(node.node_id, feedback.message)
            
            if node.action.on_failure_action in ["RE_EVALUATE", "STOP"]:
                node.current_status = ExecutionNodeStatus.FAILED
                return False 
        else:
            node.current_status = ExecutionNodeStatus.SUCCESS
            print(f"-> Node {node.node_id} SUCCESS. Status updated.")
            return True
        
        return False

    def _save_visualization(self, filename: str):
        """
        负责文件I/O和日志打印，隔离于渲染逻辑。
        """
        output_dir = 'logs/graphs'
        
        try:
            # 1. 调用 Adapter 渲染字符串 (高内聚：VisualizationAdapter 只负责渲染)
            html_content = VisualizationAdapter.render_graph_to_html_string(
                self.planner, 
                output_filename=filename
            )
            
            # 2. 构造路径并创建目录 (高内聚：DecisionMaker 负责流程 I/O)
            os.makedirs(output_dir, exist_ok=True)
            full_path = os.path.join(output_dir, f"{filename}.html")
            
            # 3. 写入文件
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
            # 4. 打印日志
            print(f"\n[VISUALIZATION SUCCESS] 图表已成功保存为 HTML 文件。")
            print(f"文件路径: {os.path.abspath(full_path)}")
            print(f"✅ 如何查看: 双击该 HTML 文件即可在浏览器中查看图形。")
            
        except Exception as e:
            timestamp = time.strftime("%H:%M:%S")
            print(f"\n[{timestamp} VISUALIZATION CRITICAL ERROR] 无法保存 HTML 源码。错误: {e}")

    def run(self):
        """
        DecisionMaker 主循环
        """
        self.is_running = True
        self.execution_counter = 0
        
        # 1. 计划初始化 (核心修复点)
        # 只有在没有任何节点时，才调用 LLM 生成初始计划。
        # 如果节点已通过 load_plan_from_json 预加载，则跳过 LLM 调用。
        if not self.planner.nodes:
            self.planner.generate_initial_plan_with_llm(self.task_goal)
        
        if not self.planner.nodes:
            print("Execution halted: Initial plan is empty.")
            self.is_running = False
            return
            
        # 注意：此处不再调用 _save_visualization，因为 JSON 加载测试中
        # 这一步已经挪到 __main__ 块中，以避免重复命名和逻辑冲突。
            
        while self.is_running:
            
            # 2. 获取下一个待执行的节点
            self.current_node = self.planner.get_next_node_to_execute()
            
            if self.current_node is None:
                print("\nPlan execution finished. No more PENDING nodes.")
                self.is_running = False
                break
                
            # 3. 标记节点为 RUNNING
            self.current_node.current_status = ExecutionNodeStatus.RUNNING
            
            print(f"\n[DECISION] Selecting Node {self.current_node.node_id} (P{self.current_node.execution_order_priority})")
            
            # 4. 执行动作并获取新的观察结果
            new_observation = self._execute_action(self.current_node.action)
            
            # 5. 处理执行结果和状态更新
            if not self._handle_execution_result(self.current_node, new_observation):
                self.is_running = False
                
                # *********** 集成可视化：最终/失败状态 (调用辅助方法) ***********
                self._save_visualization(f"plan_{self.task_goal.task_uuid}_final_failed")
                # **************************************************
                break
            
            # *********** 集成可视化：每执行一步，生成快照 ***********
            self._save_visualization(f"plan_{self.task_goal.task_uuid}_step_{self.execution_counter:02d}")
            # **********************************************************
            
            # 6. 检查时间限制
            if self.execution_counter >= 5:
                 print("Execution halted: Reached max iteration limit.")
                 self.is_running = False
                 break
                 
        print("DecisionMaker loop terminated.")


# ----------------------------------------------------------------------
# 示例用法 (使用 JSON 加载进行可视化测试)
        
if __name__ == '__main__':
    
    # 1. 定义 JSON 文件路径 
    JSON_PLAN_FILE = os.path.abspath(os.path.join(
        os.path.dirname(__file__), 
        '..', '..', '..', 
        'data', 'complex_plan.json'
    ))
    
    if not os.path.exists(JSON_PLAN_FILE):
        print(f"FATAL ERROR: JSON plan file not found at {JSON_PLAN_FILE}")
        print("请确认您已创建 'data' 目录并将 'complex_plan.json' 放置其中。")
        exit(1)

    # 2. 构造任务目标
    goal = TaskGoal(
        task_uuid="T-JSON-" + str(uuid.uuid4())[:8],
        step_id="S001",
        target_description="Visualize complex tree structure from JSON.",
        priority_level=1,
        max_execution_time_seconds=30,
        required_data={},
        allowed_actions=["navigate_to", "type_text", "click_element"] 
    )
    
    mock_browser = MockBrowserDriver("https://example.com/start")
    
    maker = DecisionMaker(goal, mock_browser)

    # 3. 从 JSON 加载计划，直接填充 maker.planner
    print(f"--- [JSON Planning] Loading static plan from: {JSON_PLAN_FILE} ---")
    maker.planner.load_plan_from_json(JSON_PLAN_FILE)
    
    if maker.planner.nodes:
        print("\n--- DecisionMaker Execution Start ---")
        
        # 初始可视化 (在执行任何动作前保存图的初始状态)
        maker._save_visualization(f"plan_{maker.task_goal.task_uuid}_0_initial_state")

        # 4. 启动完整的 DecisionMaker 执行循环
        # run() 方法现在会看到 maker.planner.nodes 非空，从而跳过 LLM 规划，直接执行 JSON 计划。
        maker.run()
        
    else:
        print("Plan load failed. Execution skipped.")
    
    print("\nDecisionMaker script finished.")