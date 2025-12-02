# AI Web Agent Industrial - Frontend

工业级 Web Agent 框架的前端应用

## 功能特性

- 🎨 **现代化UI设计**：基于 Ant Design 的工业级界面
- 🌳 **决策树可视化**：实时展示任务执行决策树和节点状态
- 🌐 **浏览器视图嵌入**：实时查看浏览器执行画面
- 💬 **对话界面**：与 AI Agent 进行自然语言交互
- 📋 **任务管理**：查看和管理所有任务
- 📝 **实时日志**：查看任务执行的详细日志
- ⚙️ **运行模式切换**：支持前端模式和命令行模式

## 技术栈

- **React 18** + **TypeScript**
- **Vite** - 现代化构建工具
- **Ant Design 5** - UI组件库
- **React Flow** - 决策树可视化
- **Socket.IO Client** - WebSocket实时通信
- **Zustand** - 状态管理

## 快速开始

### 安装依赖

```bash
cd frontend
npm install
```

### 开发模式

```bash
npm run dev
```

前端将在 http://localhost:3000 启动

### 构建生产版本

```bash
npm run build
```

构建产物将在 `dist` 目录

## 项目结构

```
frontend/
├── src/
│   ├── components/          # React组件
│   │   ├── Layout/         # 布局组件
│   │   ├── DecisionTree/   # 决策树可视化
│   │   ├── BrowserView/    # 浏览器视图
│   │   ├── Chat/           # 对话界面
│   │   ├── TaskPanel/      # 任务面板
│   │   └── Log/            # 日志面板
│   ├── services/           # API和WebSocket服务
│   ├── store/             # 状态管理
│   ├── types/              # TypeScript类型定义
│   └── App.tsx            # 主应用组件
├── package.json
└── vite.config.ts
```

## 使用说明

1. **启动后端API服务器**：运行 `run_api_server.cmd`
2. **启动前端开发服务器**：运行 `run_frontend.cmd` 或使用 `npm run dev`
3. **或使用一键启动**：运行 `run_full_stack.cmd` 同时启动前后端

## 功能说明

### 对话界面
- 输入自然语言任务描述
- 选择运行模式（前端/命令行）
- 选择浏览器模式（可见/无头）

### 决策树视图
- 实时显示任务执行决策树
- 节点状态颜色编码：
  - 🔵 蓝色：等待执行
  - 🟡 黄色：正在运行
  - 🟢 绿色：执行成功
  - 🔴 红色：执行失败
  - ⚫ 灰色：已剪枝/跳过
- 点击节点查看详细信息

### 浏览器视图
- 实时显示浏览器当前页面
- 支持截图模式和CDP模式
- 可全屏查看

### 任务管理
- 查看所有任务列表
- 查看任务状态和详情
- 停止正在运行的任务

### 日志面板
- 实时显示任务执行日志
- 按级别过滤（info/warning/error/success）
- 显示节点关联信息

