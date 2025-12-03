# 文件: backend/src/services/LLMAdapter.py

import os
import requests 
import json
from dotenv import load_dotenv
from typing import List, Optional, Dict, Any
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
    def _create_api_payload(
        goal: TaskGoal, 
        observation: Optional[WebObservation], 
        json_schema: dict,
        failed_node_history: Optional[List[Dict[str, Any]]] = None,
    ) -> dict:
        """
        构造发送给 LLM API 的请求 Payload。
        
        :param goal: 任务目标
        :param observation: 当前观测
        :param json_schema: JSON Schema
        :param failed_node_history: 失败的节点历史，用于避免重复生成相同错误
        """
        schema_text = json.dumps(json_schema, indent=2)
        
        # 【规划原则】：说明各工具的关键参数约束，帮助 LLM 正确调用。
        planning_principle = (
            "【规划原则】: "
            "1. type_text 和 click_element 工具**必须**在 tool_args 中提供一个有效的 'selector' 或 'xpath' 字符串来定位元素；"
            "   对于 type_text，如果指定了 submit_key='Enter'，则不必紧接着执行 click_element 来点击提交按钮。"
            "2. 对于复杂的、需要动态定位的点击（如搜索结果链接），可以使用 on_failure_action: 'RE_EVALUATE' 让 Agent 自我纠错。"
            "3. 当用户要求记录或整理信息时，可以调用 open_notepad 工具，tool_args 支持 file_path(可选) 和 initial_content(可选)。"
            "4. 当需要保存当前页面截图时，请使用 take_screenshot，tool_args 至少包含 task_topic(字符串)。"
            "   如需自定义保存位置，提供 output_path(字符串，完整路径，可包含'桌面'等中文描述) 或 output_dir(字符串，目录路径)＋filename；未指定时默认保存到 temp/screenshots。"
            "5. 当需要点击搜索结果或重复元素列表中的第 N 个元素时，请使用 click_nth，tool_args 中包含 selector/xpath/text_content 以及 index(从0开始)。"
            "6. 当需要按文本模糊匹配链接时，请使用 find_link_by_text，tool_args 中包含 keyword(字符串) 和可选 limit(整数，默认5)。"
            "7. 当需要保存当前页面 HTML 源码时，请使用 download_page，tool_args 中包含 task_topic(字符串，用于生成文件名)。"
            "8. 当需要下载链接中的内容时，请使用 download_link，tool_args 可以包含 url(直接下载) 或 selector/xpath/text_content(从页面元素读取 href)，以及 task_topic(字符串)。"
            "9. 【重要】当需要提取页面内容（特别是提取可跳转的 URL）时，extract_data 工具现在支持多种提取模式："
            "   - mode='comprehensive'（推荐，默认）：综合策略，先使用 LLM 分析 HTML，如果失败则回退到高级提取。"
            "      会自动展开折叠内容、触发懒加载等，模拟人类操作，适用于所有场景，特别是防爬网站。"
            "   - mode='llm' 或 use_llm=true：将 HTML 源码传给大模型分析，让 LLM 智能识别和提取所需内容。"
            "   - mode='advanced'：使用高级提取，提取所有链接和页面元素。"
            "   - mode='simple'：使用简单的选择器提取，适用于结构简单的页面。"
            "   默认会启用 prepare_page=true，自动展开折叠内容、触发懒加载、等待内容加载完成。"
            "   可以设置 extraction_instruction（字符串）来指导 LLM 提取什么内容，例如："
            "      '提取页面中所有可以跳转的 URL 链接，忽略导航栏和页脚链接，重点关注主要内容区域'。"
            "   推荐：对于'提取当前页面中可以跳转的url'这类任务，使用 mode='comprehensive'，"
            "   这样系统会智能地处理防爬机制、展开内容，并使用 LLM 提取最准确的结果。"
            "10. 【系统操作工具】当用户要求创建文件夹、删除文件、列出目录、读取/写入文件时，可以使用以下工具："
            "   - create_directory: 创建目录，tool_args 包含 path(字符串，目录路径)。"
            "   - delete_file_or_directory: 删除文件或目录，tool_args 包含 path(字符串) 和 recursive(布尔，是否递归删除目录，默认False)。"
            "   - list_directory: 列出目录内容，tool_args 包含 path(字符串，默认'.') 和 show_hidden(布尔，是否显示隐藏文件，默认False)。"
            "   - read_file_content: 读取文件内容，tool_args 包含 path(字符串) 和 max_size(整数，最大文件大小字节，默认1MB)。"
            "   - write_file_content: 写入文件内容，tool_args 包含 path(字符串)、content(字符串) 和 append(布尔，是否追加模式，默认False)。"
            "   注意：系统操作允许访问整个系统（如桌面、用户目录等），但会保护系统关键目录（如 C:\\Windows）。"
            "   删除操作和覆盖写入操作需要用户确认（项目内 temp/ 和 logs/ 目录的删除除外）。"
            "11. 【Office 文档工具】当用户要求创建 Microsoft Office 文档时，可以使用以下工具："
            "   - create_word_document: 创建 Word 文档(.docx)，tool_args 包含 path(字符串，文件路径，应包含.docx扩展名)、content(字符串，可选，文档内容，支持多行)、title(字符串，可选，文档标题)。"
            "   - create_excel_document: 创建 Excel 文档(.xlsx)，tool_args 包含 path(字符串，文件路径)、data(二维列表，可选，数据行，例如[[\"A1\",\"B1\"],[\"A2\",\"B2\"]])、sheet_name(字符串，可选，工作表名称，默认\"Sheet1\")、headers(字符串列表，可选，表头，例如[\"姓名\",\"年龄\"])。"
            "   - create_powerpoint_document: 创建 PowerPoint 演示文稿(.pptx)，tool_args 包含 path(字符串，文件路径)、slides(字典列表，可选，每张幻灯片包含\"title\"和\"content\"字段)、title(字符串，可选，演示文稿标题)。"
            "   - create_office_document: 通用 Office 文档创建函数，tool_args 包含 file_type(字符串，\"docx\"、\"xlsx\"或\"pptx\")、path(字符串，文件路径)以及其他相应类型的参数。"
            "   注意：创建 Office 文档需要安装相应的 Python 库：python-docx(Word)、openpyxl(Excel)、python-pptx(PowerPoint)。如果覆盖已存在的文件，需要用户确认。"
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
        
        # 2. 构造用户消息 (包含当前状态和失败历史)
        observation_json = observation.model_dump_json(indent=2) if observation else "Initial state (No prior observation)."
        
        failed_history_text = ""
        if failed_node_history:
            failed_history_text = "\n\n【⚠️ 重要：失败的节点历史】\n"
            failed_history_text += "以下节点之前尝试过但失败了，请避免生成相同或类似的错误节点：\n"
            for idx, failed_node in enumerate(failed_node_history, 1):
                failed_history_text += f"\n{idx}. 失败节点 ID: {failed_node.get('node_id', 'unknown')}\n"
                failed_history_text += f"   工具: {failed_node.get('tool_name', 'unknown')}\n"
                failed_history_text += f"   参数: {json.dumps(failed_node.get('tool_args', {}), ensure_ascii=False)}\n"
                failed_history_text += f"   错误信息: {failed_node.get('error_message', 'unknown')}\n"
            failed_history_text += "\n请确保新生成的节点与上述失败的节点不同，尝试使用不同的方法或参数。\n"
        
        user_message = (
            f"Goal ID: {goal.task_uuid}\n"
            f"Current Web Observation:\n{observation_json}\n"
            f"{failed_history_text}\n"
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
    def generate_nodes(
        goal: TaskGoal, 
        observation: Optional[WebObservation] = None,
        failed_node_history: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ExecutionNode]:
        """
        根据任务目标和当前观测结果，调用 LLM API 生成 ExecutionNode 列表。
        
        :param goal: 任务目标
        :param observation: 当前观测结果
        :param failed_node_history: 失败的节点历史，用于避免重复生成相同错误
        """
        if not LLMAdapter.API_KEY:
            # 如果没有密钥，则返回一个硬编码的、但能通过验证的空列表
            print("ERROR: LLM API Key missing. Cannot generate dynamic plan.")
            return []
            
        json_schema = LLMAdapter._create_json_schema()
        payload = LLMAdapter._create_api_payload(goal, observation, json_schema, failed_node_history)
        
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