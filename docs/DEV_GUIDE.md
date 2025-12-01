## 开发手册（Developer Guide）

### 1. 总览

本手册面向希望二次开发、扩展或集成本项目的工程师，重点说明：

- 项目分层与模块职责；
- `tools/` 工具层的扩展方式（浏览器工具、本地工具）；
- 临时文件与日志的管理约定；
- LLM 配置与新工具接入（让大模型学会用新工具）。

建议先阅读仓库根目录的 `README.md` 了解整体能力，再结合本手册深入具体模块。

---

### 2. 分层架构与主要模块

#### 2.1 Agent 层（任务编排与执行）

- `backend/src/agent/DecisionMaker.py`
  - 负责单次任务的完整生命周期：
    - 初始化 `DynamicExecutionGraph`、`BrowserService`；
    - 调用 `LLMAdapter` 生成/补充执行计划；
    - 驱动执行循环：选择下一个节点 → 解析动态参数 → 执行工具 → 处理结果；
    - 失败时触发剪枝或 LLM 自我纠错（self-correction）；
    - 生成执行总结报告、触发可视化快照输出。
  - 同时包含一个 `__main__` 自测入口，用于在无 CLI 情况下直接跑预置计划或 LLM 动态规划。

- `backend/src/agent/Planner.py`
  - 核心是 `DynamicExecutionGraph`：
    - `add_node`：添加节点，并维护父子关系与执行优先级；
    - `get_next_node_to_execute`：根据当前图状态，选择下一个 `PENDING` 节点，采用“按优先级的广度/深度混合策略”，并保证注入的纠错子图也会被遍历到；
    - `prune_on_failure`：当某节点失败时，剪枝其子树，将相关节点标记为 `PRUNED`；
    - `inject_correction_plan`：将 LLM 返回的新 plan 片段挂载在失败节点之后，实现金融/工业场景中常见的“自愈性流程”；
    - `generate_initial_plan_with_llm`：调用 `LLMAdapter.generate_nodes` 构建初始计划。

#### 2.2 Services 层（外部系统适配）

- `backend/src/services/BrowserService.py`
  - 使用 Playwright 同步 API (`sync_playwright`) 封装浏览器操作：
    - `navigate_to`、`click_element`、`type_text`、`scroll`、`wait`；
    - `get_element_attribute`：用于读取 DOM 属性；
    - `extract_data`：借助 `tools.browser.search_results.extract_search_results` 抽取搜索结果或列表内容；
    - `take_screenshot` / `click_nth` / `find_link_by_text`：通过 `tools.browser` 中的工具实现更复杂操作。
  - 输出统一的 `WebObservation`，包括当前 URL / HTTP 状态码 / 关键元素列表 / 上一步操作反馈等。

- `backend/src/services/LLMAdapter.py`
  - 封装与 LLM（如 DeepSeek）的交互：
    - 通过 `ExecutionNode.model_json_schema()` 生成 JSON Schema，并在 system prompt 中明确要求 LLM 严格输出结构化 JSON；
    - 使用 `response_format={"type": "json_object"}` 进一步约束输出；
    - `planning_principle` 字段中描述各工具的关键参数要求，帮助大模型“看说明书写调用”；
    - `generate_nodes`：发起 HTTP 请求，解析响应 JSON，并用 Pydantic 严格校验成 `ExecutionNode` 列表。

#### 2.3 Tools 层（可扩展工具库）

##### 2.3.1 本地工具

- `backend/src/tools/local_tools.py`
  - `launch_notepad(file_path: Optional[str], initial_content: str) -> Tuple[str, bool, str]`
    - 在 Windows 下启动 `notepad.exe` 并写入初始内容；
    - 使用 `utf-8-sig` 编码写文件，保证系统记事本可以正确识别编码；
    - 返回 `(目标文件路径, 是否成功, 消息字符串)`。
  - 后续如需扩展本地工具（如打开 Excel、调用自定义脚本等），建议在此文件或新的本地工具模块中添加。

##### 2.3.2 浏览器工具（单操作单文件）

所有浏览器工具位于 `backend/src/tools/browser/` 目录中，每个文件只负责一个清晰的操作逻辑：

- `search_results.py`
  - `extract_search_results(page, current_url, selector, attribute="text", limit=3) -> List[str]`
    - 若传入了 `selector`，则优先用该 selector 提取文本/属性；
    - 若没有取到结果，且当前 URL 是百度搜索结果页，则等待 `#content_left` 出现，并从其中的 `h3` 元素提取标题。

- `screenshot.py`
  - `take_screenshot(page, task_topic, filename=None, full_page=True) -> str`
    - 借助 `utils.path_utils.build_temp_file_path("screenshots", task_topic, ".png")` 决定截图存放路径；
    - 支持自定义 `filename`，也会统一落在 `temp/screenshots/` 中；
    - 返回截图的绝对路径，供上层写入 `feedback.message`。

- `click_nth.py`
  - `click_nth_match(page, selector, index=0, timeout_ms=10000)`
    - 等待 selector 可见；
    - 点击匹配列表中的第 `index` 个元素（从 0 开始），常用于“点击第 N 条搜索结果”。

- `find_link_by_text.py`
  - `find_link_by_text(page, keyword, limit=5) -> List[Dict[str, str]]`
    - 使用 XPath `//a[contains(normalize-space(string(.)), '{keyword}')]` 模糊匹配包含关键字的链接；
    - 返回形如 `{"text": "...", "href": "..."}` 的列表。

`backend/src/tools/browser/__init__.py` 则集中导出这些工具，便于 `BrowserService` 用统一入口导入。

---

### 3. 路径与临时文件管理

#### 3.1 项目根路径推断

- 模块：`backend/src/utils/path_utils.py`
  - `get_project_root()`：
    - 通过当前文件位置（`backend/src/utils/`）向上三级目录推断项目根目录；
    - 避免硬编码磁盘路径（如 `D:\...`），保证项目可以被克隆到任意机器任意位置运行。

#### 3.2 临时文件分类与命名规则

- `get_temp_dir(file_type: Literal["notes","screenshots","downloads","other"])`
  - 返回 `<root>/temp/<file_type>/`，并在不存在时自动创建。

- `build_temp_file_path(file_type, task_topic, extension)`
  - 使用 `slugify(task_topic)` 生成安全的文件名前缀（去除非法字符、控制长度）；
  - 加上时间戳 `YYYYMMDD_HHMMSS`；
  - 最终路径形如：  
    - `temp/notes/任务主题_20251201_153045.txt`  
    - `temp/screenshots/任务主题_20251201_153210.png`

使用约定：

- 记事本/文本类：`file_type="notes"`，由 `DecisionMaker` 在 `open_notepad` 分支中自动生成；
- 截图类：`file_type="screenshots"`，由 `take_screenshot` 工具生成；
- 其它类型（如下载文件、导出报表）可根据需要扩展 `file_type` 并在调用处采用同一套规则。

---

### 4. LLM 与工具接入约定

#### 4.1 Allowed Actions 列表

`TaskGoal.allowed_actions` 决定了 LLM 在规划时可以使用哪些工具。  
当前 CLI 和 `DecisionMaker` 自测入口默认包含：

- `navigate_to`
- `click_element`
- `type_text`
- `scroll`
- `wait`
- `extract_data`
- `get_element_attribute`
- `open_notepad`
- `take_screenshot`
- `click_nth`
- `find_link_by_text`

如需新增工具（例如 `download_file`），需要：

1. 在 `BrowserService.execute_action` 或对应 Service 中新增 `elif action.tool_name == "download_file": ...` 分支，实现具体逻辑；  
2. 将 `"download_file"` 加入 `TaskGoal.allowed_actions`（CLI 和/或自测入口）；  
3. 在 `LLMAdapter._create_api_payload` 的 `planning_principle` 中补充工具说明和关键参数格式。

#### 4.2 LLM 提示词与 JSON Schema

- `LLMAdapter._create_json_schema()`：
  - 直接调用 `ExecutionNode.model_json_schema()` 生成完整 schema；
  - 要求 LLM 返回：`{"execution_plan": [<ExecutionNode JSON>...]}`。

- `LLMAdapter._create_api_payload()`：
  - system prompt 中包括：
    - 当前任务目标 `Goal: ...`；
    - `Allowed Tools: [...]` 列表；
    - 每个工具的参数约定（参见 `planning_principle` 的中文说明）；  
    - 以及 JSON Schema 文本（帮助模型理解结构）。

这样设计的好处：

- 新工具一旦在 `planning_principle` 中被描述，并列入 `allowed_actions`，LLM 就能自动规划出包含该工具的 `ExecutionNode`；  
- 后端仍然通过 Pydantic Schema 验证输出，保证不会因为格式错误导致执行崩溃。

---

### 5. 日志与可视化

- 执行日志：直接输出到命令行，由 `DecisionMaker` 和各 Service/Tools 打印（带 `[INFO]` / `[WARN]` / `[ERROR]` 等前缀）。  
- 执行图可视化：
  - 由 `DecisionMaker._save_visualization()` 调用 `VisualizationAdapter.render_graph_to_html_string`；
  - 将 HTML 写入 `logs/graphs/plan_<TASK_ID>_*.html`；
  - 文件可直接在浏览器中查看，用于调试或审计。

`run_agent.cmd` 中的清理选项可以一键删除 `logs/` 和 `temp/`，方便在开发调试过程中重置环境。

---

### 6. 如何扩展一个新的浏览器工具（示例流程）

假设你要新增一个工具：`get_page_title`，用于获取当前页面标题并作为数据流的一部分：

1. **在 tools 层添加实现**
   - 建议在 `backend/src/tools/browser/` 中新增文件 `page_title.py`：
     - 实现函数 `get_page_title(page: Page) -> str`，内部调用 `page.title()`。

2. **在 BrowserService 中接入**
   - 在 `BrowserService.execute_action` 中增加分支：
     - `elif action.tool_name == "get_page_title": ...`；
     - 调用 `get_page_title` 并将结果写入 `feedback.message`。

3. **更新 TaskGoal.allowed_actions**
   - 在 CLI 的 `_create_task_goal` 中加入 `"get_page_title"`；
   - 在 `DecisionMaker` 自测入口的 `allowed_actions` 中也加上。

4. **更新 LLMAdapter 提示**
   - 在 `planning_principle` 中增加一条：
     - “当需要获取当前页面标题时，请使用 get_page_title 工具，无需额外参数。”

完成以上步骤后，LLM 在规划任务时就可以自然产出包含 `get_page_title` 的节点，后端也能安全执行并将结果写入后续节点的数据流中。

---

### 7. 贡献与注意事项

- 保持工具“单一职责”：每个工具文件只做一件清晰的事情，便于维护和测试。
- 修改数据模型（尤其是 `ExecutionNode`、`DecisionAction`）时，请同步更新：
  - `decision_models.py`；
  - `ai_agent_models.hpp`（如仍需 C++ 兼容）；
  - `LLMAdapter` 的 JSON Schema 与 `planning_principle`。
- 对于新增的外部依赖（第三方库），请更新 `requirements.txt` 并在 README 中补充安装说明。

如需更复杂的集成（如接入企业内部 SSO、工控系统、报表平台等），可以在 `services/` 下增加新的 Service，并通过 `DecisionAction.tool_name` 和 `tools/` 中的适配器进行桥接。 


