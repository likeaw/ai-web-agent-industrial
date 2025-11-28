# 文件: websocket_test.py (新增了 5 秒超时)
import websocket
import time
import sys

ws = websocket.WebSocket()
print("Attempting connection...")
# 设置 5 秒超时
ws.settimeout(5) 
try:
    ws.connect("ws://127.0.0.1:8000/ws/agent/monitor")
    print("\n--- TEST SUCCESS: CONNECTION ESTABLISHED ---")
    ws.send('{"client_id": "ExternalTest"}')
    time.sleep(1)
    ws.close()
    print("Test complete.")
except websocket.WebSocketTimeoutException:
    print("\n!!! TEST FAILED: Connection timed out after 5 seconds. 这是典型的防火墙/网络阻断行为。")
except Exception as e:
    print(f"\n!!! TEST FAILED: Connection refused or failed: {type(e).__name__}: {e}")