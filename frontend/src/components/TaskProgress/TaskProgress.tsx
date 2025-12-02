import { Progress, Card, Space, Tag } from 'antd'
import { useTaskStore } from '../../store/useTaskStore'
import { ExecutionNodeStatus } from '../../types'
import './TaskProgress.css'

export default function TaskProgress() {
  const { currentTask } = useTaskStore()

  if (!currentTask) {
    return null
  }

  const nodes = Object.values(currentTask.nodes || {})
  const totalNodes = nodes.length
  const completedNodes = nodes.filter(
    (n) => n.current_status === ExecutionNodeStatus.SUCCESS
  ).length
  const runningNodes = nodes.filter(
    (n) => n.current_status === ExecutionNodeStatus.RUNNING
  ).length
  const failedNodes = nodes.filter(
    (n) => n.current_status === ExecutionNodeStatus.FAILED
  ).length
  const pendingNodes = nodes.filter(
    (n) => n.current_status === ExecutionNodeStatus.PENDING
  ).length

  const progressPercent =
    totalNodes > 0 ? Math.round((completedNodes / totalNodes) * 100) : 0

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'success'
      case 'running':
        return 'processing'
      case 'failed':
        return 'error'
      default:
        return 'default'
    }
  }

  return (
    <Card
      title="任务进度"
      size="small"
      className="task-progress-card"
      extra={
        <Tag color={getStatusColor(currentTask.status)}>
          {currentTask.status === 'completed'
            ? '已完成'
            : currentTask.status === 'running'
            ? '运行中'
            : currentTask.status === 'failed'
            ? '失败'
            : '待执行'}
        </Tag>
      }
    >
      <Space direction="vertical" style={{ width: '100%' }} size="small">
        <Progress
          percent={progressPercent}
          status={
            currentTask.status === 'failed'
              ? 'exception'
              : currentTask.status === 'completed'
              ? 'success'
              : 'active'
          }
          strokeColor={{
            '0%': '#108ee9',
            '100%': '#87d068',
          }}
        />
        <div className="progress-stats">
          <Space split="|" size="small">
            <span>总计: {totalNodes}</span>
            <span style={{ color: '#52c41a' }}>完成: {completedNodes}</span>
            <span style={{ color: '#faad14' }}>运行中: {runningNodes}</span>
            <span style={{ color: '#ff4d4f' }}>失败: {failedNodes}</span>
            <span style={{ color: '#1890ff' }}>等待: {pendingNodes}</span>
          </Space>
        </div>
        {currentTask.start_time && (
          <div className="progress-time">
            开始时间: {new Date(currentTask.start_time).toLocaleString()}
          </div>
        )}
        {currentTask.end_time && (
          <div className="progress-time">
            结束时间: {new Date(currentTask.end_time).toLocaleString()}
          </div>
        )}
      </Space>
    </Card>
  )
}

