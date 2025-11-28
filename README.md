## \# ai-web-agent-industrial：工业级自主 Web Agent 框架

[](https://www.python.org/downloads/)
[](https://fastapi.tiangolo.com/)
[](https://playwright.dev/)
[](https://www.deepseek.com/)

### 🚀 项目概述与核心目标

本项目的核心目标是开发一个高可靠、可审计的 AI Agent 框架，用于替代人类执行重复性的、基于网页（或其他界面）的机械性工作。

我们的 Agent 侧重于**工业级可靠性**，通过结构化数据模型和动态执行图来确保任务的可追溯性和稳定性，同时采用高级技术来**模拟人类操作**，有效应对网站的防爬和安全机制。

**核心价值与特性：**

  * **人类行为模拟 (Anti-Bot)**: 基于 Playwright，实现接近真实用户的操作模式（例如：鼠标随机移动、打字延迟），有效避免触发网站的反爬机制。
  * **动态规划执行 (DEG)**: 引入 **动态执行图 (Dynamic Execution Graph)** 机制，确保任务的每一步都能被规划、跟踪、回溯，并支持异常熔断。
  * **结构化决策**: 通过严格的 Pydantic 数据模型 (`TaskGoal`, `WebObservation`, `DecisionAction`) 约束 LLM 的输出，确保指令的准确性和可执行性。
  * **实时监控与可审计性**: 基于 **FastAPI/WebSocket**，提供实时的任务状态更新和 **Mermaid** 可视化图表，实现对 Agent 运行流程的完全审计。
  * **异步非阻塞后端**: Agent 核心阻塞逻辑在独立线程中执行 (`loop.run_in_executor`)，保障 API 的响应能力和 WebSocket 连接的稳定性。
  * **多语言兼容数据模型**: 核心数据模型同时提供 Python (Pydantic) 和 C++ (Struct) 定义，便于未来与不同语言的工业系统集成。

### ⚙️ 核心架构组件

项目采用清晰的分层架构，解耦了决策、规划、执行和通信等核心逻辑：

| 模块名称 | 文件路径 | 职责简述 |
| :--- | :--- | :--- |
| **决策执行者** (`DecisionMaker`) | `backend/src/agent/DecisionMaker.py` | 任务的生命周期管理者。驱动 Planner 流转，调用 BrowserService 执行操作，处理全局异常，并输出可视化快照。 |
| **动态规划器** (`Planner`) | `backend/src/agent/Planner.py` | 管理 **动态执行图** 的流转逻辑。负责生成下一步执行节点，或加载静态测试计划。 |
| **浏览器服务** (`BrowserService`) | `backend/src/services/BrowserService.py` | 基于 **Playwright** 的工具适配层。执行 `DecisionAction`（如点击、输入），并返回标准化的 `WebObservation`。 |
| **LLM 适配器** (`LLMAdapter`) | `backend/src/services/LLMAdapter.py` | 封装 LLM API 调用，使用 JSON Schema 确保 LLM 严格遵守结构化决策模型的输出格式。 |
| **可视化适配器** (`VisualizationAdapter`) | `backend/src/visualization/VisualizationAdapter.py` | 将 DEG 实时转换为 **Mermaid** 图表，用于生成流程审计的 HTML 报告。 |
| **API 服务** (`main_server.py`) | `backend/api/main_server.py` | 基于 **FastAPI** 的 Web 服务，提供 WebSocket 接口用于任务启动和实时状态广播。 |

### 🧩 核心数据模型（Pydantic/C++）

项目的稳定运行依赖于以下四个严格定义的、工业级数据结构：

| 模型名称 | 用途 | 关键字段 |
| :--- | :--- | :--- |
| **TaskGoal** | 任务目标与约束的定义。 | `target_description`, `task_deadline_utc`, `max_execution_time_seconds` |
| **WebObservation** | 浏览器环境的结构化状态快照（LLM 的输入）。 | `current_url`, `key_elements`, `screenshot_available`, `last_action_feedback` |
| **DecisionAction** | LLM 决策出的原子操作指令（Planner 的输出）。 | `tool_name`, `tool_args`, `reasoning`, `confidence_score` |
| **ExecutionNode** | 动态执行图中的节点。 | `node_id`, `parent_id`, `action`, `current_status` (`PENDING`/`SUCCESS`/`FAILED`) |

### 🛠️ 安装与配置

#### 1\. 环境依赖

确保您的系统安装了 **Python 3.9+**，并安装了 `git`。

```bash
# 克隆仓库
git clone <your-repo-link>
cd ai-web-agent-industrial

# 创建并激活虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
.\venv\Scripts\activate   # Windows

# 安装 Python 依赖
pip install -r requirements.txt 

# 安装 Playwright 浏览器驱动
playwright install chromium
```

#### 2\. 配置环境变量

创建 `.env` 文件，用于配置 LLM 密钥和 API 地址。

```dotenv
# .env 文件示例

# LLM 配置 (DeepSeek 示例)
LLM_API_KEY="YOUR_LLM_API_KEY"
LLM_MODEL_NAME="deepseek-chat"
LLM_API_URL="https://api.deepseek.com/v1/chat/completions"

# 默认浏览器运行模式 (True 为无头模式/后台运行，推荐生产环境使用)
AGENT_HEADLESS=True 
```

### ▶️ 快速开始

#### 1\. 启动后端服务

使用 Uvicorn 启动异步 API 服务器：

```bash
# --reload 仅用于开发环境
uvicorn backend.api.main_server:app --reload --host 0.0.0.0 --port 8000
```

服务器启动后，API 服务将在 `http://0.0.0.0:8000` 运行。

#### 2\. 任务启动与实时监控 (WebSocket)

前端客户端（或测试脚本）通过 WebSocket 连接并发送启动指令：

**WebSocket 地址:** `ws://0.0.0.0:8000/ws/agent/monitor`

**启动指令示例 (JSON Payload):**

```json
{
    "command": "START_TASK",
    "task_description": "Go to bing.com, search for 'Industrial AI Agent', and extract the first 3 links."
}
```

**实时状态接收:** Agent 任务将在后台线程中执行，并通过 WebSocket 实时回调发送以下类型的状态消息：

```json
// 运行中状态示例
{"type": "STATUS", "level": "RUNNING", "message": "Agent execution started in background thread."}

// 操作进度示例
{"type": "ACTION", "level": "INFO", "message": "Executing action: click_element, XPath: //button[@id='search-button']"}

// 任务完成示例
{"type": "STATUS", "level": "SUCCESS", "message": "Agent task execution finished."}
```

### 📈 可视化审计

在 Agent 运行过程中，`VisualizationAdapter` 会将当前的动态执行图 (DEG) 转换为 **Mermaid** 图。

您可以通过打开生成的 HTML 报告文件，直观地查看任务流程、节点状态（`SUCCESS` 绿色, `FAILED` 红色等）和操作之间的逻辑依赖关系，极大提高了 Agent 行为的可审计性。