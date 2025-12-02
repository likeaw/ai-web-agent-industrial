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

load_dotenv() 

class LLMAdapter:
    
    API_KEY = os.getenv("LLM_API_KEY")
    MODEL_NAME = os.getenv("LLM_MODEL_NAME", "deepseek-chat")
    API_URL = os.getenv("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions") 

    if not API_KEY:
        print("WARNING: LLM_API_KEY is not set in environment variables. Execution will fail.")

    @staticmethod
    def _create_json_schema() -> dict:
        """动态生成 LLM 必须遵循的 JSON Schema。"""
        node_schema = ExecutionNode.model_json_schema()
        
        schema = {
            "type": "object",
            "properties": {
                "execution_plan": {
                    "type": "array",
                    "description": "A list of structured execution nodes.",
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
        schema_text = json.dumps(json_schema, indent=2)
        
        # 【规划原则】：说明各工具的关键参数约束，帮助 LLM 正确调用。
        planning_principle = (
            "【规划原则】: "
            "1. type_text 和 click_element 工具**必须**在 tool_args 中提供一个有效的 'selector' 或 'xpath' 字符串来定位元素；"
            "   对于 type_text，如果指定了 submit_key='Enter'，则不必紧接着执行 click_element 来点击提交按钮。"
            "2. 对于复杂的、需要动态定位的点击（如搜索结果链接），可以使用 on_failure_action: 'RE_EVALUATE' 让 Agent 自我纠错。"
            "3. 当用户要求记录或整理信息时，可以调用 open_notepad 工具，tool_args 支持 file_path(可选) 和 initial_content(可选)。"
            "4. 当需要保存当前页面截图时，请使用 take_screenshot，tool_args 至少包含 task_topic(字符串)，可选 filename 和 full_page(bool)。"
            "5. 当需要点击搜索结果或重复元素列表中的第 N 个元素时，请使用 click_nth，tool_args 中包含 selector/xpath/text_content 以及 index(从0开始)。"
            "6. 当需要按文本模糊匹配链接时，请使用 find_link_by_text，tool_args 中包含 keyword(字符串) 和可选 limit(整数，默认5)。"
            "7. 当需要保存当前页面 HTML 源码时，请使用 download_page，tool_args 中包含 task_topic(字符串，用于生成文件名)。"
            "8. 当需要下载链接中的内容时，请使用 download_link，tool_args 可以包含 url(直接下载) 或 selector/xpath/text_content(从页面元素读取 href)，以及 task_topic(字符串)。"
        )

        system_prompt = (
            "You are the core planning engine for an industrial Web Agent. "
            "Your task is to generate a structured execution plan (ExecutionNode list) based on the goal and current observation.\n"
            "【Output Constraint】: You MUST strictly adhere to the provided JSON Schema, returning a single JSON object with the 'execution_plan' array. Do not output any prose or extra text.\n"
            f"Allowed Tools: {goal.allowed_actions}\n"
            f"Goal: {goal.target_description}\n\n"
            f"{planning_principle}\n\n"
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
            # 如果没有密钥，则返回一个硬编码的、但能通过验证的空列表
            print("ERROR: LLM API Key missing. Cannot generate dynamic plan.")
            return []
            
        json_schema = LLMAdapter._create_json_schema()
        payload = LLMAdapter._create_api_payload(goal, observation, json_schema)
        
        headers = {
            "Authorization": f"Bearer {LLMAdapter.API_KEY}",
            "Content-Type": "application/json"
        }

        # 2. 发起 API 调用
        try:
            TIMEOUT_SECONDS = 90
            response = requests.post(
                LLMAdapter.API_URL, 
                headers=headers, 
                json=payload, 
                timeout=TIMEOUT_SECONDS  
            )
            response.raise_for_status() 

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
            # ... (错误处理保持不变)
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
            # ... (错误处理保持不变)
            print(f"API Response Parsing FAILED (LLM output format error/Pydantic validation): {e}")
            return []