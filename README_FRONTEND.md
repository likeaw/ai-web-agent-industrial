# AI Web Agent Industrial - 前端使用指南

## 🚀 快速开始

### 方式一：一键启动（推荐）

运行项目根目录下的 `run_full_stack.cmd`，这将同时启动：
- API服务器（http://localhost:8000）
- 前端开发服务器（http://localhost:3000）

### 方式二：分别启动

1. **启动API服务器**
   ```cmd
   run_api_server.cmd
   ```

2. **启动前端开发服务器**
   ```cmd
   run_frontend.cmd
   ```
   或进入 frontend 目录运行：
   ```cmd
   cd frontend
   npm install  # 首次运行需要安装依赖
   npm run dev
   ```

3. **访问前端应用**
   打开浏览器访问：http://localhost:3000

## 📋 前置要求

- **Node.js** 16+ （用于前端开发服务器）
- **Python 3.9+** （用于后端API服务器）
- 已安装项目依赖（运行 `run_agent.cmd` 会自动安装）

## 🎯 主要功能

### 1. 对话界面
- 输入自然语言任务描述
- 选择运行模式：
  - **前端模式**：通过Web界面执行任务
  - **命令行模式**：提示使用命令行工具
- 选择浏览器模式：
  - **可见模式**：浏览器窗口可见
  - **无头模式**：浏览器后台运行

### 2. 决策树可视化
- 实时展示任务执行决策树
- 节点状态实时更新
- 点击节点查看详细信息
- 支持缩放和拖拽

### 3. 浏览器视图
- 实时显示浏览器当前页面
- 支持截图刷新
- 可全屏查看

### 4. 任务管理
- 查看所有任务列表
- 查看任务详情
- 停止正在运行的任务

### 5. 实时日志
- 实时显示任务执行日志
- 按级别分类显示
- 显示节点关联信息

## 🔧 配置说明

### 环境变量

确保项目根目录有 `.env` 文件，包含：

```env
LLM_API_KEY="your_api_key"
LLM_MODEL_NAME="deepseek-chat"
LLM_API_URL="https://api.deepseek.com/v1/chat/completions"
BROWSER_HEADLESS=False
```

### API服务器配置

API服务器默认运行在 `http://localhost:8000`

如需修改端口，编辑 `backend/src/api_runner.py`：

```python
uvicorn.run(
    "backend.src.api_server:app",
    host="0.0.0.0",
    port=8000,  # 修改这里
    ...
)
```

### 前端开发服务器配置

前端默认运行在 `http://localhost:3000`

如需修改端口，编辑 `frontend/vite.config.ts`：

```typescript
server: {
  port: 3000,  // 修改这里
  ...
}
```

## 🐛 故障排除

### 前端无法连接后端

1. 确保API服务器正在运行（检查 http://localhost:8000）
2. 检查 `frontend/vite.config.ts` 中的代理配置
3. 检查浏览器控制台是否有CORS错误

### WebSocket连接失败

1. 确保API服务器支持WebSocket
2. 检查防火墙设置
3. 查看浏览器控制台的WebSocket错误信息

### 浏览器视图无法显示

1. 确保任务正在运行
2. 检查浏览器服务是否正常初始化
3. 查看后端日志中的错误信息

### 决策树不更新

1. 检查WebSocket连接状态（查看右上角状态指示器）
2. 刷新页面重新连接
3. 查看浏览器控制台的WebSocket消息

## 📝 开发说明

### 添加新功能

1. **添加新组件**：在 `frontend/src/components/` 下创建
2. **添加API接口**：在 `backend/src/api_server.py` 中添加路由
3. **添加WebSocket事件**：在 `backend/src/api_server.py` 的 `_broadcast_to_task` 中使用

### 代码结构

- `frontend/src/components/` - React组件
- `frontend/src/services/` - API和WebSocket服务
- `frontend/src/store/` - 状态管理（Zustand）
- `frontend/src/types/` - TypeScript类型定义
- `backend/src/api_server.py` - FastAPI服务器
- `backend/src/api_runner.py` - API服务器启动脚本

## 🎨 UI定制

前端使用 Ant Design 5，可以通过以下方式定制：

1. **主题配置**：修改 `frontend/src/main.tsx` 中的 `ConfigProvider`
2. **样式覆盖**：在组件对应的 `.css` 文件中添加样式
3. **组件配置**：在组件中使用 Ant Design 的配置属性

## 📚 更多信息

- 后端API文档：访问 http://localhost:8000/docs （启动API服务器后）
- 项目主README：查看项目根目录的 `README.md`
- 开发指南：查看 `docs/DEV_GUIDE.md`

