import unittest
import os
import uuid
# *****************************************************************
# 修正点：确保同时导入 TaskGoal 和 ExecutionNode
from backend.src.data_models.decision_engine.decision_models import TaskGoal, ExecutionNode 
# *****************************************************************
from backend.src.services.LLMAdapter import LLMAdapter

# -------------------------------------------------------------------
# 辅助函数：创建用于测试的任务目标
# -------------------------------------------------------------------
def create_test_goal():
    """创建一个基础的 TaskGoal 实例用于测试。"""
    # 增加 Allowed Tools 字段，让 LLM 知道它可以做什么
    return TaskGoal(
        task_uuid=str(uuid.uuid4()),
        step_id="T_CONFIG_001",
        target_description="Test LLM configuration by generating a simple plan to navigate and login.",
        priority_level=1,
        max_execution_time_seconds=5,
        required_data={'test': 'config'},
        allowed_actions=['navigate_to', 'type_text', 'click_element', 'scroll', 'extract_data']
    )

class TestLLMConfiguration(unittest.TestCase):

    def test_01_api_key_loading(self):
        """测试 LLMAdapter 是否成功加载了 API Key。"""
        
        api_key = LLMAdapter.API_KEY
        
        self.assertIsNotNone(api_key, 
                             "FAIL: LLMAdapter.API_KEY 应该被加载，但它是 None。请检查 .env 文件和 load_dotenv()")
        self.assertTrue(len(api_key) > 10, 
                        "FAIL: API Key 看起来太短或为空。请检查 .env 文件中的 LLM_API_KEY 值。")
        print(f"\n[CONFIG CHECK] API Key Loaded: {'Success' if api_key else 'Failure'}")
        
    def test_02_model_name_loading(self):
        """测试 LLMAdapter 是否成功加载了模型名称。"""
        model_name = LLMAdapter.MODEL_NAME
        self.assertIsNotNone(model_name, 
                             "FAIL: LLMAdapter.MODEL_NAME 应该是被设置的。")
        self.assertTrue(len(model_name) > 2, 
                        "FAIL: Model Name 看起来不正确。请检查 .env 文件中的 LLM_MODEL_NAME 值。")
        print(f"[CONFIG CHECK] Model Name Loaded: {model_name}")

    def test_03_generate_nodes_success(self):
        """
        测试 LLMAdapter.generate_nodes 是否能够成功调用 AI 并返回节点列表。
        此测试会触发实际的 API 调用。
        """
        test_goal = create_test_goal()
        
        # 调用 generate_nodes，期望它能连接到 AI 并返回结构化的 ExecutionNode 列表
        node_list = LLMAdapter.generate_nodes(test_goal)
        
        # 期望返回的列表不为空
        self.assertGreater(len(node_list), 0,
                           "FAIL: LLMAdapter.generate_nodes 返回了空列表。这可能意味着：\n"
                           "1. API Key 无效或额度不足。\n"
                           "2. LLM 返回的 JSON 格式不正确，Pydantic 验证失败。\n"
                           "请检查网络连接和 LLM Adapter 的日志输出。")
        
        # 健壮性检查：检查返回的第一个节点是否是正确的类型
        self.assertIsInstance(node_list[0], ExecutionNode, 
                              "FAIL: 返回的元素不是 ExecutionNode 类型，JSON 解析或验证失败。")
        
        print(f"[LLM EXECUTION] Successfully generated {len(node_list)} nodes.")

# 运行测试
if __name__ == '__main__':
    unittest.main()