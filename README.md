## ai-web-agent-industrial：工业级自主 Web Agent 框架

### 🚀 项目概述

本项目是一个 **工业级 Web 自动化 AI Agent 框架**，用于替代人工执行“打开网站、搜索、点击、提取数据、记录到记事本/文件”等重复性网页操作，并保证过程可审计、可回放、可扩展。  
当前版本提供了一个基于 `rich` 的命令行对话前端，用户用自然语言描述任务，后端通过 **LLM + 动态执行图 (Dynamic Execution Graph)** 自动规划并驱动浏览器和本地工具执行。

**核心特性：**

- **工业级数据模型**：通过 Pydantic 定义 `TaskGoal` / `WebObservation` / `DecisionAction` / `ExecutionNode`，约束 LLM 输出，确保每一步操作可执行、可追踪。
- **动态执行图 (DEG)**：使用 `DynamicExecutionGraph` 管理任务步骤及依赖，支持失败剪枝、动态纠错计划注入。
- **浏览器自动化**：基于 Playwright 的 `BrowserService` 执行 `navigate_to` / `click_element` / `type_text` / `scroll` / `extract_data` 等操作。
- **丰富工具层**：在 `backend/src/tools/` 中将“本地工具”和“浏览器工具”拆分为独立模块，便于按单个操作维护和扩展。
- **可视化审计**：`VisualizationAdapter` 将 DEG 渲染为 Mermaid 图，并输出 HTML 报告到 `logs/graphs/`，便于复盘每次任务执行。
- **统一临时文件管理**：所有由 Agent 生成的临时文件统一放在项目根目录 `temp/` 下，按类型（notes/screenshots/...）和任务主题+时间命名。

更多面向开发者的细节，请参见 `docs/DEV_GUIDE.md`。

### 🧱 项目结构总览

```text
ai-web-agent-industrial/
├─ run_agent.cmd                 # Windows 一键启动 / 清理脚本
├─ backend/
│  └─ src/
│     ├─ agent/
│     │  ├─ DecisionMaker.py     # 决策执行者：拉起浏览器、驱动执行图、处理失败与纠错
│     │  └─ Planner.py           # 动态执行图 DEG：节点管理、优先级调度、纠错计划注入
│     ├─ data_models/
│     │  └─ decision_engine/
│     │     ├─ decision_models.py # Pydantic 数据模型：TaskGoal / WebObservation / DecisionAction / ExecutionNode
│     │     └─ ai_agent_models.hpp # C++ 版本的数据结构定义（便于跨语言集成）
│     ├─ services/
│     │  ├─ BrowserService.py    # Playwright 浏览器适配层 + 工具调用入口
│     │  └─ LLMAdapter.py        # LLM 调用封装 + JSON Schema 约束
│     ├─ tools/
│     │  ├─ local_tools.py       # 本地工具（例如：launch_notepad）
│     │  └─ browser/             # 浏览器工具（每个操作一个文件）
│     │     ├─ search_results.py # extract_search_results：搜索结果提取
│     │     ├─ screenshot.py     # take_screenshot：分类存储截图
│     │     ├─ click_nth.py      # click_nth_match：点击第 N 个匹配元素
│     │     └─ find_link_by_text.py # find_link_by_text：按文本模糊匹配链接
│     ├─ utils/
│     │  └─ path_utils.py        # get_project_root / build_temp_file_path 等路径与 temp 管理工具
│     ├─ visualization/
│     │  └─ VisualizationAdapter.py # DEG → Mermaid HTML 渲染
│     └─ cli.py                  # rich 命令行对话入口（推荐使用）
├─ logs/
│  └─ graphs/                    # 执行图可视化 HTML 报告（运行时自动生成）
├─ temp/                         # 统一临时文件目录（运行时自动创建）
│  ├─ notes/                     # 记事本/文本类输出
│  └─ screenshots/               # 截图文件
└─ docs/
   └─ DEV_GUIDE.md               # 开发手册（项目结构与文件职责说明）
```

### 🛠️ 安装与配置

#### 1. 环境依赖

- **操作系统**：Windows 10+（当前脚本和本地工具主要针对 Windows 做了适配）  
- **Python**：3.9+  
- **浏览器自动化**：Playwright (chromium)

```bash
# 克隆仓库
git clone <your-repo-link>
cd ai-web-agent-industrial

# 创建并激活虚拟环境（示例）
python -m venv venv
.\venv\Scripts\activate         # Windows
# source venv/bin/activate      # Linux/macOS

# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器驱动
playwright install chromium
```

#### 2. 配置环境变量

在项目根目录创建 `.env` 文件，用于配置 LLM 和浏览器模式等信息：

```dotenv
# LLM 配置 (以 DeepSeek 为例)
LLM_API_KEY="YOUR_LLM_API_KEY"
LLM_MODEL_NAME="deepseek-chat"
LLM_API_URL="https://api.deepseek.com/v1/chat/completions"

# 浏览器运行模式（True=无头，False=可见窗口）
BROWSER_HEADLESS=False
```

### ▶️ 快速开始（推荐方式：命令行对话模式）

#### 1. 使用一键脚本启动

在项目根目录执行（或直接双击）`run_agent.cmd`：

```cmd
cd ai-web-agent-industrial
run_agent.cmd
```

你会看到一个英文菜单：

- **1**：Run CLI – 启动基于 `rich` 的对话式前端。  
- **2**：Clean logs – 清理 `logs\` 目录。  
- **3**：Clean temp – 清理 `temp\` 目录。  
- **4**：Clean logs + temp – 同时清理日志和临时文件。  
- **Q**：退出脚本。

#### 2. 直接运行 CLI（等价于菜单 1）

```bash
python -m backend.src.cli
```

在 CLI 中，你可以输入类似的自然语言指令，例如：

- “打开百度搜索 合肥，提取前三条搜索结果标题，然后把结果写到记事本里”  
- “打开某个官网，截图当前页面并保存到截图目录”  
- “在当前页面查找包含 ‘官网’ 字样的链接，并将这些链接记录到记事本”  

Agent 会自动：

1. 将你的自然语言转换为 `TaskGoal`。  
2. 通过 `LLMAdapter` 调用 LLM，根据 `allowed_actions` 规划出一系列 `ExecutionNode`。  
3. 由 `DecisionMaker` 驱动 `BrowserService` 和 `tools/` 中的工具执行，实时打印结构化日志。  
4. 在 `logs/graphs/` 中生成可视化 HTML 执行图。  
5. 在 `temp/notes/`、`temp/screenshots/` 中生成对应的输出文件。

### 🧩 核心数据模型（Pydantic / C++）

核心数据模型位于 `backend/src/data_models/decision_engine/decision_models.py` 与 `ai_agent_models.hpp` 中，主要包括：

- **TaskGoal**：任务目标与约束（任务描述、优先级、允许使用的工具集合等）。  
- **WebObservation**：浏览器当前状态快照（URL、HTTP 状态码、关键元素列表、上一步操作反馈等）。  
- **DecisionAction**：单步操作指令（工具名 + 参数 + 决策解释 + 故障策略）。  
- **ExecutionNode**：动态执行图节点（父子关系、优先级、运行状态、最新观测结果等）。  

这些结构通过 JSON Schema 暴露给 LLM，使得 LLM 的规划结果可以被严格验证和回放。

### 📈 可视化审计

`VisualizationAdapter` 会在以下时机输出执行图快照：

- 初始规划完成后（`*_00_initial_plan.html`）。  
- 每个步骤执行之后（`*_step_XX_NODE_ID.html`）。  

你可以打开 `logs/graphs/` 下的 HTML 文件，查看每次任务执行的完整决策路径、每个节点的状态变化和依赖关系，用于调试和合规审计。

### 📚 开发手册

开发者可阅读 `docs/DEV_GUIDE.md` 了解：

- 完整的模块分层说明（Agent / Services / Tools / Utils）。  
- 如何为 Agent 添加新的工具（例如更多浏览器操作、本地应用集成）。  
- 如何扩展 LLM 提示词和 JSON Schema，让大模型安全地使用新工具。  
- 常见调试技巧与日志/临时文件管理规范。  