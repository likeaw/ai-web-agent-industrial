# 文件: backend/src/services/BrowserService.py

import time
from typing import List, Dict, Any, Optional
# 导入 Playwright 同步 API 和 TimeoutError
from playwright.sync_api import sync_playwright, Page, TimeoutError, Error

# 导入你现有的数据模型
from backend.src.data_models.decision_engine.decision_models import (
    WebObservation, KeyElement, BoundingBox, ActionFeedback, DecisionAction
)

class BrowserService:
    """
    工业级浏览器适配器 (基于 Playwright)。
    职责：执行 DecisionAction，并返回标准化的 WebObservation。
    """

    def __init__(self, headless: bool = True):
        self.playwright = sync_playwright().start()
        # 启动 Chromium，增加参数避免翻译弹窗等干扰，并使用 --no-sandbox
        self.browser = self.playwright.chromium.launch(headless=headless, args=['--disable-features=TranslateUI', '--no-sandbox'])
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        self.page: Page = self.context.new_page()
        self._last_http_status = 200

        self.page.on("response", self._handle_response)

    def _handle_response(self, response):
        """捕获主文档的状态码"""
        if response.request.resource_type == "document":
            self._last_http_status = response.status

    def close(self):
        self.context.close()
        self.browser.close()
        self.playwright.stop()

    def _get_selector(self, args: Dict) -> str:
        """优先使用 xpath，其次使用 selector"""
        if "xpath" in args and args["xpath"]:
            return f"xpath={args['xpath']}"
        if "selector" in args and args["selector"]:
            return args["selector"]
        if "element_id" in args:
            return f"#{args['element_id']}" 
        raise ValueError("No valid selector (xpath/selector/element_id) provided for action.")

    def _extract_interactive_elements(self) -> List[KeyElement]:
        """扫描页面，提取对 AI 有意义的交互元素，修复了 JS 注入时的语法错误。"""
        elements = []
        
        js_script = """
        () => {
            const items = [];
            const tags = ['a', 'button', 'input', 'textarea', 'select'];
            document.querySelectorAll(tags.join(',')).forEach((el, index) => {
                const rect = el.getBoundingClientRect();
                const isVisible = rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden';
                
                if (isVisible) {
                    items.push({
                        element_id: el.id || `gen_id_${index}`,
                        tag_name: el.tagName.toLowerCase(),
                        inner_text: el.innerText.slice(0, 50) || el.value || "", 
                        x_min: rect.left,
                        y_min: rect.top,
                        x_max: rect.right,
                        y_max: rect.bottom,
                        xpath: ""
                    });
                }
            });
            return items;
        }
        """
        
        try:
            raw_data = self.page.evaluate(js_script)
            
            for item in raw_data:
                xpath = f"//{item['tag_name']}[@id='{item['element_id']}']" if "gen_id" not in item['element_id'] else f"//{item['tag_name']}"

                elements.append(KeyElement(
                    element_id=item['element_id'],
                    tag_name=item['tag_name'],
                    xpath=xpath, 
                    inner_text=item['inner_text'].strip(),
                    is_visible=True,
                    is_clickable=True,
                    bbox=BoundingBox(
                        x_min=item['x_min'],
                        y_min=item['y_min'],
                        x_max=item['x_max'],
                        y_max=item['y_max']
                    ),
                    purpose_hint=None
                ))
        except Exception as e:
            print(f"[WARN] Error extracting elements: {e}")
            
        return elements
        
    def execute_action(self, action: DecisionAction) -> WebObservation:
        """
        核心入口：执行动作 -> 等待页面稳定 -> 提取观测数据
        """
        start_time = time.time()
        feedback = ActionFeedback(status="SUCCESS", error_code="0", message="Action executed.")
        
        timeout_ms = action.execution_timeout_seconds * 1000

        try:
            # 1. 执行具体动作
            if action.tool_name == "navigate_to":
                url = action.tool_args.get("url")
                if not url:
                    raise ValueError("Missing 'url' in tool_args")
                self.page.goto(url, wait_until="load", timeout=timeout_ms)
            
            elif action.tool_name == "click_element":
                selector = self._get_selector(action.tool_args)
                
                # 只等待元素存在 (attached)
                self.page.wait_for_selector(selector, state="attached", timeout=timeout_ms) 
                
                # 强制点击 (force=True)，忽略可见性或被覆盖的检查。
                self.page.click(selector, timeout=timeout_ms, force=True)
            
            elif action.tool_name == "type_text":
                selector = self._get_selector(action.tool_args)
                text = action.tool_args.get("text", "")
                submit_key = action.tool_args.get("submit_key") # <-- 获取提交键参数

                # 1. 填充文本：等待元素存在于 DOM 中，并强制填充。
                self.page.wait_for_selector(selector, state="attached", timeout=timeout_ms)
                self.page.fill(selector, text, timeout=timeout_ms, force=True)
                
                # 2. 【人类模拟操作】如果指定了提交键，则按下它来提交表单
                if submit_key:
                    # 使用 page.press 模拟键盘操作，更鲁棒
                    self.page.press(selector, submit_key)
                    print(f"[BrowserService] Human-like simulation: Pressed '{submit_key}' on {selector} to submit.")
                
            elif action.tool_name == "scroll":
                direction = action.tool_args.get("direction", "down")
                scroll_amount = action.tool_args.get("amount", "window.innerHeight")
                
                js_scroll = f"window.scrollBy(0, {scroll_amount})" if direction == "down" else f"window.scrollBy(0, -{scroll_amount})"
                self.page.evaluate(js_scroll)
            
            elif action.tool_name == "wait":
                duration = action.tool_args.get("duration", 2)
                time.sleep(duration) 

            else:
                raise ValueError(f"Unsupported tool: {action.tool_name}")

            # 等待网络空闲
            try:
                self.page.wait_for_load_state("networkidle", timeout=3000)
            except TimeoutError:
                pass 

        except Error as e:
            # 捕获所有 Playwright 错误
            feedback.status = "FAILED"
            feedback.error_code = "PLAYWRIGHT_ERROR"
            feedback.message = str(e)
            print(f"[BrowserService] Action Failed: {e}")
            
        except Exception as e:
            # 捕获其他 Python 错误
            feedback.status = "FAILED"
            feedback.error_code = "EXECUTION_ERROR"
            feedback.message = str(e)
            print(f"[BrowserService] Action Failed: {e}")

        # 2. 构造 WebObservation
        end_time = time.time()
        load_time_ms = int((end_time - start_time) * 1000)
        
        return WebObservation(
            observation_timestamp_utc=str(time.time()),
            current_url=self.page.url,
            http_status_code=self._last_http_status,
            page_load_time_ms=load_time_ms if feedback.status == "SUCCESS" else 0,
            is_authenticated=False, 
            key_elements=self._extract_interactive_elements(), 
            screenshot_available=False, 
            last_action_feedback=feedback,
            memory_context="Browser state captured."
        )