# 文件: frontend/src/app_main.py (最终稳定版本)

import sys
import os
import json
from datetime import datetime
from typing import Optional

# 移除 QWebEngineView 导入，替换为 QWidget/QTextEdit
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLineEdit, QTextEdit, QSplitter
)
from PySide6.QtGui import QIcon, QColor, QTextCharFormat, QTextCursor 
from PySide6.QtCore import QUrl, QThread, Signal, QObject, Qt, Slot
from PySide6.QtWebSockets import QWebSocket

# 定义资源路径 
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
WS_URL = "ws://127.0.0.1:8000/ws/agent/monitor"


class WebSocketClient(QObject):
    """用于在单独线程中处理 WebSocket 连接和消息的 QObject。"""
    message_received = Signal(dict)
    log_signal = Signal(str, str) # message, level
    connected_signal = Signal() # 新增：用于连接成功时通知主线程
    disconnected_signal = Signal() # 新增：用于连接断开时通知主线程

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.websocket: Optional[QWebSocket] = None
        self.url = QUrl(url)

    def connect_to_server(self):
        """此方法在新的 QThread 中执行，在目标线程中创建 QWebSocket。"""
        # 注意：QWebSocket 必须在它所属的线程中创建
        self.websocket = QWebSocket() 
        
        # 信号连接
        self.websocket.connected.connect(self.on_connected)
        self.websocket.disconnected.connect(self.on_disconnected)
        self.websocket.textMessageReceived.connect(self.on_text_message_received)
        # 优化：Qt 的 errorOccurred 信号在不同版本中参数类型可能不同，使用 Slot 确保兼容性
        self.websocket.errorOccurred.connect(self.on_error) 
        
        print(f"Connecting to: {self.url.toString()}")
        self.websocket.open(self.url)

    @Slot()
    def on_connected(self):
        self.connected_signal.emit() # 立即通知主线程更新 UI
        self.log_signal.emit("Connected to Backend API.", "SUCCESS") 
        # 发送客户端标识符
        self.websocket.sendTextMessage(json.dumps({"client_id": "FrontendMonitor"}))

    @Slot()
    def on_disconnected(self):
        self.disconnected_signal.emit() # 通知主线程更新 UI
        self.log_signal.emit("Disconnected from Backend API.", "WARNING")

    @Slot(str)
    def on_text_message_received(self, message: str):
        """接收到后端发送的 Agent 状态信息。"""
        try:
            data = json.loads(message)
            self.message_received.emit(data)
        except json.JSONDecodeError:
            self.log_signal.emit(f"Failed to decode JSON from backend: {message[:100]}...", "ERROR")

    @Slot('QAbstractSocket::SocketError')
    def on_error(self, error_code):
        # 修复：确保处理所有版本的 QAbstractSocket::SocketError
        self.log_signal.emit(f"WebSocket Error occurred (Code: {error_code.name}).", "ERROR")

    def send_command(self, command: str, **kwargs):
        """向后端发送控制指令。"""
        if self.websocket and self.websocket.isValid():
            data = {"command": command, **kwargs}
            self.websocket.sendTextMessage(json.dumps(data))
        else:
            self.log_signal.emit("Cannot send command: WebSocket not connected.", "WARNING")


class MainWindow(QMainWindow):
    
    def log_system_message(self, message: str, level: str):
        """格式化并输出系统/状态日志。"""
        color_map = {
            "INFO": QColor("#729fcf"), "WARNING": QColor("#fce94f"), "ERROR": QColor("#cc0000"),     
            "SUCCESS": QColor("#8ae234"), "RUNNING": QColor("#ff8c00"), "REPORT": QColor("#75507b"),
            "PENDING": QColor("#eeeeec"), "SKIPPED": QColor("#909090"), "FAILED": QColor("#cc0000")
        }
        
        fmt = QTextCharFormat()
        fmt.setForeground(color_map.get(level.upper(), QColor("#eeeeec")))
        
        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.End) 
        
        cursor.insertBlock()
        cursor.setCharFormat(fmt)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}][{level.upper():<7}] {message}"
        
        cursor.insertText(log_entry)
        self.log_output.ensureCursorVisible()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Agent 工业级执行控制台 (纯文本模式)")
        self.setMinimumSize(1200, 800)
        
        # --- 1. UI 布局 ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 任务输入与控制区
        control_layout = QHBoxLayout()
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("请输入 Agent 任务目标 (Task Goal)")
        # 默认输入您测试的命令，方便再次测试
        self.task_input.setText("打开百度官网") 
        
        self.run_button = QPushButton("等待连接...")
        self.run_button.setFixedSize(80, 40)
        self.run_button.setEnabled(False) 
        
        control_layout.addWidget(self.task_input)
        control_layout.addWidget(self.run_button)
        main_layout.addLayout(control_layout)
        
        # 日志/可视化分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setObjectName("LogOutputArea")
        splitter.addWidget(self.log_output)
        
        # 使用 QTextEdit 替换 QWebEngineView
        self.graph_viewer = QTextEdit()
        self.graph_viewer.setReadOnly(True)
        self.graph_viewer.setHtml("<h1>Agent Execution Graph (HTML 源码)</h1><p>可视化功能已禁用，请在浏览器中打开日志文件夹中的 HTML 文件。</p>")
        splitter.addWidget(self.graph_viewer)
        
        splitter.setSizes([300, 500])
        main_layout.addWidget(splitter)
        
        # --- 2. WebSocket 线程化和连接 ---
        self.ws_thread = QThread()
        self.ws_client = WebSocketClient(WS_URL) 
        self.ws_client.moveToThread(self.ws_thread)
        
        # 信号连接
        self.ws_client.log_signal.connect(self.log_system_message)
        
        # 专用的连接/断开信号连接
        self.ws_client.connected_signal.connect(self._set_ui_to_ready)
        self.ws_client.disconnected_signal.connect(self._set_ui_to_disconnected)
        
        self.ws_thread.started.connect(self.ws_client.connect_to_server)
        self.ws_client.message_received.connect(self.handle_agent_message)
        self.ws_thread.start()
        
        # --- 3. 信号连接 ---
        self.run_button.clicked.connect(self._start_task)
        self.log_system_message("System: Application initialized. Connecting to backend...", "INFO")
        
    @Slot()
    def _set_ui_to_ready(self):
        """连接成功时设置 UI 状态。"""
        self.run_button.setText("启动")
        self.run_button.setEnabled(True)

    @Slot()
    def _set_ui_to_disconnected(self):
        """连接断开时设置 UI 状态。"""
        self.run_button.setText("连接失败")
        self.run_button.setEnabled(False)
        self.log_system_message("System: Connection lost or failed. Please check backend status.", "ERROR")


    def _start_task(self):
        """触发任务执行，并通知后端启动 Agent"""
        if not self.run_button.isEnabled():
            self.log_system_message("Cannot start task: Not connected to backend.", "WARNING")
            return
            
        task_goal = self.task_input.text().strip()
        if not task_goal:
            self.log_system_message("Please enter a task goal.", "WARNING")
            return
            
        self.log_system_message(f"Starting Task: {task_goal}", "INFO")
        
        # 向后端发送 START_TASK 指令
        self.ws_client.send_command("START_TASK", task_description=task_goal)
        self.run_button.setText("运行中...")
        self.run_button.setEnabled(False)

    def handle_agent_message(self, data: dict):
        """处理来自 WebSocket 后端的 Agent 状态更新。"""
        msg_type = data.get("type")
        level = data.get("level", "INFO")
        
        if msg_type == "STATUS":
            self.log_system_message(data.get("message", "Unknown status message"), level)
            
            # 当 Agent 任务结束或失败时，重置 UI
            if "finished" in data.get("message", "").lower() or level == "ERROR":
                self._reset_ui_to_ready()
                
        elif msg_type == "NODE_UPDATE":
            status = data.get("status", "UNKNOWN")
            log_msg = f"Node {data.get('node_id')}: Tool '{data.get('tool')}' Status: {status}"
            # ... (日志内容省略，保持与原代码一致)
            if data.get("url"):
                log_msg += f" URL: {data.get('url')}"
            if data.get("error_message"):
                log_msg += f" Error: {data.get('error_message')}"
            
            self.log_system_message(log_msg, status)
            
        elif msg_type == "VISUALIZATION":
            # 不再使用 QWebEngineView 渲染，而是显示 HTML 源码
            html_content = data.get("html", "<h1>No visualization data received.</h1>")
            # 仅显示开头，避免显示过多内容
            self.graph_viewer.setPlainText(f"--- Visualization HTML Source ---\n\n{html_content[:500]}...")
            self.log_system_message("Visualization HTML Source received (Visualization is disabled).", "REPORT")
            
    def _reset_ui_to_ready(self):
        """将 UI 恢复到可接受新任务的状态。"""
        # 仅在连接状态下重置为“启动”
        if self.run_button.text() != "连接失败":
            self.run_button.setText("启动")
            self.run_button.setEnabled(True)
            
    def closeEvent(self, event):
        """关闭应用时安全退出线程和连接。"""
        if self.ws_client.websocket and self.ws_client.websocket.isValid():
             self.ws_client.websocket.close()
        self.ws_thread.quit()
        self.ws_thread.wait()
        super().closeEvent(event)


if __name__ == "__main__":
    
    # 彻底移除所有 GPU/ANGLE/CHROMIUM 相关的环境变量设置，防止干扰。
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())