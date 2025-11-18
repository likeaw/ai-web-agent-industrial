# 文件: backend/src/services/LLMAdapter.py

import os
import requests 
import json
from dotenv import load_dotenv
from typing import List, Optional
from backend.src.data_models.decision_engine.decision_models import (
    TaskGoal, ExecutionNode, WebObservation
)

# ----------------------------------------------------
# 1. 配置加载 (Initialization)
# ----------------------------------------------------

# 加载 .env 文件中的环境变量
load_dotenv() 

class LLMAdapter:
    """
    LLM 适配器。
    负责处理所有与 LLM API 相关的交互，包括：
    1. 读取 API 密钥和 URL。
    2. 将 Python 数据模型转换为 LLM 提示 (Prompt)。
    3. 解析 LLM 返回的 JSON 结构化数据为 ExecutionNode 列表。
    """
    
    API_KEY = os.getenv("LLM_API_KEY")
    MODEL_NAME = os.getenv("LLM_MODEL_NAME", "deepseek-chat")
    # 从 .env 文件中获取 API URL，默认为 DeepSeek 的官方端点
    API_URL = os.getenv("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions") 

    if not API_KEY:
        print("WARNING: LLM_API_KEY is not set in environment variables. Execution will fail.")

    @staticmethod
    def _create_json_schema() -> dict:
        """
        动态生成 LLM 必须遵循的 JSON Schema，要求返回 ExecutionNode 列表。
        """
        # 使用 Pydantic 的内置方法生成 ExecutionNode 的 JSON Schema
        node_schema = ExecutionNode.model_json_schema()
        
        # 封装成一个包含 execution_plan 数组的顶层对象
        schema = {
            "type": "object",
            "properties": {
                "execution_plan": {
                    "type": "array",
                    "description": "A list of structured execution nodes. The first node must be the root (parent_id: null).",
                    "items": node_schema
                }
            },
            "required": ["execution_plan"]
        }
        return schema

    @staticmethod
    def _create_api_payload(goal: TaskGoal, observation: Optional[WebObservation], json_schema: dict) -> dict:
        """
        构造发送给 LLM API 的请求 Payload。
        """
        # 1. 构造系统角色和约束
        schema_text = json.dumps(json_schema, indent=2)
        system_prompt = (
            "You are the core planning engine for an industrial Web Agent. "
            "Your task is to generate a structured execution plan (ExecutionNode list) based on the goal and current observation.\n"
            "【Output Constraint】: You MUST strictly adhere to the provided JSON Schema, returning a single JSON object with the 'execution_plan' array. Do not output any prose or extra text.\n"
            f"Allowed Tools: {goal.allowed_actions}\n"
            f"Goal: {goal.target_description}\n\n"
            f"【JSON Schema Constraint】:\n{schema_text}"
        )
        
        # 2. 构造用户消息 (包含当前状态)
        observation_json = observation.model_dump_json(indent=2) if observation else "Initial state (No prior observation)."
        user_message = (
            f"Goal ID: {goal.task_uuid}\n"
            f"Current Web Observation:\n{observation_json}\n\n"
            "Generate the complete sequence of steps (ExecutionNode list) required to fulfill the task goal, prioritizing essential actions."
        )

        # 3. 构造请求体
        payload = {
            "model": LLMAdapter.MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            # 强制要求 JSON 输出格式
            "response_format": {"type": "json_object"}, 
            "temperature": 0.0, 
        }
        
        return payload

    @staticmethod
    def generate_nodes(goal: TaskGoal, observation: Optional[WebObservation] = None) -> List[ExecutionNode]:
        """
        根据任务目标和当前观测结果，调用 LLM API 生成 ExecutionNode 列表。
        """
        if not LLMAdapter.API_KEY:
            return []
            
        print(f"--- Calling LLM ({LLMAdapter.MODEL_NAME}) at URL: {LLMAdapter.API_URL} ---")
        
        json_schema = LLMAdapter._create_json_schema()
        payload = LLMAdapter._create_api_payload(goal, observation, json_schema)
        
        # *********** DEBUG 日志输出 (打印请求 Payload) ***********
        print("--- DEBUG: Full Request Payload (for debugging JSON Schema) ---")
        payload_str = json.dumps(payload, indent=2, ensure_ascii=False)
        print(payload_str[:500] + "..." if len(payload_str) > 500 else payload_str)
        print("-----------------------------------------------------------------")
        # ***************************************************************
        
        headers = {
            "Authorization": f"Bearer {LLMAdapter.API_KEY}",
            "Content-Type": "application/json"
        }

        # 2. 发起 API 调用
        try:
            # *********** 修正点：将超时时间设置为 90 秒 ***********
            TIMEOUT_SECONDS = 90
            response = requests.post(
                LLMAdapter.API_URL, 
                headers=headers, 
                json=payload, 
                timeout=TIMEOUT_SECONDS  
            )
            response.raise_for_status() # 检查 HTTP 错误 (4xx, 5xx)

            response_data = response.json()
            
            # 3. 解析 LLM 返回的 JSON
            json_content = response_data['choices'][0]['message']['content']
            
            # 4. JSON Decode
            llm_output = json.loads(json_content)
            raw_node_list = llm_output.get("execution_plan", [])
            
            if not raw_node_list:
                 raise ValueError("LLM returned empty or missing 'execution_plan' array.")
            
            # 5. Pydantic 严格验证和实例化
            node_list: List[ExecutionNode] = [
                ExecutionNode.model_validate(data) for data in raw_node_list
            ]
            
            return node_list

        except requests.exceptions.HTTPError as e:
            print(f"API Request FAILED (HTTP Error {e.response.status_code}): {e}")
            try:
                error_details = e.response.json()
                print(f"ERROR DETAILS (from API): {json.dumps(error_details, indent=2)}")
            except:
                print("ERROR DETAILS: API did not return valid JSON response.")
            return []

        except requests.exceptions.RequestException as e:
            print(f"API Request FAILED (Network/Connection Error): {e}")
            return []
            
        except (KeyError, json.JSONDecodeError, ValueError) as e:
            # LLM 返回了 JSON 但格式错误或 Pydantic 验证失败
            print(f"API Response Parsing FAILED (LLM output format error/Pydantic validation): {e}")
            
            # 打印调试信息：原始响应内容和用于约束的 Schema
            try:
                # 尝试获取完整的响应文本
                print(f"DEBUG: Raw LLM response content: {response.text}")
            except:
                pass
            print(f"DEBUG: Payload JSON Schema was enforced: {json.dumps(json_schema, indent=2)}")
            return []