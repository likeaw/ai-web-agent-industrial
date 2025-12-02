import { useEffect, useRef } from 'react'
import { List, Tag, Empty } from 'antd'
import { useTaskStore } from '../../store/useTaskStore'
import './LogPanel.css'

export default function LogPanel() {
  const { logs, clearLogs } = useTaskStore()
  const logsEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const getLogColor = (level: string) => {
    switch (level) {
      case 'error':
        return 'red'
      case 'warning':
        return 'orange'
      case 'success':
        return 'green'
      default:
        return 'blue'
    }
  }

  return (
    <div className="log-panel">
      <div className="log-panel-header">
        <span>执行日志</span>
        <span className="log-count">共 {logs.length} 条</span>
      </div>
      <div className="log-panel-content">
        {logs.length === 0 ? (
          <Empty description="暂无日志" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <List
            dataSource={logs}
            renderItem={(log) => (
              <List.Item className="log-item">
                <div className="log-content">
                  <div className="log-header">
                    <Tag color={getLogColor(log.level)}>{log.level}</Tag>
                    <span className="log-time">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </span>
                    {log.node_id && (
                      <span className="log-node-id">节点: {log.node_id}</span>
                    )}
                  </div>
                  <div className="log-message">{log.message}</div>
                </div>
              </List.Item>
            )}
          />
        )}
        <div ref={logsEndRef} />
      </div>
    </div>
  )
}

