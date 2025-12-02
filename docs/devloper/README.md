## 开发者文档总览

本目录面向希望在本项目基础上二次开发、扩展功能或集成到自身系统中的开发者，整理了：

- **项目结构与模块职责**
- **本地开发环境与运行方式**
- **核心数据模型与执行流程**
- **调试与可视化审计说明**

如果你只是想「先跑起来体验一下」，可以直接参考项目根目录的 `README.md` 中的「快速开始」小节。

---

## 项目结构与模块职责

项目结构总体如下（只展示与核心功能相关的主要目录和文件）：

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
│     │     ├─ decision_models.py  # Pydantic 数据模型：TaskGoal / WebObservation / DecisionAction / ExecutionNode
│     │     └─ ai_agent_models.hpp # C++ 版本的数据结构定义（便于跨语言集成）
│     ├─ services/
│     │  ├─ BrowserService.py    # Playwright 浏览器适配层 + 工具调用入口
│     │  └─ LLMAdapter.py        # LLM 调用封装 + JSON Schema 约束
│     ├─ tools/
│     │  ├─ local_tools.py       # 本地工具（例如：launch_notepad）
│     │  └─ browser/             # 浏览器工具（每个操作一个文件）
│     │     ├─ search_results.py     # extract_search_results：搜索结果提取
│     │     ├─ screenshot.py         # take_screenshot：分类存储截图
│     │     ├─ click_nth.py          # click_nth_match：点击第 N 个匹配元素
│     │     └─ find_link_by_text.py  # find_link_by_text：按文本模糊匹配链接
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
   ├─ DEV_GUIDE.md               # 原始开发手册（分层与扩展说明）
   ├─ PYTHON_ENV_SETUP.md        # 内置 Python 环境配置说明
   └─ devloper/                  # 当前开发文档目录
      └─ README.md               # 本文档
```

推荐先阅读 `docs/DEV_GUIDE.md` 获取更详细的模块分层说明，再结合本目录的说明进行二次开发。

---

## 环境与安装（面向开发者）

### 基本依赖

- **操作系统**：Windows 10+（当前脚本和本地工具主要针对 Windows 做了适配）  
- **Python**：3.9+（推荐 3.10 或更高版本）  
- **浏览器自动化**：Playwright (chromium)

### 方式一：使用内置 Python 环境（推荐，一键部署）

项目支持使用 Windows 下的 **Python embeddable package**，以减少系统依赖差异：

```bash
# 1. 下载 Python 3.11.0 embeddable package 并解压到 python/ 目录
#    或直接运行 setup_python_env.cmd 按提示操作

# 2. 在项目根目录执行一键脚本
run_agent.cmd
```

详细的内置 Python 环境说明可参考 `docs/PYTHON_ENV_SETUP.md`。

### 方式二：使用系统 Python 环境

```bash
# 克隆仓库
git clone <your-repo-link>
cd ai-web-agent-industrial

# 创建并激活虚拟环境（示例）
python -m venv venv
.\venv\Scripts\activate         # Windows
# source venv/bin/activate      # Linux/macOS

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器驱动
playwright install chromium

# 可选：安装 Office 文档支持（如需创建 Word/Excel/PowerPoint）
pip install python-docx openpyxl python-pptx
```

### 环境变量配置

在项目根目录创建 `.env` 文件，用于配置 LLM 和浏览器模式等信息：

```dotenv
# LLM 配置 (以 DeepSeek 为例)
LLM_API_KEY="YOUR_LLM_API_KEY"
LLM_MODEL_NAME="deepseek-chat"
LLM_API_URL="https://api.deepseek.com/v1/chat/completions"

# 浏览器运行模式（True=无头，False=可见窗口）
BROWSER_HEADLESS=False
```

---

## 运行与调试

### 启动 CLI（推荐入口）

```bash
python -m backend.src.cli
```

或在 Windows 下使用一键脚本：

```cmd
run_agent.cmd
```

脚本会提供一个简单菜单：

- **1**：Run CLI – 启动基于 `rich` 的对话式前端  
- **2**：Clean logs – 清理 `logs\` 目录  
- **3**：Clean temp – 清理 `temp\` 目录  
- **4**：Clean logs + temp – 同时清理日志和临时文件  
- **Q**：退出脚本

在 CLI 中可以直接输入自然语言任务，例如：

- 「打开某个网站搜索关键词，整理前几条结果到记事本」  
- 「打开指定官网并截图当前页面，保存到截图目录」

---

## 核心数据模型与执行流程

核心数据模型位于 `backend/src/data_models/decision_engine/decision_models.py` 与 `ai_agent_models.hpp` 中，主要包括：

- **TaskGoal**：任务目标与约束（任务描述、优先级、允许使用的工具集合等）  
- **WebObservation**：浏览器当前状态快照（URL、HTTP 状态码、关键元素列表、上一步操作反馈等）  
- **DecisionAction**：单步操作指令（工具名 + 参数 + 决策解释 + 故障策略）  
- **ExecutionNode**：动态执行图节点（父子关系、优先级、运行状态、最新观测结果等）

整体执行流程大致为：

1. 用户在 CLI 中输入自然语言任务，构造 `TaskGoal`  
2. `LLMAdapter` 将任务与当前 `WebObservation` 输入大模型，并约束输出结构  
3. LLM 规划出若干 `ExecutionNode`，构成动态执行图（DEG）  
4. `DecisionMaker` 按图中依赖和优先级调度节点，调用 `BrowserService` 与各类工具执行  
5. 执行过程中的每一步都会被记录与可视化，便于回放与调试

更多关于分层设计和扩展方式，请参考 `docs/DEV_GUIDE.md`。

---

## 可视化与日志

`VisualizationAdapter` 会在以下时机输出执行图快照：

- 初始规划完成后（`*_00_initial_plan.html`）  
- 每个步骤执行之后（`*_step_XX_NODE_ID.html`）

你可以在 `logs/graphs/` 下打开对应的 HTML 文件，查看：

- 每次任务执行的完整决策路径  
- 每个节点的状态变化与依赖关系  
- 各类工具的调用顺序与结果

与之配合的还有：

- `temp/notes/`：存放文本类/记事本类输出  
- `temp/screenshots/`：存放截图文件

---

## 扩展与二次开发建议

- **新增浏览器动作**：在 `backend/src/tools/browser/` 中按「一个文件一个工具」的原则添加，实现对应操作并在提示词中开放给 LLM 使用  
- **新增本地工具**：在 `backend/src/tools/local_tools.py` 中添加函数，并在决策环节暴露相应的工具名与入参  
- **接入不同 LLM 服务**：修改 `services/LLMAdapter.py`，适配新的接口地址、鉴权方式和模型名称  
- **跨语言集成**：可参考 `ai_agent_models.hpp` 中的 C++ 结构定义，与现有系统进行更紧密的集成

如果你在扩展过程中有新的想法或遇到问题，欢迎基于本目录进行补充文档和示例。


