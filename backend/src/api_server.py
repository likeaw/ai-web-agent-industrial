"""
FastAPI Web服务器：为前端提供RESTful API和WebSocket支持
"""

import os
import sys
import uuid
import json
import asyncio
import threading
import time
from typing import Dict, Optional
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.src.data_models.decision_engine.decision_models import TaskGoal, ExecutionNode, ExecutionNodeStatus
from backend.src.agent.DecisionMaker import DecisionMaker

load_dotenv()

app = FastAPI(title="AI Web Agent Industrial API")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局状态
active_tasks: Dict[str, Dict] = {}
task_executors: Dict[str, DecisionMaker] = {}
websocket_connections: Dict[str, list] = {}


class TaskCreateRequest(BaseModel):
    description: str
    headless: bool = False


class TaskResponse(BaseModel):
    task_uuid: str
    goal: dict
    nodes: Dict[str, dict]
    root_node_id: Optional[str] = None
    status: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None


def _create_task_goal(description: str) -> TaskGoal:
    """根据用户自然语言描述构造一个 TaskGoal"""
    task_uuid = f"TASK-{str(uuid.uuid4())[:8]}"
    return TaskGoal(
        task_uuid=task_uuid,
        step_id="INIT",
        target_description=description,
        priority_level=5,
        max_execution_time_seconds=180,
        allowed_actions=[
            "navigate_to",
            "click_element",
            "type_text",
            "scroll",
            "wait",
            "extract_data",
            "get_element_attribute",
            "open_notepad",
            "take_screenshot",
            "click_nth",
            "find_link_by_text",
            "download_page",
            "download_link",
            "create_directory",
            "delete_file_or_directory",
            "list_directory",
            "read_file_content",
            "write_file_content",
            "create_word_document",
            "create_excel_document",
            "create_powerpoint_document",
            "create_office_document",
            # OCR 工具
            "extract_text_from_image",
            "extract_text_from_screenshot",
            "analyze_ocr_text",
        ],
    )


def _node_to_dict(node: ExecutionNode) -> dict:
    """将ExecutionNode转换为字典"""
    return {
        "node_id": node.node_id,
        "parent_id": node.parent_id,
        "child_ids": node.child_ids,
        "execution_order_priority": node.execution_order_priority,
        "action": {
            "tool_name": node.action.tool_name,
            "tool_args": node.action.tool_args,
            "max_attempts": node.action.max_attempts,
            "execution_timeout_seconds": node.action.execution_timeout_seconds,
            "wait_for_condition_after": node.action.wait_for_condition_after,
            "reasoning": node.action.reasoning,
            "confidence_score": node.action.confidence_score,
            "expected_outcome": node.action.expected_outcome,
            "on_failure_action": node.action.on_failure_action,
        },
        "current_status": node.current_status.value,
        "failure_reason": node.failure_reason,
        "required_precondition": node.required_precondition,
        "expected_cost_units": node.expected_cost_units,
        "last_observation": node.last_observation.dict() if node.last_observation else None,
        "resolved_output": node.resolved_output,
    }


def _task_to_dict(task_uuid: str, maker: DecisionMaker) -> dict:
    """将任务转换为字典格式"""
    nodes_dict = {}
    for node_id, node in maker.planner.nodes.items():
        nodes_dict[node_id] = _node_to_dict(node)
    
    return {
        "task_uuid": task_uuid,
        "goal": maker.task_goal.dict(),
        "nodes": nodes_dict,
        "root_node_id": maker.planner.root_node_id,
        "status": "running" if maker.is_running else "idle",
        "start_time": datetime.now().isoformat() if maker.is_running else None,
        "end_time": None,
    }


async def _broadcast_to_task(task_uuid: str, event: str, data: dict):
    """向任务的所有WebSocket连接广播消息"""
    if task_uuid in websocket_connections:
        message = json.dumps({"event": event, "data": data})
        disconnected = []
        for ws in websocket_connections[task_uuid]:
            try:
                await ws.send_text(message)
            except:
                disconnected.append(ws)
        
        # 清理断开的连接
        for ws in disconnected:
            if ws in websocket_connections[task_uuid]:
                websocket_connections[task_uuid].remove(ws)


def _update_task_status_periodically():
    """定期更新任务状态并广播到WebSocket"""
    import asyncio
    
    async def update_loop():
        while True:
            try:
                for task_uuid, maker in list(task_executors.items()):
                    if maker.is_running:
                        # 更新任务数据
                        task_data = _task_to_dict(task_uuid, maker)
                        active_tasks[task_uuid] = task_data
                        
                        # 广播任务更新
                        await _broadcast_to_task(task_uuid, "task_update", {"task": task_data})
                        
                        # 发送节点更新（只发送状态变化的节点）
                        for node_id, node in maker.planner.nodes.items():
                            # 只发送状态不是PENDING的节点更新，减少网络流量
                            if node.current_status != ExecutionNodeStatus.PENDING:
                                await _broadcast_to_task(task_uuid, "node_update", {
                                    "node": _node_to_dict(node)
                                })
                        
                        # 发送浏览器URL更新
                        if maker.browser_service and maker.browser_service.page:
                            try:
                                current_url = maker.browser_service.page.url
                                await _broadcast_to_task(task_uuid, "browser_url", {
                                    "url": current_url
                                })
                            except:
                                pass
                
                await asyncio.sleep(0.5)  # 每0.5秒更新一次
            except Exception as e:
                print(f"Error in update loop: {e}")
                await asyncio.sleep(1)
    
    # 在后台运行更新循环
    asyncio.create_task(update_loop())


def _run_task_in_thread(task_uuid: str, description: str, headless: bool):
    """在单独线程中运行任务"""
    import asyncio
    
    # 创建新的事件循环用于这个线程
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        goal = _create_task_goal(description)
        maker = DecisionMaker(goal, headless=headless)
        task_executors[task_uuid] = maker
        
        # 更新任务状态
        task_data = _task_to_dict(task_uuid, maker)
        task_data["status"] = "running"
        task_data["start_time"] = datetime.now().isoformat()
        active_tasks[task_uuid] = task_data
        
        # 通知WebSocket任务已开始
        loop.run_until_complete(_broadcast_to_task(task_uuid, "task_update", {"task": task_data}))
        loop.run_until_complete(_broadcast_to_task(task_uuid, "log", {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "level": "info",
            "message": f"任务开始执行: {description}",
        }))
        
        # 启动任务
        maker.run()
        
        # 确保is_running设置为False
        maker.is_running = False
        
        # 任务完成
        task_data = _task_to_dict(task_uuid, maker)
        task_data["status"] = "completed"
        task_data["end_time"] = datetime.now().isoformat()
        active_tasks[task_uuid] = task_data
        
        # 通知WebSocket任务已完成
        loop.run_until_complete(_broadcast_to_task(task_uuid, "task_update", {"task": task_data}))
        loop.run_until_complete(_broadcast_to_task(task_uuid, "log", {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "level": "success",
            "message": "任务执行完成",
        }))
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        task_data = active_tasks.get(task_uuid, {})
        task_data["status"] = "failed"
        task_data["end_time"] = datetime.now().isoformat()
        active_tasks[task_uuid] = task_data
        
        # 通知WebSocket任务失败
        error_msg = f"任务执行失败: {str(e)}"
        loop.run_until_complete(_broadcast_to_task(task_uuid, "task_update", {"task": task_data}))
        loop.run_until_complete(_broadcast_to_task(task_uuid, "log", {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "level": "error",
            "message": error_msg,
        }))
    finally:
        # 注意：不要立即关闭浏览器，因为前端可能还需要查看截图
        # 延迟关闭浏览器，给前端一些时间获取最后的截图
        def delayed_close():
            import time
            time.sleep(5)  # 等待5秒
            if task_uuid in task_executors:
                executor = task_executors[task_uuid]
                if executor.browser_service:
                    try:
                        executor.close()
                    except:
                        pass
                del task_executors[task_uuid]
        
        import threading
        close_thread = threading.Thread(target=delayed_close, daemon=True)
        close_thread.start()
        
        loop.close()


@app.post("/api/tasks", response_model=TaskResponse)
async def create_task(request: TaskCreateRequest):
    """创建新任务"""
    goal = _create_task_goal(request.description)
    task_uuid = goal.task_uuid
    
    # 初始化任务数据
    task_data = {
        "task_uuid": task_uuid,
        "goal": goal.dict(),
        "nodes": {},
        "root_node_id": None,
        "status": "idle",
        "start_time": None,
        "end_time": None,
    }
    active_tasks[task_uuid] = task_data
    
    # 在后台线程中启动任务
    thread = threading.Thread(
        target=_run_task_in_thread,
        args=(task_uuid, request.description, request.headless),
        daemon=True
    )
    thread.start()
    
    return TaskResponse(**task_data)


@app.get("/api/tasks/{task_uuid}", response_model=TaskResponse)
async def get_task(task_uuid: str):
    """获取任务详情"""
    if task_uuid not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_data = active_tasks[task_uuid]
    
    # 如果任务正在运行，更新节点状态
    if task_uuid in task_executors:
        maker = task_executors[task_uuid]
        task_data = _task_to_dict(task_uuid, maker)
        active_tasks[task_uuid] = task_data
    
    return TaskResponse(**task_data)


@app.get("/api/tasks")
async def list_tasks():
    """列出所有任务"""
    return {"tasks": list(active_tasks.values())}


@app.post("/api/tasks/{task_uuid}/stop")
async def stop_task(task_uuid: str):
    """停止任务"""
    if task_uuid not in task_executors:
        raise HTTPException(status_code=404, detail="Task not found or not running")
    
    executor = task_executors[task_uuid]
    executor.is_running = False
    
    if executor.browser_service:
        executor.close()
    
    task_data = active_tasks.get(task_uuid, {})
    task_data["status"] = "stopped"
    task_data["end_time"] = datetime.now().isoformat()
    active_tasks[task_uuid] = task_data
    
    return {"message": "Task stopped"}


@app.get("/api/tasks/{task_uuid}/screenshot")
async def get_screenshot(task_uuid: str):
    """获取浏览器截图"""
    # 首先检查任务是否存在（可能在active_tasks中但不在executors中）
    if task_uuid not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 如果任务不在executors中，尝试从文件系统获取最后一张截图
    if task_uuid not in task_executors:
        screenshot_dir = project_root / "temp" / "screenshots"
        if screenshot_dir.exists():
            screenshots = sorted(screenshot_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
            if screenshots:
                return FileResponse(
                    screenshots[0],
                    media_type="image/png",
                    headers={
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Pragma": "no-cache",
                        "Expires": "0"
                    }
                )
        raise HTTPException(status_code=404, detail="Screenshot not available (task may have completed)")
    
    executor = task_executors[task_uuid]
    
    # 如果浏览器服务未初始化，等待一段时间
    max_wait = 10  # 最多等待10秒
    wait_count = 0
    while not executor.browser_service and wait_count < max_wait:
        await asyncio.sleep(0.5)
        wait_count += 0.5
        # 检查任务是否还在运行
        if task_uuid not in task_executors:
            # 任务已结束，尝试从文件系统获取
            screenshot_dir = project_root / "temp" / "screenshots"
            if screenshot_dir.exists():
                screenshots = sorted(screenshot_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
                if screenshots:
                    return FileResponse(
                        screenshots[0],
                        media_type="image/png",
                        headers={
                            "Cache-Control": "no-cache, no-store, must-revalidate",
                            "Pragma": "no-cache",
                            "Expires": "0"
                        }
                    )
            raise HTTPException(status_code=404, detail="Task completed, screenshot not found")
    
    if not executor.browser_service:
        raise HTTPException(status_code=400, detail="Browser not initialized yet, please wait")
    
    # 尝试直接从浏览器页面截图
    try:
        if executor.browser_service.page:
            import io
            
            # 使用Playwright截图（返回bytes）
            screenshot_bytes = executor.browser_service.page.screenshot(type='png', full_page=False)
            
            return StreamingResponse(
                io.BytesIO(screenshot_bytes),
                media_type="image/png",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
    except Exception as e:
        print(f"Direct screenshot failed: {e}, trying file-based screenshot")
    
    # 回退到文件系统截图
    screenshot_dir = project_root / "temp" / "screenshots"
    if not screenshot_dir.exists():
        screenshot_dir.mkdir(parents=True, exist_ok=True)
    
    screenshots = sorted(screenshot_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if screenshots:
        return FileResponse(
            screenshots[0],
            media_type="image/png",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    else:
        raise HTTPException(status_code=404, detail="Screenshot not found")


@app.get("/api/tasks/{task_uuid}/cdp-url")
async def get_cdp_url(task_uuid: str):
    """获取浏览器视图URL（用于浏览器视图嵌入）"""
    if task_uuid not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 如果任务不在executors中（已完成），仍然返回截图URL
    if task_uuid not in task_executors:
        import time
        timestamp = int(time.time() * 1000)
        return {
            "url": f"/api/tasks/{task_uuid}/screenshot?t={timestamp}",
            "status": "completed"
        }
    
    executor = task_executors[task_uuid]
    
    # 如果浏览器服务未初始化，返回等待状态
    if not executor.browser_service:
        return {
            "url": None,
            "status": "waiting",
            "message": "Browser is initializing, please wait..."
        }
    
    # 直接返回截图URL（使用时间戳避免缓存）
    import time
    timestamp = int(time.time() * 1000)
    return {
        "url": f"/api/tasks/{task_uuid}/screenshot?t={timestamp}",
        "status": "ready"
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket端点"""
    await websocket.accept()
    task_uuid = None
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("event") == "join_task":
                task_uuid = message.get("task_uuid")
                if task_uuid:
                    if task_uuid not in websocket_connections:
                        websocket_connections[task_uuid] = []
                    websocket_connections[task_uuid].append(websocket)
                    
                    # 发送当前任务状态
                    if task_uuid in active_tasks:
                        await websocket.send_text(json.dumps({
                            "event": "task_update",
                            "data": {"task": active_tasks[task_uuid]}
                        }))
            
            elif message.get("event") == "ping":
                await websocket.send_text(json.dumps({"event": "pong"}))
    
    except WebSocketDisconnect:
        pass
    finally:
        if task_uuid and task_uuid in websocket_connections:
            if websocket in websocket_connections[task_uuid]:
                websocket_connections[task_uuid].remove(websocket)


@app.on_event("startup")
async def startup_event():
    """启动时初始化后台任务"""
    import asyncio
    
    async def update_loop():
        while True:
            try:
                for task_uuid, maker in list(task_executors.items()):
                    if maker.is_running:
                        # 更新任务数据
                        task_data = _task_to_dict(task_uuid, maker)
                        active_tasks[task_uuid] = task_data
                        
                        # 广播任务更新
                        await _broadcast_to_task(task_uuid, "task_update", {"task": task_data})
                        
                        # 发送节点更新（只发送状态变化的节点）
                        for node_id, node in maker.planner.nodes.items():
                            # 只发送状态不是PENDING的节点更新，减少网络流量
                            if node.current_status != ExecutionNodeStatus.PENDING:
                                await _broadcast_to_task(task_uuid, "node_update", {
                                    "node": _node_to_dict(node)
                                })
                        
                        # 发送浏览器URL更新
                        if maker.browser_service and maker.browser_service.page:
                            try:
                                current_url = maker.browser_service.page.url
                                await _broadcast_to_task(task_uuid, "browser_url", {
                                    "url": current_url
                                })
                            except:
                                pass
                
                await asyncio.sleep(0.5)  # 每0.5秒更新一次
            except Exception as e:
                print(f"Error in update loop: {e}")
                await asyncio.sleep(1)
    
    # 启动后台更新任务
    asyncio.create_task(update_loop())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

