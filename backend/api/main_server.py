import asyncio
import json
import time
from typing import Dict, Set, Optional, Any, Callable
from datetime import datetime

# FastAPI 依赖
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState

# 假设 Agent 核心模块和数据模型在相应的路径
# !!! 请确保这些导入路径在您的项目中是正确的 !!!
try:
    from backend.src.agent.DecisionMaker import DecisionMaker
    from backend.src.data_models.decision_engine.decision_models import TaskGoal
    # BrowserService 仅用于 DecisionMaker 的初始化，如果 DecisionMaker 内部处理，可忽略此导入
    from backend.src.services.BrowserService import BrowserService 
except ImportError as e:
    # 占位符类，如果在您的环境中运行报错，请确保您的导入路径正确
    print(f"Import Error in main_server.py: Check your module paths. Error: {e}")
    class DecisionMaker:
        def __init__(self, task_goal, headless=True, callback_function=None): pass
        def run(self): 
            print("DecisionMaker running in placeholder mode.")
            time.sleep(5)
    class TaskGoal:
        def __init__(self, target_description): pass


# --- 配置 ---
app = FastAPI(title="AI Agent Backend API")

# 启用 CORS，允许前端连接
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 允许所有来源 (仅供开发测试)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 全局状态管理 ---
# 监控客户端连接
monitor_connections: Set[WebSocket] = set()
# Agent 运行中的任务（使用 asyncio.Future 跟踪状态）
running_task: Optional[asyncio.Future] = None


async def broadcast_message(message: Dict):
    """向所有连接的监控客户端广播消息。"""
    message_str = json.dumps(message)
    dead_connections = []
    
    # 检查连接是否处于开放状态
    active_connections = [
        conn for conn in monitor_connections 
        if conn.client_state == WebSocketState.CONNECTED
    ]
    
    await_list = [conn.send_text(message_str) for conn in active_connections]
    
    # 并行发送，并处理异常
    results = await asyncio.gather(*await_list, return_exceptions=True)
    
    for ws, result in zip(active_connections, results):
        if isinstance(result, Exception):
             print(f"ERROR: Failed to send to connection {id(ws)}: {type(result).__name__}. Marking for removal.")
             dead_connections.append(ws)
             
    for ws in dead_connections:
        monitor_connections.discard(ws)
        

def task_callback_function(message: Dict):
    """
    (同步函数) DecisionMaker 在执行过程中调用此函数发送状态更新。
    它必须将同步调用转换为异步任务来广播。
    """
    # 在 DecisionMaker 的同步线程中被调用，必须转为异步任务
    try:
        # 使用 run_coroutine_threadsafe 确保协程在主事件循环中运行
        asyncio.run_coroutine_threadsafe(
            broadcast_message(message),
            asyncio.get_event_loop()
        )
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [CALLBACK ERROR] Failed to run broadcast coroutine: {e}")


def execute_agent_sync(task_description: str):
    """
    (同步函数) 封装 DecisionMaker 的同步 run 逻辑。
    此函数将在 loop.run_in_executor 启动的独立线程中运行。
    """
    # ❗ 修复: 确保在函数内任何读取/修改全局变量前声明 ❗
    global running_task 
    
    # 初始状态广播
    task_callback_function({"type": "STATUS", "level": "INFO", "message": f"Agent task received: {task_description}"})
    
    try:
        # 1. 初始化 DecisionMaker 实例
        task_goal = TaskGoal(target_description=task_description)
        # 传入 callback_function 和 headless 模式
        maker = DecisionMaker(task_goal, headless=True, callback_function=task_callback_function)
        
        # 2. 执行 Agent 核心逻辑
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [AGENT] Starting run for: {task_description}")
        task_callback_function({"type": "STATUS", "level": "RUNNING", "message": "Agent execution started in background thread."})
        
        # --- 核心阻塞调用 ---
        maker.run() 
        
        # 3. 任务完成后发送最终成功消息
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [AGENT] Task finished successfully.")
        task_callback_function({"type": "STATUS", "level": "SUCCESS", "message": "Agent task execution finished."})
        
    except Exception as e:
        # 任务失败时发送错误消息
        error_msg = f"Agent task failed: {type(e).__name__}: {str(e)}"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [AGENT ERROR] {error_msg}")
        task_callback_function({"type": "STATUS", "level": "ERROR", "message": error_msg})
        
    finally:
        # 无论成功或失败，任务完成后清除 running_task 状态
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [AGENT] Cleaning up task reference.")
        running_task = None
        

@app.websocket("/ws/agent/monitor")
async def websocket_endpoint(websocket: WebSocket):
    """处理前端的 WebSocket 监控连接。"""
    
    # ❗ 修复: 确保在函数内任何读取/修改全局变量前声明 ❗
    global running_task 
    
    await websocket.accept()
    monitor_connections.add(websocket)
    client_id = f"client_{time.time()}"
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WS_CONNECT] Client connected: {client_id}")

    try:
        # 首次连接，发送当前 Agent 状态
        await websocket.send_json({"type": "STATUS", "level": "INFO", "message": f"Connected to Backend. Total monitors: {len(monitor_connections)}"})
        
        # 检查 running_task 状态 (读取操作)
        if running_task and not running_task.done():
            await websocket.send_json({"type": "STATUS", "level": "RUNNING", "message": "Warning: A task is currently running on the server."})

        while True:
            # 等待接收前端消息
            data = await websocket.receive_json()
            
            # 接收前端的 client_id 或其他消息
            if "client_id" in data:
                 print(f"[{datetime.now().strftime('%H:%M:%S')}] [WS_RECV] Received client ID: {data['client_id']}")
                 continue
                 
            command = data.get("command")
            task_description = data.get("task_description")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [WS_COMMAND] Parsed command: {command}")
            
            if command == "START_TASK":
                
                if not task_description:
                    await websocket.send_json({"type": "STATUS", "level": "ERROR", "message": "Task description is empty."})
                    continue

                # 检查 running_task 状态 (读取操作)
                if running_task and not running_task.done():
                    await websocket.send_json({"type": "STATUS", "level": "WARNING", "message": "A task is already running. Please wait for it to complete."})
                    continue
                
                # ----------------------------------------------------------------
                # 核心逻辑：在后台线程中运行同步 Agent 逻辑
                # ----------------------------------------------------------------
                
                loop = asyncio.get_event_loop()
                
                # run_in_executor 返回一个 Future 对象，我们将其存储以跟踪状态 (修改操作)
                running_task = loop.run_in_executor(
                    None, # None 使用默认线程池
                    execute_agent_sync, 
                    task_description
                )
                
                # 立即向所有客户端广播任务开始
                await broadcast_message({"type": "STATUS", "level": "RUNNING", "message": f"Agent task received and starting: {task_description}"})

            elif command == "STOP_TASK":
                 # 检查 running_task 状态 (读取操作)
                 if running_task and not running_task.done():
                    # 尝试取消 Future
                    result = running_task.cancel()
                    if result:
                        await broadcast_message({"type": "STATUS", "level": "WARNING", "message": "Agent task forcefully cancelled by user."})
                    else:
                        await broadcast_message({"type": "STATUS", "level": "ERROR", "message": "Could not cancel task (it may be finishing up)."})
                    # 清除 running_task 状态 (修改操作)
                    running_task = None
                 else:
                     await websocket.send_json({"type": "STATUS", "level": "INFO", "message": "No running task to stop."})


    except WebSocketDisconnect:
        # 客户端断开连接
        pass
    except RuntimeError as e:
        # 捕获可能的 RuntimeError
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WS_ERROR] Connection runtime error: {e}")
    finally:
        monitor_connections.discard(websocket)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Connection closed. Total monitors: {len(monitor_connections)}")

# --- FastAPI 根路由 (可选，用于健康检查) ---
@app.get("/")
async def health_check():
    return {"status": "ok", "service": "AI Agent Backend"}