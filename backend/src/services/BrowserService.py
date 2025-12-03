# 文件: backend/src/services/BrowserService.py

import json
import os
import subprocess
import tempfile
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
# 导入 Playwright 同步 API 和 TimeoutError
from playwright.sync_api import sync_playwright, Page, TimeoutError, Error

# 导入你现有的数据模型

from backend.src.data_models.decision_engine.decision_models import (
    WebObservation, KeyElement, BoundingBox, ActionFeedback, DecisionAction
)

# 浏览器工具层（单个操作的可扩展实现）
from backend.src.tools.browser import (
    extract_search_results,
    take_screenshot,
    click_nth_match,
    find_link_by_text,
    save_current_page_html,
    download_from_link,
    extract_page_content,
)
from backend.src.tools.browser.llm_html_analyzer import (
    analyze_html_with_llm,
    extract_with_llm_analysis,
)
from backend.src.tools.browser.human_simulator import (
    prepare_page_for_extraction,
    human_like_scroll,
    random_delay,
)
from backend.src.tools.system import resolve_user_path
from backend.src.utils.path_utils import slugify
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
        self._headless = headless
        self._login_prompt_shown = False

        self.page.on("response", self._handle_response)

    def _handle_response(self, response):
        """捕获主文档的状态码"""
        if response.request.resource_type == "document":
            self._last_http_status = response.status

    def close(self):
        self.context.close()
        self.browser.close()
        self.playwright.stop()

    def _detect_login_interface(self) -> Tuple[bool, str]:
        """
        综合检测登录界面（包括 URL、页面元素和弹窗/模态框）。
        
        返回: (是否检测到登录界面, 检测到的类型描述)
        """
        try:
            # 1. 检测 URL 中的登录关键词
            url = (self.page.url or "").lower()
            url_keywords = ["login", "signin", "sign-in", "auth", "authenticate", "signin", "log-in"]
            if any(keyword in url for keyword in url_keywords):
                return True, "URL contains login keywords"
            
            # 2. 检测页面上的密码输入框（包括弹窗中）
            try:
                password_inputs = self.page.locator("input[type='password']")
                if password_inputs.count() > 0:
                    return True, "Password input field detected"
            except Exception:
                pass
            
            # 3. 检测弹窗/模态框中的登录相关内容
            login_keywords_cn = ["登录", "登入", "登陆", "账号登录", "用户登录", "会员登录", "立即登录"]
            login_keywords_en = ["login", "sign in", "sign-in", "log in", "log-in", "authenticate"]
            all_login_keywords = login_keywords_cn + login_keywords_en
            
            # 常见的弹窗/模态框选择器
            modal_selectors = [
                "[role='dialog']",
                ".modal",
                ".modal-dialog",
                ".popup",
                ".popup-dialog",
                ".dialog",
                "[class*='modal']",
                "[class*='popup']",
                "[class*='dialog']",
                "[id*='modal']",
                "[id*='popup']",
                "[id*='dialog']",
                "[id*='login']",
                "[class*='login']",
            ]
            
            # 检测弹窗是否可见且包含登录关键词
            for modal_selector in modal_selectors:
                try:
                    modals = self.page.locator(modal_selector)
                    modal_count = modals.count()
                    
                    for idx in range(min(modal_count, 5)):  # 最多检查5个弹窗
                        modal = modals.nth(idx)
                        
                        # 检查弹窗是否可见
                        try:
                            if not modal.is_visible(timeout=500):
                                continue
                        except Exception:
                            continue
                        
                        # 获取弹窗的文本内容
                        try:
                            modal_text = modal.inner_text().lower()
                        except Exception:
                            continue
                        
                        # 检查是否包含登录关键词
                        if any(keyword.lower() in modal_text for keyword in all_login_keywords):
                            # 进一步检查弹窗中是否有密码输入框或用户名输入框
                            has_password_in_modal = False
                            has_username_in_modal = False
                            
                            try:
                                password_in_modal = modal.locator("input[type='password']")
                                if password_in_modal.count() > 0:
                                    has_password_in_modal = True
                            except Exception:
                                pass
                            
                            try:
                                username_selectors = [
                                    "input[type='text']",
                                    "input[type='email']",
                                    "input[name*='user']",
                                    "input[name*='account']",
                                    "input[name*='login']",
                                    "input[placeholder*='user']",
                                    "input[placeholder*='account']",
                                ]
                                for username_sel in username_selectors:
                                    if modal.locator(username_sel).count() > 0:
                                        has_username_in_modal = True
                                        break
                            except Exception:
                                pass
                            
                            if has_password_in_modal or (has_username_in_modal and any(kw in modal_text for kw in ["登录", "login", "sign"])):
                                return True, f"Login modal/popup detected (contains login keywords and form fields)"
                            
                            # 即使没有明确的表单字段，如果包含登录关键词也可能需要登录
                            if any(kw in modal_text for kw in login_keywords_cn + ["login", "sign in"]):
                                return True, f"Login modal/popup detected (contains login keywords)"
                except Exception:
                    continue
            
            # 4. 检测页面主体中的登录相关文本和表单
            try:
                page_text = self.page.inner_text("body").lower()
                if any(keyword.lower() in page_text for keyword in all_login_keywords):
                    # 检查页面是否有用户名/密码输入框组合
                    try:
                        username_inputs = self.page.locator(
                            "input[type='text'], input[type='email'], input[name*='user'], input[name*='account']"
                        )
                        password_inputs = self.page.locator("input[type='password']")
                        
                        if username_inputs.count() > 0 and password_inputs.count() > 0:
                            return True, "Login form detected on page (username + password inputs)"
                    except Exception:
                        pass
            except Exception:
                pass
            
            return False, ""
        except Exception as e:
            # 如果检测过程中出错，保守处理，不触发登录等待
            print(f"[WARN] Error during login detection: {e}")
            return False, ""

    def _maybe_wait_for_manual_login(self):
        """
        检测是否处于登录页面或登录弹窗，如果是且为有头模式，则提示用户在浏览器中完成登录后按回车继续。
        支持检测 URL、页面元素和弹窗/模态框中的登录界面。
        """
        if self._headless or self._login_prompt_shown:
            return
        
        # 给页面一点时间加载弹窗（如果存在）
        try:
            self.page.wait_for_timeout(1000)  # 等待1秒，让弹窗有时间出现
        except Exception:
            pass
        
        # 综合检测登录界面
        has_login, detection_info = self._detect_login_interface()
        
        if has_login:
            self._login_prompt_shown = True
            print("\n" + "=" * 70)
            print("[HUMAN-ASSIST] 🔐 登录界面检测")
            print("=" * 70)
            print(f"检测到登录界面: {detection_info}")
            print("\n请在浏览器窗口中完成登录操作（填写用户名、密码等）。")
            print("登录完成后，请回到此窗口按 ENTER 键继续...")
            print("=" * 70)
            
            try:
                input()
                print("[HUMAN-ASSIST] ✅ 已收到确认，继续执行任务...\n")
                # 重置标志，允许后续再次检测（例如页面跳转后可能再次出现登录）
                self._login_prompt_shown = False
            except EOFError:
                # 在无法交互的环境下，直接继续，不阻塞
                print("[HUMAN-ASSIST] ⚠️  Input not available; continuing without manual login wait.\n")

    def _get_selector(self, args: Dict) -> str:
        """
        [工业最终版] 解析定位器。
        支持：XPath, CSS Selector, 文本定位, 和新增的父子组合定位 (container_selector + relative_selector)。
        """
        # 1. 精确 XPath
        if "xpath" in args and args["xpath"]:
            return f"xpath={args['xpath']}"
            
        # 2. CSS Selector (标准定位)
        if "selector" in args and args["selector"]:
            return args["selector"]
            
        # 3. 父子组合定位 (Container + Relative)
        if "container_selector" in args and args["container_selector"]:
            # 使用 Playwright 的复合定位语法: "父定位器 >> 子定位器"
            container = args["container_selector"]
            relative = args.get("relative_selector", "") 
            if not relative:
                return container
            return f"{container} >> {relative}" 
            
        # 4. 基于文本内容的智能定位 (兼容旧格式)
        if "text_content" in args and args["text_content"]:
            text = args['text_content']
            if "tag_hint" in args and args["tag_hint"]:
                return f"{args['tag_hint']}:has-text('{text}')"
            else:
                return f"*:has-text('{text}')"
            
        raise ValueError(f"JSON Error: No valid selector provided in args: {args.keys()}")

    def _perform_pre_actions(self, actions: List[Dict[str, Any]], timeout_ms: int) -> None:
        """
        在执行特定工具（如 extract_data）前，执行一组简单的页面交互操作。
        支持 click/scroll/wait，便于在提取前唤起或加载更多内容。
        """
        for idx, pre_action in enumerate(actions):
            action_type = (pre_action or {}).get("type")
            if not action_type:
                continue

            try:
                if action_type == "click":
                    selector = self._get_selector(pre_action)
                    self.page.wait_for_selector(selector, state="visible", timeout=timeout_ms)
                    self.page.click(selector, timeout=timeout_ms)
                elif action_type == "scroll":
                    direction = pre_action.get("direction", "down")
                    amount = int(pre_action.get("amount", 800))
                    if direction == "down":
                        self.page.mouse.wheel(0, abs(amount))
                    else:
                        self.page.mouse.wheel(0, -abs(amount))
                elif action_type == "wait":
                    duration = float(pre_action.get("duration", 1))
                    time.sleep(max(0.0, duration))
                else:
                    print(f"[BrowserService] Unknown pre_action '{action_type}' ignored.")
            except Exception as exc:
                print(f"[BrowserService] pre_action #{idx} ({action_type}) failed: {exc}")

    # 在 BrowserService 类中新增一个方法，用于执行后的验证
    def _verify_post_action(self, action: DecisionAction, initial_url: str) -> bool:
        """
        在执行 `click_element` 或 `Maps_to` 后，验证操作结果。
        """
        # 验证是否成功导航 (即 URL 发生了变化)
        if action.tool_name in ["click_element", "navigate_to"]:
            if self.page.url == initial_url:
                # 检查页面是否只是局部刷新，或者确实没有跳转
                if action.tool_name == "click_element":
                    # 只有点击链接后 URL 仍未变，才认为是失败 (除非预期就是局部刷新)
                    print(f"    [VERIFY] Click executed, but URL did not change from {initial_url}. Assuming failure to navigate.")
                    return False
                # 对于 navigate_to，URL 应该等于目标 URL，如果等于初始 URL 则是网络问题
                
        # 成功通过验证
        return True

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
        
    def get_element_attribute(self, selector: str, attribute_name: str) -> str:
        """
        根据 CSS Selector 定位元素并提取指定的属性值。
        :param selector: 元素的 Playwright/CSS Selector。
        :param attribute_name: 要提取的属性名，如 'href', 'value'。
        :return: 属性值，如果元素不存在或属性不存在则返回空字符串。
        """
        try:
            # 使用 page.locator 来获取元素，并等待它处于可见状态
            locator = self.page.locator(selector)
            # 等待元素可见，最多等待 10 秒
            locator.wait_for(state="visible", timeout=10000) 
            
            # 使用 get_attribute 提取属性值
            attribute_value = locator.get_attribute(attribute_name)
            
            return attribute_value if attribute_value is not None else ""
        
        except TimeoutError:
            print(f"[BrowserService] Error: Element not visible or attribute not found for selector: {selector}")
            return ""
        except Error as e:
            print(f"[BrowserService] Playwright Error during get_element_attribute: {e}")
            return ""

    def _launch_notepad(self, action: DecisionAction, feedback: ActionFeedback):
        """
        启动 Windows 记事本，并可选地写入初始内容。
        """
        file_path = action.tool_args.get("file_path")
        initial_content = action.tool_args.get("initial_content")

        if file_path:
            target_path = os.path.abspath(file_path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
        else:
            fd, temp_path = tempfile.mkstemp(prefix="agent_note_", suffix=".txt")
            os.close(fd)
            target_path = temp_path

        if initial_content:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(initial_content)

        try:
            subprocess.Popen(["notepad.exe", target_path], creationflags=subprocess.DETACHED_PROCESS)
            feedback.status = "SUCCESS"
            feedback.message = f"Notepad opened for file: {target_path}"
        except Exception as exc:
            feedback.status = "FAILED"
            feedback.error_code = "NOTEPAD_LAUNCH_ERROR"
            feedback.message = f"Failed to open Notepad: {exc}"
            raise

    def execute_action(self, action: DecisionAction) -> WebObservation:
        """
        核心入口：执行动作 -> 等待页面稳定 -> 提取观测数据
        """
        start_time = time.time()
        feedback = ActionFeedback(status="SUCCESS", error_code="0", message="Action executed.")
        initial_url = self.page.url
        timeout_ms = action.execution_timeout_seconds * 1000

        try:
            # 1. 执行具体动作
            if action.tool_name == "navigate_to":
                url = action.tool_args.get("url")
                if not url:
                    raise ValueError("Missing 'url' in tool_args")
                self.page.goto(url, wait_until="load", timeout=timeout_ms)
                # 导航后检查是否命中登录页面
                self._maybe_wait_for_manual_login()
            
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
                
            elif action.tool_name == "get_element_attribute":
                selector = self._get_selector(action.tool_args)
                attribute_name = action.tool_args.get("attribute_name", "href")
                
                print(f"    -> Extracting attribute '{attribute_name}' from target: {selector}")
                
                # 调用新添加的方法
                extracted_value = self.get_element_attribute(selector, attribute_name)
                
                if extracted_value:
                    # 将提取到的值存入 feedback.message，作为 SUCCESS 时的结果
                    feedback.message = f"Attribute '{attribute_name}' extracted: {extracted_value}"
                    feedback.status = "SUCCESS"
                else:
                    feedback.status = "FAILED"
                    feedback.error_code = "ATTRIBUTE_NOT_FOUND"
                    feedback.message = f"Failed to extract attribute '{attribute_name}' from {selector}. Target not found or attribute missing."
                    raise Error(feedback.message)
                
            elif action.tool_name == "extract_data":
                # 参数提取
                selector = action.tool_args.get("selector")
                attribute = action.tool_args.get("attribute", "text")  # 默认提取元素的文本
                limit = action.tool_args.get("limit")  # 可以是 None（提取全部）
                pre_actions = action.tool_args.get("pre_actions", [])
                extract_mode = action.tool_args.get("mode", "comprehensive")  # simple, advanced, llm, comprehensive
                use_llm = action.tool_args.get("use_llm", True)  # 默认使用 LLM 分析
                extraction_instruction = action.tool_args.get("extraction_instruction", "")  # LLM 提取指令
                prepare_page = action.tool_args.get("prepare_page", True)  # 是否准备页面（展开折叠、触发懒加载等）

                if not selector:
                    # 回退到通用选择器解析逻辑（支持 xpath / text_content 等）
                    try:
                        selector = self._get_selector(action.tool_args)
                    except Exception:
                        selector = None

                # 【关键增强】在提取前全面准备页面，模拟人类操作
                if prepare_page:
                    print("[BrowserService] Preparing page for extraction (expanding collapsible content, triggering lazy load)...")
                    try:
                        prepare_page_for_extraction(self.page)
                    except Exception as e:
                        print(f"[BrowserService] Page preparation warning: {e}")

                if isinstance(pre_actions, list) and pre_actions:
                    self._perform_pre_actions(pre_actions, timeout_ms)

                results = []
                
                # 根据模式选择提取方法（综合策略）
                if extract_mode == "comprehensive" or (extract_mode == "llm" or use_llm):
                    # 综合策略：先尝试 LLM 分析，如果失败则回退到高级提取
                    print("[BrowserService] Using comprehensive extraction strategy (LLM + Advanced)...")
                    
                    # 1. 先尝试 LLM 分析
                    html_content = self.page.content()
                    
                    if extraction_instruction:
                        extraction_instruction_final = extraction_instruction
                    else:
                        extraction_instruction_final = (
                            "提取页面中所有可以跳转的 URL 链接，格式为标题和 URL 的对应关系。"
                            "忽略导航栏、页脚、广告等无关链接，重点关注主要内容区域的链接。"
                            "包括搜索结果、文章链接、产品链接等所有可点击的链接。"
                        )
                    
                    llm_result = analyze_html_with_llm(
                        html_content,
                        extraction_instruction_final,
                        max_html_length=50000
                    )
                    
                    if llm_result.get("success") and "data" in llm_result:
                        data = llm_result["data"]
                        if "items" in data and data["items"]:
                            results = data["items"]
                        elif "links" in data and data["links"]:
                            results = data["links"]
                    
                    # 2. 如果 LLM 提取失败或结果为空，回退到高级提取
                    if not results:
                        print("[BrowserService] LLM extraction returned no results, falling back to advanced extraction...")
                        page_content = extract_page_content(
                            page=self.page,
                            current_url=self.page.url,
                            mode="links",
                            selector=selector,
                            limit=limit,
                            include_html=False,
                        )
                        
                        if "data" in page_content and "links" in page_content["data"]:
                            results = page_content["data"]["links"]
                
                elif extract_mode == "llm":
                    # 仅使用 LLM 分析
                    print("[BrowserService] Using LLM-based HTML analysis for extraction...")
                    html_content = self.page.content()
                    
                    if extraction_instruction:
                        llm_result = analyze_html_with_llm(
                            html_content,
                            extraction_instruction,
                            max_html_length=50000
                        )
                        if llm_result.get("success") and "data" in llm_result:
                            data = llm_result["data"]
                            if "items" in data:
                                results = data["items"]
                            elif "links" in data:
                                results = data["links"]
                    else:
                        results = extract_with_llm_analysis(
                            html_content,
                            task_description=action.tool_args.get("task_description", "提取页面中所有可跳转的 URL 链接"),
                            max_html_length=50000
                        )
                
                elif extract_mode == "advanced":
                    # 使用高级提取工具
                    print("[BrowserService] Using advanced page content extraction...")
                    page_content = extract_page_content(
                        page=self.page,
                        current_url=self.page.url,
                        mode="links",
                        selector=selector,
                        limit=limit,
                        include_html=False,
                    )
                    
                    if "data" in page_content and "links" in page_content["data"]:
                        results = page_content["data"]["links"]
                
                else:
                    # 使用原有的简单提取逻辑
                    if limit is None:
                        limit = 10  # 默认限制
                    
                    results = extract_search_results(
                        page=self.page,
                        current_url=self.page.url,
                        selector=selector,
                        attribute=attribute,
                        limit=limit,
                    )

                if results:
                    feedback.status = "SUCCESS"
                    payload = {
                        "result_type": "link_list",
                        "items": results,
                    }
                    summary = json.dumps(payload, ensure_ascii=False)
                    print(f"[BrowserService] extract_data -> Extracted {len(results)} items")
                    feedback.message = summary
                else:
                    feedback.status = "FAILED"
                    feedback.error_code = "NO_DATA_EXTRACTED"
                    feedback.message = "extract_data: no items extracted from page."
                    print("[BrowserService] extract_data -> NO DATA EXTRACTED")

            elif action.tool_name == "take_screenshot":
                # task_topic 主要用于生成有语义的文件名
                task_topic = action.tool_args.get("task_topic", "web_page")
                filename = action.tool_args.get("filename")
                full_page = bool(action.tool_args.get("full_page", True))
                output_path_arg = action.tool_args.get("output_path")
                output_dir_arg = action.tool_args.get("output_dir")
                custom_output_path: Optional[str] = None

                try:
                    if output_path_arg:
                        custom_output_path = resolve_user_path(output_path_arg)
                    elif output_dir_arg:
                        resolved_dir = resolve_user_path(output_dir_arg)
                        os.makedirs(resolved_dir, exist_ok=True)
                        name = filename
                        if not name:
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            name = f"{slugify(task_topic)}_{ts}.png"
                        custom_output_path = os.path.join(resolved_dir, name)
                except ValueError as exc:
                    raise ValueError(f"Invalid screenshot output path: {exc}") from exc

                screenshot_path = take_screenshot(
                    page=self.page,
                    task_topic=task_topic,
                    filename=filename,
                    full_page=full_page,
                    custom_path=custom_output_path,
                )

                feedback.status = "SUCCESS"
                feedback.message = f"Screenshot saved to: {screenshot_path}"

            elif action.tool_name == "download_page":
                task_topic = action.tool_args.get("task_topic", "web_page")
                path = save_current_page_html(self.page, task_topic=task_topic)
                feedback.status = "SUCCESS"
                feedback.message = f"Page HTML saved to: {path}"

            elif action.tool_name == "download_link":
                task_topic = action.tool_args.get("task_topic", "download")
                url = action.tool_args.get("url")
                selector = None
                if not url and any(k in action.tool_args for k in ("selector", "xpath", "text_content", "container_selector")):
                    selector = self._get_selector(action.tool_args)

                path = download_from_link(
                    page=self.page,
                    task_topic=task_topic,
                    url=url,
                    selector=selector,
                )
                feedback.status = "SUCCESS"
                feedback.message = f"Downloaded content saved to: {path}"

            elif action.tool_name == "click_nth":
                selector = self._get_selector(action.tool_args)
                index = int(action.tool_args.get("index", 0))
                timeout_ms = int(action.tool_args.get("timeout_ms", timeout_ms))

                print(f"    -> Clicking element #{index} for selector: {selector}")
                click_nth_match(
                    page=self.page,
                    selector=selector,
                    index=index,
                    timeout_ms=timeout_ms,
                )

            elif action.tool_name == "find_link_by_text":
                keyword = action.tool_args.get("keyword")
                limit = int(action.tool_args.get("limit", 5))

                if not keyword:
                    raise ValueError("find_link_by_text requires 'keyword' in tool_args.")

                matches = find_link_by_text(
                    page=self.page,
                    keyword=keyword,
                    limit=limit,
                )

                feedback.status = "SUCCESS"
                feedback.message = f"Found {len(matches)} links: {matches}"

            elif action.tool_name == "click_element":
                selector = self._get_selector(action.tool_args)
                print(f"    -> Clicking target: {selector}")
                
                timeout_ms = action.execution_timeout_seconds * 1000

                # 🚀 工业级修复：使用 Playwright 的 expect_navigation 来处理点击导致的页面跳转。
                # 这样可以可靠地等待跳转完成，或在超时时抛出 TimeoutError。
                
                # 1. 确保元素可见
                self.page.wait_for_selector(selector, state="visible", timeout=timeout_ms)
                
                # 2. 预期导航发生并执行点击
                # 这一步会等待 URL 变化或页面加载完成。
                # 如果点击不导致导航，expect_navigation 会超时，所以用 try-except 处理
                try:
                    with self.page.expect_navigation(timeout=timeout_ms):
                        self.page.click(selector, timeout=timeout_ms)
                except TimeoutError:
                    # 点击可能不导致导航（如按钮触发 AJAX），直接点击即可
                    self.page.click(selector, timeout=timeout_ms)
                
                # 点击后可能跳转到登录页，做一次检测
                self._maybe_wait_for_manual_login()

            elif action.tool_name == "open_notepad":
                self._launch_notepad(action, feedback)

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
            
            # 操作完成后，检测是否出现了登录界面（包括弹窗）
            # 这可以在页面加载或 AJAX 操作完成后捕获突然出现的登录弹窗
            self._maybe_wait_for_manual_login() 

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