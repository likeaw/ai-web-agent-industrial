# 文件: backend/src/agent/Planner.py

import uuid
import json # <-- 新增：用于 JSON 加载
import os # <-- 新增：用于文件路径检查
from typing import List, Dict, Optional
from collections import deque
from backend.src.services.LLMAdapter import LLMAdapter 
from backend.src.data_models.decision_engine.decision_models import (
    ExecutionNode, ExecutionNodeStatus, TaskGoal, DecisionAction
)

class DynamicExecutionGraph:
    """动态执行图 (DEG) 管理器。"""
    
    def __init__(self):
        self.nodes: Dict[str, ExecutionNode] = {}
        self.root_node_id: Optional[str] = None

    def add_node(self, node: ExecutionNode):
        """添加节点到图中，并维护父子关系和子节点优先级排序。"""
        if node.node_id in self.nodes:
            print(f"Warning: Node ID {node.node_id} already exists. Overwriting.")
        
        self.nodes[node.node_id] = node
        
        if node.parent_id is None:
            if self.root_node_id is not None and self.root_node_id != node.node_id:
                raise ValueError("Attempted to add a second root node to a non-empty graph.") 
            self.root_node_id = node.node_id
        
        if node.parent_id and node.parent_id in self.nodes:
            parent_node = self.nodes[node.parent_id]
            if node.node_id not in parent_node.child_ids:
                parent_node.child_ids.append(node.node_id)
            
            # 过滤掉不存在的节点 ID，防止 KeyError
            parent_node.child_ids = [
                child_id for child_id in parent_node.child_ids
                if child_id in self.nodes
            ]

            # 排序
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
                
            if node.current_status == ExecutionNodeStatus.SUCCESS:
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
            
            
    def generate_initial_plan_with_llm(self, task_goal: TaskGoal) -> 'DynamicExecutionGraph':
        """调用 LLMAdapter 获取 ExecutionNode 列表，并构建图。"""
        print(f"--- [LLM Planning] Calling LLM to generate plan for {task_goal.task_uuid} ---")
        
        self.nodes = {}
        self.root_node_id = None

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

    def load_plan_from_json(self, json_file_path: str) -> 'DynamicExecutionGraph':
        """
        从 JSON 文件加载 ExecutionNode 列表并构建图结构。
        此版本包含了对 Pydantic 必需字段的防御性初始化。
        """
        if not os.path.exists(json_file_path):
            print(f"ERROR: JSON plan file not found at {json_file_path}")
            return self

        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"ERROR: Failed to decode JSON file. Details: {e}")
            return self

        self.nodes = {}
        self.root_node_id = None

        try:
            plan_data = data.get('execution_plan', [])
            
            for node_dict in plan_data:
                # 1. 创建 DecisionAction
                action_dict = node_dict.get('action', {})
                
                # --- 防御性初始化所有可能的必需字段 ---
                # 确保所有必需字段都有一个合理的默认值，以通过 Pydantic 验证
                action = DecisionAction(
                    # 核心字段
                    tool_name=action_dict.get('tool_name', 'default_tool'),
                    tool_args=action_dict.get('tool_args', {}),
                    on_failure_action=action_dict.get('on_failure_action', 'STOP'),
                    
                    # LLM生成元数据 (根据报错信息推断)
                    reasoning=action_dict.get('reasoning', 'Static test plan.'),
                    confidence_score=action_dict.get('confidence_score', 0.95),
                    expected_outcome=action_dict.get('expected_outcome', 'Expected static outcome.'),

                    # 其他潜在的必需字段 (根据您的 C++ 头文件和其他常见模型推断)
                    # 如果 DecisionAction 模型中还有其他必需字段，请在这里添加默认值
                    # 例如，如果 max_attempts 是必需的 int 字段
                    max_attempts=action_dict.get('max_attempts', 1),
                    execution_timeout_seconds=action_dict.get('execution_timeout_seconds', 10),
                    
                    # 补充：如果有其他必需字段，也应在此初始化
                    # (请根据您实际的 Python 模型定义进行检查和补充)
                )

                # 2. 创建 ExecutionNode
                node = ExecutionNode(
                    node_id=node_dict['node_id'],
                    parent_id=node_dict.get('parent_id'),
                    action=action,
                    execution_order_priority=node_dict['execution_order_priority'],
                    # 确保状态从字符串正确映射到枚举
                    current_status=ExecutionNodeStatus[node_dict.get('current_status', 'PENDING').upper()], # 确保大写
                    child_ids=node_dict.get('child_ids', [])
                    # ... 确保其他 ExecutionNode 字段也被映射 ...
                )
                
                self.add_node(node)
                
        except Exception as e:
            # 打印更详细的错误类型，以方便调试
            print(f"ERROR: Failed to load plan from JSON. Details: {type(e).__name__}: {e}")
            print("请检查 JSON 结构是否与 ExecutionNode 和 DecisionAction 模型一致。")
            return self

        print(f"Plan loaded successfully from JSON: {len(self.nodes)} nodes added.")
        return self
    
if __name__ == '__main__':
    # 恢复符合工业要求的 Planner 模块自测块，用于快速验证图逻辑
    print("--- Planner.py Self-Test Start ---")
    
    planner = DynamicExecutionGraph()
    
    # 1. 测试节点添加和优先级排序
    root_node = ExecutionNode(
        node_id="ROOT", parent_id=None, execution_order_priority=1, current_status=ExecutionNodeStatus.PENDING,
        action=DecisionAction(tool_name="navigate", tool_args={}, on_failure_action="STOP")
    )
    planner.add_node(root_node)
    
    child_b = ExecutionNode(
        node_id="B", parent_id="ROOT", execution_order_priority=2, current_status=ExecutionNodeStatus.PENDING,
        action=DecisionAction(tool_name="type", tool_args={}, on_failure_action="STOP")
    )
    planner.add_node(child_b)
    
    child_a = ExecutionNode(
        node_id="A", parent_id="ROOT", execution_order_priority=1, current_status=ExecutionNodeStatus.PENDING,
        action=DecisionAction(tool_name="click", tool_args={}, on_failure_action="STOP")
    )
    planner.add_node(child_a)

    print(f"Graph initialized with {len(planner.nodes)} nodes.")
    # 预期: A (P1) 在 B (P2) 之前
    print(f"Root node children (Prio 1, 2): {planner.nodes['ROOT'].child_ids}")
    
    # 2. 测试遍历和剪枝
    print("Simulating execution: ROOT SUCCESS")
    planner.nodes["ROOT"].current_status = ExecutionNodeStatus.SUCCESS
    
    next_node = planner.get_next_node_to_execute() # 预期: A
    print(f"Next node to execute: {next_node.node_id if next_node else 'None'}")
    
    print("--- Planner.py Self-Test Finished ---")