# 文件: backend/src/services/LLMAdapter.py

import json
from typing import List, Dict, Any
from backend.src.data_models.decision_engine.decision_models import ExecutionNode, TaskGoal

class LLMAdapter:
    """
    大语言模型 (LLM) 服务适配器。
    这是一个抽象接口，负责与外部 LLM API 进行通信，
    并确保其输出严格符合 ExecutionNode 的 JSON Schema。
    """
    
    @staticmethod
    def _build_planning_prompt(task_goal: TaskGoal) -> str:
        """
        根据任务目标，构建用于请求 LLM 生成计划的Prompt。
        这是规划智能的关键部分。
        """
        # [TODO: 配置化 Prompt 工程]
        # 实际代码中，这会从配置文件或数据库中加载复杂的模板。
        
        prompt = (
            f"你是一个专业的网页自动化规划引擎。你的目标是：'{task_goal.target_description}'。\n"
            f"任务UUID: {task_goal.task_uuid}, 优先级: {task_goal.priority_level}。\n"
            f"可用工具集: {task_goal.allowed_actions}。\n"
            f"数据约束: {task_goal.required_data}\n\n"
            "请将任务分解为一系列 ExecutionNode 结构体，以 JSON 数组的形式输出。\n"
            "确保每个节点都包含 'execution_order_priority' 和 'parent_id' 来定义图结构。\n"
            "如果无法确定子节点，请返回根节点和下一个明确的步骤。"
        )
        return prompt

    @staticmethod
    def generate_nodes(task_goal: TaskGoal) -> List[ExecutionNode]:
        """
        调用 LLM API，生成初始计划或重规划的 ExecutionNode 列表。
        
        !!! 注意: 在此演示中，我们必须返回一个合法的 List[ExecutionNode]。
        由于无法调用外部 API，我们返回一个严格遵循 JSON Schema 的空列表。
        您需要用实际的 API 调用替换 'json.loads' 部分。
        """
        prompt = LLMAdapter._build_planning_prompt(task_goal)
        
        # [TODO: 实际 API 调用集成点]
        # 实际代码会是: 
        # llm_raw_response = external_llm_client.call(prompt, output_schema=ExecutionNode_Schema)
        # ----------------------------------------------------------------------------------
        
        # *** 严格无硬编码的占位符 ***
        # 假设 LLM 返回的 JSON 列表是空的，直到您实现 API 调用
        llm_json_output = "[]" 
        # ---------------------------
        
        # Pydantic 严格验证和解析 JSON
        raw_node_data: List[Dict[str, Any]] = json.loads(llm_json_output)
        
        nodes = []
        for data in raw_node_data:
            # 使用 model_validate 严格验证结构
            nodes.append(ExecutionNode.model_validate(data))
            
        return nodes