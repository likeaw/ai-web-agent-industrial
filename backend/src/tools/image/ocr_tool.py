"""
OCR 图像文字识别工具。

使用开源 OCR 模型（EasyOCR）识别图片中的文字内容。
支持中英文识别，适用于截图、图片文件等场景。
"""

import os
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

try:
    import easyocr
    EASYOCR_AVAILABLE = True
    EASYOCR_ERROR = None
except ImportError as e:
    # Package not installed
    EASYOCR_AVAILABLE = False
    EASYOCR_ERROR = f"Package not installed: {e}"
    print(f"[ocr_tool] Warning: easyocr package not found. OCR functionality will be disabled.")
    print(f"[ocr_tool] Install with: pip install easyocr")
except OSError as e:
    # DLL loading failure (usually Visual C++ Redistributable missing)
    EASYOCR_AVAILABLE = False
    EASYOCR_ERROR = f"DLL loading failed: {e}"
    print(f"[ocr_tool] Warning: easyocr installed but cannot load (DLL error). OCR functionality will be disabled.")
    print(f"[ocr_tool] Error details: {e}")
    print("[ocr_tool] Solution: Install Visual C++ Redistributable from:")
    print("[ocr_tool]   https://aka.ms/vs/17/release/vc_redist.x64.exe")
    print("[ocr_tool]   Or search for 'Visual C++ Redistributable 2015-2022'")
except Exception as e:
    # Other unexpected errors
    EASYOCR_AVAILABLE = False
    EASYOCR_ERROR = f"Unexpected error: {e}"
    print(f"[ocr_tool] Warning: easyocr import failed. OCR functionality will be disabled.")
    print(f"[ocr_tool] Error: {e}")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[ocr_tool] Warning: Pillow not installed. Some image operations may fail.")
    print("[ocr_tool] Install with: pip install Pillow")


# 全局OCR读取器实例（延迟初始化）
_ocr_reader: Optional[Any] = None


def _get_ocr_reader(languages: List[str] = None) -> Any:
    """
    获取或创建OCR读取器实例（单例模式）。
    
    :param languages: 支持的语言列表，默认 ['ch_sim', 'en']（简体中文+英文）
    :return: EasyOCR Reader 实例
    """
    global _ocr_reader
    
    if not EASYOCR_AVAILABLE:
        if EASYOCR_ERROR and ("DLL" in EASYOCR_ERROR or "c10.dll" in EASYOCR_ERROR):
            raise ImportError(
                "EasyOCR is installed but cannot load due to missing Visual C++ Redistributable.\n"
                "Please install Visual C++ Redistributable from:\n"
                "  https://aka.ms/vs/17/release/vc_redist.x64.exe"
            )
        else:
            raise ImportError(f"easyocr is not available. {EASYOCR_ERROR or 'Please install it with: pip install easyocr'}")
    
    if languages is None:
        languages = ['ch_sim', 'en']  # 简体中文 + 英文
    
    # 如果读取器已存在且语言匹配，直接返回
    if _ocr_reader is not None:
        return _ocr_reader
    
    # 创建新的读取器（首次调用时会下载模型，可能需要一些时间）
    print(f"[ocr_tool] Initializing EasyOCR reader with languages: {languages}")
    print("[ocr_tool] Note: First-time initialization may download models, please wait...")
    _ocr_reader = easyocr.Reader(languages, gpu=False)  # 使用CPU模式，更通用
    print("[ocr_tool] EasyOCR reader initialized successfully")
    
    return _ocr_reader


def extract_text_from_image(
    image_path: str,
    languages: List[str] = None,
    detail: int = 0,
) -> Dict[str, Any]:
    """
    从图片文件中提取文字内容。
    
    :param image_path: 图片文件路径（支持常见格式：png, jpg, jpeg, bmp等）
    :param languages: OCR支持的语言列表，默认 ['ch_sim', 'en']
    :param detail: 详细信息级别，0=只返回文本，1=返回文本+位置+置信度
    :return: 提取结果字典，包含：
        - text: 提取的完整文本（字符串）
        - details: 详细信息列表（如果detail=1），每个元素包含：
            - text: 文本内容
            - bbox: 边界框坐标
            - confidence: 置信度
    """
    if not EASYOCR_AVAILABLE:
        error_msg = "EasyOCR is not available."
        if EASYOCR_ERROR:
            if "DLL" in EASYOCR_ERROR or "c10.dll" in EASYOCR_ERROR:
                error_msg = (
                    "EasyOCR is installed but cannot load due to missing Visual C++ Redistributable.\n"
                    "Please install Visual C++ Redistributable from:\n"
                    "  https://aka.ms/vs/17/release/vc_redist.x64.exe\n"
                    "Or search for 'Visual C++ Redistributable 2015-2022'"
                )
            elif "not installed" in EASYOCR_ERROR.lower():
                error_msg = "EasyOCR is not installed. Please install it with: pip install easyocr"
            else:
                error_msg = f"EasyOCR error: {EASYOCR_ERROR}"
        else:
            error_msg = "EasyOCR is not installed. Please install it with: pip install easyocr"
        
        return {
            "success": False,
            "error": error_msg,
            "text": "",
            "details": []
        }
    
    if not os.path.exists(image_path):
        return {
            "success": False,
            "error": f"Image file not found: {image_path}",
            "text": "",
            "details": []
        }
    
    try:
        reader = _get_ocr_reader(languages)
        
        # 执行OCR识别
        print(f"[ocr_tool] Extracting text from image: {image_path}")
        results = reader.readtext(image_path, detail=detail)
        
        # 处理结果
        if detail == 0:
            # 只返回文本列表
            texts = [item for item in results if isinstance(item, str)]
            full_text = "\n".join(texts)
            return {
                "success": True,
                "text": full_text,
                "details": []
            }
        else:
            # 返回详细信息
            text_parts = []
            details = []
            
            for item in results:
                if isinstance(item, tuple) and len(item) >= 2:
                    bbox, text, confidence = item[0], item[1], item[2] if len(item) > 2 else 1.0
                    text_parts.append(text)
                    details.append({
                        "text": text,
                        "bbox": bbox,
                        "confidence": float(confidence)
                    })
            
            full_text = "\n".join(text_parts)
            return {
                "success": True,
                "text": full_text,
                "details": details
            }
    
    except Exception as e:
        print(f"[ocr_tool] Error during OCR extraction: {e}")
        return {
            "success": False,
            "error": str(e),
            "text": "",
            "details": []
        }


def extract_text_from_screenshot(
    screenshot_path: str,
    languages: List[str] = None,
    detail: int = 0,
) -> Dict[str, Any]:
    """
    从截图文件中提取文字内容（extract_text_from_image的别名，语义更清晰）。
    
    :param screenshot_path: 截图文件路径
    :param languages: OCR支持的语言列表
    :param detail: 详细信息级别
    :return: 提取结果字典
    """
    return extract_text_from_image(screenshot_path, languages, detail)


def batch_extract_text_from_images(
    image_paths: List[str],
    languages: List[str] = None,
    detail: int = 0,
) -> List[Dict[str, Any]]:
    """
    批量从多个图片文件中提取文字内容。
    
    :param image_paths: 图片文件路径列表
    :param languages: OCR支持的语言列表
    :param detail: 详细信息级别
    :return: 提取结果列表，每个元素对应一个图片的提取结果
    """
    results = []
    for image_path in image_paths:
        result = extract_text_from_image(image_path, languages, detail)
        result["image_path"] = image_path  # 添加图片路径信息
        results.append(result)
    return results

