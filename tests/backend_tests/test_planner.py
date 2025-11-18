# 文件: tests/backend_tests/test_planner.py

import unittest
import json
import os
import uuid
from typing import List
from backend.src.agent.Planner import DynamicExecutionGraph 
from backend.src.data_models.decision_engine.decision_models import (
    ExecutionNode, ExecutionNodeStatus
)

# 获取当前文件路径，用于定位测试数据
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DATA_PATH = os.path.join(CURRENT_DIR, "test_data", "complex_deg_scenario.json")


def load_deg_from_json(json_path: str, graph: DynamicExecutionGraph):
    """
    加载 JSON 文件，并构建 DynamicExecutionGraph。
    """
    print(f"\n--- DEBUG: Loading test scenario from: {json_path} ---")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    nodes_to_add: List[ExecutionNode] = []
    
    # 1. 严格解析 JSON 数据为 Pydantic ExecutionNode 对象
    for node_data in data:
        try:
            # 使用 model_validate 严格校验 JSON 格式
            node = ExecutionNode.model_validate(node_data)
            nodes_to_add.append(node)
        except Exception as e:
            raise ValueError(f"Failed to validate JSON node {node_data.get('node_id', 'Unknown')}: {e}")

    # 2. 将节点按顺序添加到图中
    for node in nodes_to_add:
        graph.add_node(node)
        print(f"DEBUG: Added Node {node.node_id} (P{node.execution_order_priority}, Parent: {node.parent_id})")
        
    return graph

class TestDynamicExecutionGraph(unittest.TestCase):
    
    def setUp(self):
        """为每个测试用例加载复杂的 DEG 结构"""
        self.graph = DynamicExecutionGraph()
        self.graph = load_deg_from_json(TEST_DATA_PATH, self.graph)
        
        # 预期的图结构验证： N0 的子节点应按优先级排序
        # N0 -> [N1 (P5), N2 (P20)]
        self.assertEqual(self.graph.nodes["N0"].child_ids, ["N1", "N2"])
        
    def _execute_and_assert(self, expected_id, new_status=ExecutionNodeStatus.SUCCESS, failure_reason=None):
        """执行下一个节点并验证结果，输出详细信息。"""
        next_node = self.graph.get_next_node_to_execute()
        
        # 详细信息输出
        print(f"\n[EXECUTION STEP] Expected Node: {expected_id}")
        if next_node:
            print(f"   -> Actual Node: {next_node.node_id} (P{next_node.execution_order_priority})")
        else:
            print("   -> Actual Node: None (Plan Completed or Halted)")
            
        self.assertIsNotNone(next_node, f"Expected node {expected_id} but graph returned None.")
        self.assertEqual(next_node.node_id, expected_id, f"Traversal error: Expected {expected_id} but got {next_node.node_id}.")
        
        # 更新状态
        if new_status == ExecutionNodeStatus.FAILED:
            # 只有在调用 _execute_and_assert 时传入 FAILED 状态，才调用剪枝逻辑
            self.graph.prune_on_failure(next_node.node_id, failure_reason or "Simulated Failure")
            next_node.current_status = ExecutionNodeStatus.FAILED # 确保节点状态被更新
        else:
            next_node.current_status = new_status


    def test_01_json_traversal_and_priority(self):
        """测试 JSON 加载的图是否遵循优先级和遍历顺序。（优先级+深度）"""
        
        # 正确的预期执行顺序：N0 -> N1 -> N3 -> N4 -> N6 -> N5 -> N2
        
        # 1. N0 (L1)
        self._execute_and_assert("N0")
        
        # 2. N1 (L2 - P5)
        self._execute_and_assert("N1")
        
        # 3. N3 (L3 - P6)
        self._execute_and_assert("N3")

        # 4. N4 (L4 - P1)
        self._execute_and_assert("N4")

        # 5. N6 (L5 - P7) - N4的子节点，深度优先进入
        self._execute_and_assert("N6") 

        # 6. N5 (L4 - P10) - 回溯到 N3，发现未执行的 N5
        self._execute_and_assert("N5")

        # 7. N2 (L2 - P20) - 回溯到 N0，发现未执行的 N2
        self._execute_and_assert("N2")
        
        # 8. 图已完成
        self.assertIsNone(self.graph.get_next_node_to_execute(), "Graph should be empty after all nodes succeed.")


    def test_02_prune_mid_traversal(self):
        """测试在执行中间路径失败时，剪枝和重新遍历是否正确。"""
        
        # 1. N0 成功
        self._execute_and_assert("N0")
        
        # 2. N1 成功 (进入高优先级路径)
        self._execute_and_assert("N1")
        
        # 3. N3 失败 (N3 失败将导致 N4, N5, N6 被剪枝)
        self._execute_and_assert("N3", new_status=ExecutionNodeStatus.FAILED, failure_reason="Login attempt failed.")
        
        # 验证 N4, N5, N6 是否被剪枝 (PRUNED)
        self.assertEqual(self.graph.nodes["N4"].current_status, ExecutionNodeStatus.PRUNED, "N4 must be PRUNED after N3 failure.")
        self.assertEqual(self.graph.nodes["N5"].current_status, ExecutionNodeStatus.PRUNED, "N5 must be PRUNED after N3 failure.")
        self.assertEqual(self.graph.nodes["N6"].current_status, ExecutionNodeStatus.PRUNED, "N6 must be PRUNED after N3 failure.")
        
        # 4. 重新遍历：失败路径 (N3, N4, N5, N6) 被剔除。应该回溯到 N0，并选择下一个 PENDING 子节点 N2。
        self._execute_and_assert("N2", new_status=ExecutionNodeStatus.SUCCESS)

        # 5. 最终检查
        self.assertIsNone(self.graph.get_next_node_to_execute(), "Plan should be completed (N0, N1, N2 succeeded; N3 failed, others pruned).")


# 运行测试
if __name__ == '__main__':
    # 确保测试数据文件存在
    if not os.path.exists(TEST_DATA_PATH):
        print(f"\nFATAL ERROR: Test data file not found at {TEST_DATA_PATH}")
        print("Please create the complex_deg_scenario.json file as described.")
    else:
        # 注意: 确保在项目根目录运行 python -m unittest tests.backend_tests.test_planner
        unittest.main()