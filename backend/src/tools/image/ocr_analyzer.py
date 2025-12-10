"""
OCR 结果分析工具。

将 OCR 识别出的文本内容传给 LLM 进行关键词提取、内容分析等处理。
"""

import os
import json
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()


def analyze_ocr_text_with_llm(
    ocr_text: str,
    analysis_instruction: str,
    max_text_length: int = 10000,
) -> Dict[str, Any]:
    """
    使用 LLM 分析 OCR 识别出的文本内容。
    
    适用于：
    - 关键词提取
    - 内容摘要
    - 结构化信息提取
    - 情感分析等
    
    :param ocr_text: OCR 识别出的文本内容
    :param analysis_instruction: 分析指令，告诉 LLM 需要做什么分析
    :param max_text_length: 文本内容的最大长度（字符数），超过会截断
    :return: LLM 分析结果
    """
    import requests
    
    api_key = os.getenv("LLM_API_KEY")
    model_name = os.getenv("LLM_MODEL_NAME", "deepseek-chat")
    api_url = os.getenv("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions")
    
    if not api_key:
        return {
            "success": False,
            "error": "LLM_API_KEY not configured"
        }
    
    # 截断过长的文本
    if len(ocr_text) > max_text_length:
        ocr_text = ocr_text[:max_text_length]
        print(f"[ocr_analyzer] OCR text truncated to {max_text_length} characters")
    
    # 构造提示词
    system_prompt = (
        "你是一个专业的文本分析助手。你的任务是根据用户提供的 OCR 识别文本和分析指令，"
        "准确提取所需的信息或进行相应的分析。"
        "\n\n请仔细分析文本内容，提取关键词、摘要、结构化信息等。"
        "\n\n返回 JSON 格式的结果，包含提取到的所有信息。"
    )
    
    user_prompt = f"""请分析以下 OCR 识别出的文本内容，并按照以下指令进行处理：

【分析指令】
{analysis_instruction}

【OCR 识别文本】
```
{ocr_text}
```

请根据指令提取或分析信息，并以 JSON 格式返回结果。例如，如果是关键词提取，格式应为：
{{
    "keywords": ["关键词1", "关键词2", ...],
    "summary": "内容摘要",
    "main_topics": ["主题1", "主题2", ...]
}}

如果是其他类型的分析，请根据实际情况返回合适的 JSON 结构。"""
    
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
                "data": result,
                "original_text": ocr_text[:500]  # 保留原始文本的前500字符作为参考
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


def extract_keywords_from_ocr(
    ocr_text: str,
    max_keywords: int = 10,
    language: str = "zh",
) -> Dict[str, Any]:
    """
    从 OCR 文本中提取关键词。
    
    :param ocr_text: OCR 识别出的文本内容
    :param max_keywords: 最大关键词数量
    :param language: 文本语言（zh=中文，en=英文）
    :return: 关键词提取结果
    """
    if language == "zh":
        instruction = (
            f"请从以上 OCR 识别文本中提取 {max_keywords} 个最重要的关键词。"
            "关键词应该是文本的核心主题、重要概念或关键信息。"
            "返回 JSON 格式：{{\"keywords\": [\"关键词1\", \"关键词2\", ...]}}"
        )
    else:
        instruction = (
            f"Please extract the top {max_keywords} most important keywords from the OCR text above. "
            "Keywords should be core topics, important concepts, or key information. "
            "Return JSON format: {{\"keywords\": [\"keyword1\", \"keyword2\", ...]}}"
        )
    
    return analyze_ocr_text_with_llm(ocr_text, instruction)


def summarize_ocr_text(
    ocr_text: str,
    max_length: int = 200,
) -> Dict[str, Any]:
    """
    对 OCR 文本进行摘要。
    
    :param ocr_text: OCR 识别出的文本内容
    :param max_length: 摘要最大长度（字符数）
    :return: 摘要结果
    """
    instruction = (
        f"请对以上 OCR 识别文本进行摘要，摘要长度不超过 {max_length} 字。"
        "摘要应该概括文本的主要内容和关键信息。"
        "返回 JSON 格式：{{\"summary\": \"摘要内容\"}}"
    )
    
    return analyze_ocr_text_with_llm(ocr_text, instruction)

