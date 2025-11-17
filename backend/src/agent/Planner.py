# 文件: backend/src/agent/Planner.py

import uuid
from typing import List, Dict, Optional
from collections import deque
from backend.src.services.LLMAdapter import LLMAdapter 
from backend.src.data_models.decision_engine.decision_models import (
    ExecutionNode, ExecutionNodeStatus, TaskGoal, DecisionAction
)

class DynamicExecutionGraph:
    """
    动态执行图 (DEG) 管理器。
    负责存储、遍历和运行时剪枝 ExecutionNode。
    实现了优先级驱动的深度优先遍历逻辑，确保执行的健壮性和高效性。
    """
    def __init__(self):
        # 使用字典存储节点，以便通过 ID 快速查找
        self.nodes: Dict[str, ExecutionNode] = {}
        self.root_node_id: Optional[str] = None

    def add_node(self, node: ExecutionNode):
        """添加节点到图中，并维护父子关系和子节点优先级排序。"""
        if node.node_id in self.nodes:
            # 确保节点ID唯一性
            raise ValueError(f"Node ID {node.node_id} already exists.")
        
        self.nodes[node.node_id] = node
        
        # 维护根节点
        if node.parent_id is None:
            if self.root_node_id is not None and self.root_node_id != node.node_id:
                raise ValueError("Attempted to add a second root node to a non-empty graph.") 
            self.root_node_id = node.node_id
        
        # 维护父节点关系
        if node.parent_id and node.parent_id in self.nodes:
            parent_node = self.nodes[node.parent_id]
            if node.node_id not in parent_node.child_ids:
                parent_node.child_ids.append(node.node_id)
            
            # 【健壮性关键】：始终保持子节点按优先级排序（数字越小，优先级越高）。
            parent_node.child_ids.sort(key=lambda id: self.nodes[id].execution_order_priority)

    def get_next_node_to_execute(self) -> Optional[ExecutionNode]:
        """
        核心：实现优先级驱动的深度优先遍历，找到下一个 PENDING 节点。
        优先级的数字越小，优先级越高。
        """
        if not self.root_node_id or self.root_node_id not in self.nodes:
            return None
        
        # 1. 遍历图，收集所有 PENDING 节点
        # 使用 deque 进行遍历，模拟 DFS/BFS，但最终选择取决于优先级
        stack = deque([self.root_node_id])
        pending_nodes_by_priority: Dict[int, List[ExecutionNode]] = {}
        visited = set()
        
        while stack:
            node_id = stack.popleft() # 使用 popleft() 保持遍历顺序稳定
            
            if node_id in visited:
                continue
            visited.add(node_id)
            
            node = self.nodes.get(node_id)
            if not node:
                continue

            # 收集 PENDING 节点
            if node.current_status == ExecutionNodeStatus.PENDING:
                if node.execution_order_priority not in pending_nodes_by_priority:
                    pending_nodes_by_priority[node.execution_order_priority] = []
                pending_nodes_by_priority[node.execution_order_priority].append(node)
                
            # 只有 SUCCESS 的节点才遍历其子节点 (保证深度优先/前置条件满足)
            if node.current_status == ExecutionNodeStatus.SUCCESS:
                # 子节点已在 add_node 中按优先级排序，确保在遍历中优先探查高优先级子路径
                stack.extend(node.child_ids)


        # 2. 最终选择：从所有待执行节点中，选择优先级最高的
        if not pending_nodes_by_priority:
            return None
            
        # 找到数字最小的键 (最高优先级)
        highest_priority = min(pending_nodes_by_priority.keys())
        
        # 返回优先级最高的队列中的第一个节点
        return pending_nodes_by_priority[highest_priority][0]


    def prune_on_failure(self, failed_node_id: str, reason: str):
        """
        失败时剔除节点及其所有子节点 (PRUNED 状态)，并标记失败原因。
        """
        if failed_node_id not in self.nodes:
            return

        failed_node = self.nodes[failed_node_id]
        if failed_node.current_status != ExecutionNodeStatus.SUCCESS:
            failed_node.current_status = ExecutionNodeStatus.FAILED
            failed_node.failure_reason = reason

        # 递归剪枝所有子节点
        to_prune_queue = deque(failed_node.child_ids)
        while to_prune_queue:
            prune_id = to_prune_queue.popleft()
            prune_node = self.nodes.get(prune_id)
            
            # 只剪枝 PENDING 或 SKIPPED 的节点，避免影响已成功的路径
            if prune_node and prune_node.current_status in [ExecutionNodeStatus.PENDING, ExecutionNodeStatus.SKIPPED]:
                prune_node.current_status = ExecutionNodeStatus.PRUNED
                prune_node.failure_reason = f"Pruned due to failure of ancestor node: {failed_node_id}"
                to_prune_queue.extend(prune_node.child_ids)
        
        
    def generate_initial_plan_with_llm(self, task_goal: TaskGoal) -> 'DynamicExecutionGraph':
        """
        调用 LLMAdapter 获取 ExecutionNode 列表，并构建图。
        无硬编码，依赖 LLMAdapter 返回的 JSON 数据。
        """
        print(f"--- [LLM Planning] Calling LLM to generate plan for {task_goal.task_uuid} ---")
        
        # 清空现有节点，准备新计划
        self.nodes = {}
        self.root_node_id = None

        # 调用 LLMAdapter (抽象层) 获取节点列表
        try:
            node_list = LLMAdapter.generate_nodes(task_goal)
        except Exception as e:
            print(f"ERROR: LLMAdapter failed to generate nodes: {e}")
            return self
        
        if not node_list:
            print("Warning: LLM returned an empty plan.")
            return self
        
        for node in node_list:
            self.add_node(node)
            
        print(f"Plan generated successfully: {len(self.nodes)} nodes added.")
        return self
    
    # ... (可以添加 re_plan_with_llm 等方法用于重规划)

# -----------------------------------------------------------
# 示例用法 (作为独立的测试/演示 - 依赖 LLMAdapter 的实现)

if __name__ == '__main__':
    # 警告：此示例运行时，如果 LLMAdapter 返回空列表，则不会有任何节点被执行。
    initial_goal = TaskGoal(
        task_uuid=str(uuid.uuid4()),
        step_id="S001",
        target_description="Test planner execution.",
        required_data={'test_key': 'test_value'}
    )
    
    planner = DynamicExecutionGraph()
    planner.generate_initial_plan_with_llm(initial_goal)
    
    print("\n--- Plan Execution Simulation Start ---")
    next_node = planner.get_next_node_to_execute()
    
    if next_node:
        print(f"First node to execute: {next_node.node_id} (Tool: {next_node.action.tool_name})")
    else:
        print("Planner is empty. Please check LLMAdapter.generate_nodes implementation.")