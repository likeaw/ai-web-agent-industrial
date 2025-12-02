import { useTaskStore } from '../store/useTaskStore'
import { ExecutionNode, LogEntry } from '../types'

class WebSocketService {
  private socket: WebSocket | null = null
  private taskId: string | null = null
  private reconnectTimer: NodeJS.Timeout | null = null

  connect(taskId: string) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.disconnect()
    }

    this.taskId = taskId
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.hostname}:8000/ws`
    
    try {
      this.socket = new WebSocket(wsUrl)

      this.socket.onopen = () => {
        console.log('WebSocket connected')
        useTaskStore.getState().setConnected(true)
        // 发送加入任务的消息
        this.send({
          event: 'join_task',
          task_uuid: taskId,
        })
      }

      this.socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          this.handleMessage(message)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      this.socket.onerror = (error) => {
        console.error('WebSocket error:', error)
        useTaskStore.getState().setConnected(false)
        useTaskStore.getState().addLog({
          id: Date.now().toString(),
          timestamp: new Date().toISOString(),
          level: 'error',
          message: 'WebSocket连接错误',
        })
      }

      this.socket.onclose = () => {
        console.log('WebSocket disconnected')
        useTaskStore.getState().setConnected(false)
        // 尝试重连
        if (this.taskId) {
          this.reconnectTimer = setTimeout(() => {
            if (this.taskId) {
              this.connect(this.taskId)
            }
          }, 3000)
        }
      }
    } catch (error) {
      console.error('Failed to create WebSocket:', error)
      useTaskStore.getState().setConnected(false)
    }
  }

  private send(data: any) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(data))
    }
  }

  private handleMessage(message: any) {
    const { event, data } = message

    switch (event) {
      case 'node_update':
        if (data?.node) {
          useTaskStore.getState().updateNode(data.node.node_id, data.node)
        }
        break

      case 'log':
        if (data) {
          useTaskStore.getState().addLog(data as LogEntry)
        }
        break

      case 'task_update':
        if (data?.task) {
          useTaskStore.getState().setCurrentTask(data.task)
        }
        break

      case 'browser_url':
        if (data?.url) {
          useTaskStore.getState().setBrowserViewUrl(data.url)
        }
        break

      case 'pong':
        // 心跳响应
        break

      default:
        console.log('Unknown WebSocket event:', event)
    }
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.socket) {
      this.socket.close()
      this.socket = null
      this.taskId = null
      useTaskStore.getState().setConnected(false)
    }
  }

  isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN || false
  }
}

export const wsService = new WebSocketService()

