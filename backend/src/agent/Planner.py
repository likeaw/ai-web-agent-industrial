# 文件: backend/src/agent/Planner.py (保持不变)

import uuid
import json 
import os 
from typing import List, Dict, Optional
from collections import deque
from backend.src.services.LLMAdapter import LLMAdapter 
from backend.src.data_models.decision_engine.decision_models import (
    ExecutionNode, ExecutionNodeStatus, TaskGoal, DecisionAction, WebObservation
)

class DynamicExecutionGraph:
    """动态执行图 (DEG) 管理器。"""
    
    def __init__(self):
        self.nodes: Dict[str, ExecutionNode] = {}
        self.root_node_id: Optional[str] = None
        self.nodes_execution_order: List[str] = []

    def add_node(self, node: ExecutionNode):
        """添加节点到图中，并维护父子关系和子节点优先级排序。"""
        if node.node_id in self.nodes:
            print(f"Warning: Node ID {node.node_id} already exists. Overwriting.")
        
        self.nodes[node.node_id] = node
        if node.node_id not in self.nodes_execution_order:
            self.nodes_execution_order.append(node.node_id)
        
        if node.parent_id is None:
            if self.root_node_id is not None and self.root_node_id != node.node_id:
                raise ValueError("Attempted to add a second root node to a non-empty graph.") 
            self.root_node_id = node.node_id
        
        if node.parent_id and node.parent_id in self.nodes:
            parent_node = self.nodes[node.parent_id]
            if node.node_id not in parent_node.child_ids:
                parent_node.child_ids.append(node.node_id)
            
            parent_node.child_ids = [
                child_id for child_id in parent_node.child_ids
                if child_id in self.nodes
            ]

            if parent_node.child_ids:
                parent_node.child_ids.sort(key=lambda id: self.nodes[id].execution_order_priority)

    def get_next_node_to_execute(self) -> Optional[ExecutionNode]:
        """核心：实现优先级驱动的深度优先遍历，找到下一个 PENDING 节点。"""
        if not self.root_node_id or self.root_node_id not in self.nodes:
            return None
        
        stack = deque([self.root_node_id])
        pending_nodes_by_priority: Dict[int, List[ExecutionNode]] = {}
        visited = set()
        
        while stack:
            node_id = stack.popleft()
            if node_id in visited:
                continue
            visited.add(node_id)
            
            node = self.nodes.get(node_id)
            if not node:
                continue

            if node.current_status == ExecutionNodeStatus.PENDING:
                if node.execution_order_priority not in pending_nodes_by_priority:
                    pending_nodes_by_priority[node.execution_order_priority] = []
                pending_nodes_by_priority[node.execution_order_priority].append(node)

            # 始终遍历整棵图（包括 FAILED/PRUNED 节点的子树），
            # 这样注入到失败节点之后的纠错计划也能被发现并执行。
            stack.extend(node.child_ids)


        if not pending_nodes_by_priority:
            return None
            
        highest_priority = min(pending_nodes_by_priority.keys())
        
        return pending_nodes_by_priority[highest_priority][0]


    def prune_on_failure(self, failed_node_id: str, reason: str):
        """失败时剔除节点及其所有子节点 (PRUNED 状态)。"""
        if failed_node_id not in self.nodes:
            return

        failed_node = self.nodes[failed_node_id]
        if failed_node.current_status != ExecutionNodeStatus.SUCCESS:
            failed_node.current_status = ExecutionNodeStatus.FAILED
            failed_node.failure_reason = reason

        to_prune_queue = deque(failed_node.child_ids)
        while to_prune_queue:
            prune_id = to_prune_queue.popleft()
            prune_node = self.nodes.get(prune_id)
            
            if prune_node and prune_node.current_status in [ExecutionNodeStatus.PENDING, ExecutionNodeStatus.SKIPPED]:
                prune_node.current_status = ExecutionNodeStatus.PRUNED
                prune_node.failure_reason = f"Pruned due to failure of ancestor node: {failed_node_id}"
                to_prune_queue.extend(prune_node.child_ids)

    # ----------------------------------------------------
    # 【修复 1 关键】：添加动态计划注入方法
    # ----------------------------------------------------
    def inject_correction_plan(self, failed_node_id: str, correction_plan_fragment: List[ExecutionNode]):
        """
        将 LLM 生成的纠正性计划片段注入到执行图中，实现动态重试。
        """
        if not correction_plan_fragment:
            print("[INJECT] LLM returned an empty correction plan. No nodes injected.")
            return

        failed_node = self.nodes.get(failed_node_id)
        if not failed_node:
            print(f"[ERROR] Failed node ID {failed_node_id} not found for correction.")
            return

        # 1. 找到所有直接依赖于失败节点的子节点 (Original Children)
        children_ids = [node.node_id for node in self.nodes.values() if node.parent_id == failed_node_id]

        # 2. 注入新节点：连接新计划的首尾
        
        # 将新计划的第一个节点连接到失败节点
        first_new_node = correction_plan_fragment[0]
        first_new_node.parent_id = failed_node_id 
        self.add_node(first_new_node)
        
        last_new_node = first_new_node

        # 依次连接新计划中的所有后续节点
        for i in range(1, len(correction_plan_fragment)):
            current_node = correction_plan_fragment[i]
            current_node.parent_id = last_new_node.node_id
            self.add_node(current_node)
            last_new_node = current_node
            
        # 3. 将失败节点的所有原始子节点连接到新计划的最后一个节点
        for child_id in children_ids:
            child_node = self.nodes.get(child_id)
            if child_node:
                # 原始子节点的父节点现在是新计划的最后一个节点
                child_node.parent_id = last_new_node.node_id
                print(f"[INJECT] Re-parented original child {child_id} to new node {last_new_node.node_id}.")
        
        # 4. 标记旧节点失败
        failed_node.current_status = ExecutionNodeStatus.FAILED
        print(f"[INJECT] Successfully injected {len(correction_plan_fragment)} nodes after {failed_node_id}. Graph updated.")

    def generate_initial_plan_with_llm(self, task_goal: TaskGoal, observation: Optional[WebObservation] = None):
        """
        调用 LLMAdapter 生成初始计划，并写入执行图。
        """
        node_candidates = LLMAdapter.generate_nodes(task_goal, observation)
        if not node_candidates:
            raise RuntimeError("LLM returned no execution nodes; cannot start plan.")

        # 重置现有图，确保是一次新的执行
        self.nodes.clear()
        self.nodes_execution_order.clear()
        self.root_node_id = None

        for node in node_candidates:
            self.add_node(node)

    def load_plan_from_json(self, file_path: str) -> 'DynamicExecutionGraph':
        # ... (保持不变) ...
        """
        从 JSON 文件加载 ExecutionNode 列表并构建图结构。
        此版本包含了对 Pydantic 必需字段的防御性初始化。
        """
        if not os.path.exists(file_path):
            print(f"ERROR: JSON plan file not found at {file_path}")
            return self

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
            raw_node_list = data.get("execution_plan", [])
            
            # 清空并重建执行顺序列表
            self.nodes_execution_order = [] 
            self.nodes = {} 

            for node_dict in raw_node_list:
                # 实例化 DecisionAction
                action_dict = node_dict.get('action', {})
                # ... (DecisionAction 实例化逻辑保持不变)
                action = DecisionAction(
                    tool_name=action_dict.get('tool_name', 'MISSING_TOOL'),
                    tool_args=action_dict.get('tool_args', {}),
                    on_failure_action=action_dict.get('on_failure_action', 'STOP'),
                    reasoning=action_dict.get('reasoning', 'Static test plan.'),
                    confidence_score=action_dict.get('confidence_score', 0.95),
                    expected_outcome=action_dict.get('expected_outcome', 'Expected static outcome.'),
                    max_attempts=action_dict.get('max_attempts', 1),
                    execution_timeout_seconds=action_dict.get('execution_timeout_seconds', 10),
                )

                # 实例化 ExecutionNode
                node = ExecutionNode(
                    node_id=node_dict['node_id'],
                    parent_id=node_dict.get('parent_id'),
                    action=action,
                    execution_order_priority=node_dict['execution_order_priority'],
                    current_status=ExecutionNodeStatus[node_dict.get('current_status', 'PENDING').upper()], 
                    child_ids=node_dict.get('child_ids', [])
                )
                
                self.add_node(node)
                # 确保 nodes_execution_order 包含所有节点 ID
                # self.add_node 内部已处理 self.nodes_execution_order.append(node.node_id)

        except Exception as e:
            print(f"ERROR: Failed to load plan from JSON. Details: {type(e).__name__}: {e}")
            print("请检查 JSON 结构是否与 ExecutionNode 和 DecisionAction 模型一致。")
            return self

        print(f"Plan loaded successfully from JSON: {len(self.nodes)} nodes added.")
        return self
    
if __name__ == '__main__':
    # 自测块 (保持不变)
    print("--- Planner.py Self-Test Start ---")
    # ... (保持不变)
    print("--- Planner.py Self-Test Finished ---")