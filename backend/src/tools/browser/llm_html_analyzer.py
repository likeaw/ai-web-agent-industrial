"""
基于 LLM 的 HTML 内容分析工具。

将提取的 HTML 源码传给大模型，让 LLM 分析并提取用户需要的信息。
"""

import os
import requests
import json
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()


def analyze_html_with_llm(
    html_content: str,
    extraction_instruction: str,
    max_html_length: int = 50000,
) -> Dict[str, Any]:
    """
    使用 LLM 分析 HTML 内容并提取指定信息。
    
    :param html_content: HTML 源码字符串
    :param extraction_instruction: 提取指令，告诉 LLM 需要提取什么信息
    :param max_html_length: HTML 内容的最大长度（字符数），超过会截断
    :return: LLM 分析结果
    """
    api_key = os.getenv("LLM_API_KEY")
    model_name = os.getenv("LLM_MODEL_NAME", "deepseek-chat")
    api_url = os.getenv("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions")
    
    if not api_key:
        return {
            "success": False,
            "error": "LLM_API_KEY not configured"
        }
    
    # 截断过长的 HTML
    if len(html_content) > max_html_length:
        html_content = html_content[:max_html_length]
        print(f"[llm_html_analyzer] HTML content truncated to {max_html_length} characters")
    
    # 构造提示词
    system_prompt = (
        "你是一个专业的网页内容分析助手。你的任务是根据用户提供的 HTML 源码和提取指令，"
        "准确提取所需的信息。"
        "\n\n请仔细分析 HTML 结构，找出所有相关的链接、文本、数据等信息。"
        "\n\n返回 JSON 格式的结果，包含提取到的所有信息。"
    )
    
    user_prompt = f"""请分析以下 HTML 源码，并按照以下指令提取信息：

【提取指令】
{extraction_instruction}

【HTML 源码】
```html
{html_content}
```

请提取所有符合指令要求的信息，并以 JSON 格式返回。如果提取的是链接，格式应为：
{{
    "result_type": "link_list",
    "items": [
        {{"title": "链接标题", "url": "https://..."}},
        ...
    ]
}}

如果是其他类型的信息，请根据实际情况返回合适的 JSON 结构。"""
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        }
        
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=90
        )
        response.raise_for_status()
        
        response_data = response.json()
        content = response_data['choices'][0]['message']['content']
        
        # 解析 LLM 返回的 JSON
        try:
            result = json.loads(content)
            return {
                "success": True,
                "data": result
            }
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Failed to parse LLM response as JSON: {e}",
                "raw_response": content
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def extract_with_llm_analysis(
    html_content: str,
    task_description: str,
    max_html_length: int = 50000,
) -> List[Dict[str, str]]:
    """
    使用 LLM 分析 HTML 并提取可跳转的 URL（标题+URL 格式）。
    
    :param html_content: HTML 源码
    :param task_description: 任务描述，帮助 LLM 理解需要提取什么
    :param max_html_length: HTML 最大长度
    :return: 提取结果列表
    """
    extraction_instruction = (
        f"任务描述：{task_description}\n\n"
        "请提取页面中所有可以跳转的 URL 链接，格式为标题和 URL 的对应关系。"
        "忽略导航栏、页脚、广告等无关链接，重点关注主要内容区域的链接。"
    )
    
    result = analyze_html_with_llm(html_content, extraction_instruction, max_html_length)
    
    if not result.get("success"):
        print(f"[llm_html_analyzer] LLM analysis failed: {result.get('error')}")
        return []
    
    data = result.get("data", {})
    
    # 尝试从 LLM 返回结果中提取链接列表
    if "items" in data and isinstance(data["items"], list):
        return data["items"]
    elif "links" in data and isinstance(data["links"], list):
        return data["links"]
    else:
        # 如果 LLM 返回了其他格式，尝试解析
        print(f"[llm_html_analyzer] Unexpected LLM response format: {data}")
        return []

