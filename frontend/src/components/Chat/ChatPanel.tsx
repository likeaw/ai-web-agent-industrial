import { useState, useRef, useEffect } from 'react'
import { Input, Button, Space, Card, Radio, message } from 'antd'
import { SendOutlined, RobotOutlined, UserOutlined } from '@ant-design/icons'
import { useTaskStore } from '../../store/useTaskStore'
import { taskApi } from '../../services/api'
import { wsService } from '../../services/websocket'
import './ChatPanel.css'

const { TextArea } = Input

interface Message {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: string
}

export default function ChatPanel() {
  const { currentTask, setCurrentTask, clearLogs } = useTaskStore()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [runMode, setRunMode] = useState<'frontend' | 'cli'>('frontend')
  const [headless, setHeadless] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      if (runMode === 'frontend') {
        // 前端模式：通过API创建任务并连接WebSocket
        const task = await taskApi.createTask(input, headless)
        
        if (!task || !task.task_uuid) {
          throw new Error('API返回的数据格式不正确')
        }
        
        setCurrentTask(task)
        clearLogs()

        // 连接WebSocket
        wsService.connect(task.task_uuid)

        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          type: 'assistant',
          content: `任务已创建: ${task.task_uuid}\n任务描述: ${task.goal?.target_description || input}`,
          timestamp: new Date().toISOString(),
        }
        setMessages((prev) => [...prev, assistantMessage])
      } else {
        // CLI模式：提示用户使用命令行
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          type: 'assistant',
          content: 'CLI模式已选择。请使用命令行工具运行任务。\n\n提示：运行 `run_agent.cmd` 并选择选项 1 来启动CLI。',
          timestamp: new Date().toISOString(),
        }
        setMessages((prev) => [...prev, assistantMessage])
        message.info('CLI模式：请在命令行中执行任务')
      }
    } catch (error: any) {
      console.error('创建任务失败:', error)
      const errorMsg = error.response?.data?.detail || error.message || '未知错误'
      message.error(`创建任务失败: ${errorMsg}`)
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: `错误: ${errorMsg}\n\n请检查：\n1. API服务器是否正在运行（http://localhost:8000）\n2. 网络连接是否正常\n3. 查看浏览器控制台获取详细错误信息`,
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <Space>
          <span>运行模式:</span>
          <Radio.Group
            value={runMode}
            onChange={(e) => setRunMode(e.target.value)}
            size="small"
          >
            <Radio.Button value="frontend">前端</Radio.Button>
            <Radio.Button value="cli">命令行</Radio.Button>
          </Radio.Group>
          {runMode === 'frontend' && (
            <>
              <span>浏览器:</span>
              <Radio.Group
                value={headless}
                onChange={(e) => setHeadless(e.target.value)}
                size="small"
              >
                <Radio.Button value={false}>可见</Radio.Button>
                <Radio.Button value={true}>无头</Radio.Button>
              </Radio.Group>
            </>
          )}
        </Space>
      </div>
      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <p>开始与 AI Agent 对话</p>
            <p className="hint">输入任务描述，例如：</p>
            <ul>
              <li>打开百度搜索 合肥，提取前三条搜索结果标题</li>
              <li>在桌面创建一个名为 test 的文件夹</li>
              <li>创建一个 Word 文档，标题为'报告'</li>
            </ul>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`chat-message ${msg.type === 'user' ? 'user' : 'assistant'}`}
            >
              <div className="message-avatar">
                {msg.type === 'user' ? (
                  <UserOutlined />
                ) : (
                  <RobotOutlined />
                )}
              </div>
              <Card className="message-card" size="small">
                <div className="message-content">{msg.content}</div>
                <div className="message-time">
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </div>
              </Card>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className="chat-input">
        <Space.Compact style={{ width: '100%' }}>
          <TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            placeholder="输入任务描述..."
            autoSize={{ minRows: 2, maxRows: 4 }}
            disabled={loading}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            loading={loading}
            disabled={!input.trim()}
          >
            发送
          </Button>
        </Space.Compact>
      </div>
    </div>
  )
}

