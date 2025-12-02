import { useEffect, useState } from 'react'
import { List, Card, Tag, Button, Space, Empty, Spin } from 'antd'
import { PlayCircleOutlined, StopOutlined, ReloadOutlined } from '@ant-design/icons'
import { useTaskStore } from '../../store/useTaskStore'
import { taskApi } from '../../services/api'
import { TaskExecution } from '../../types'
import './TaskPanel.css'

export default function TaskPanel() {
  const { currentTask, setCurrentTask } = useTaskStore()
  const [tasks, setTasks] = useState<TaskExecution[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadTasks()
  }, [])

  const loadTasks = async () => {
    setLoading(true)
    try {
      const taskList = await taskApi.listTasks()
      setTasks(taskList)
    } catch (error) {
      console.error('Failed to load tasks:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSelectTask = (task: TaskExecution) => {
    setCurrentTask(task)
  }

  const handleStopTask = async (taskId: string) => {
    try {
      await taskApi.stopTask(taskId)
      await loadTasks()
    } catch (error) {
      console.error('Failed to stop task:', error)
    }
  }

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

  if (loading) {
    return (
      <div className="task-panel-loading">
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div className="task-panel">
      <div className="task-panel-header">
        <Space>
          <span>任务列表</span>
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={loadTasks}
          >
            刷新
          </Button>
        </Space>
      </div>
      <div className="task-panel-content">
        {tasks.length === 0 ? (
          <Empty description="暂无任务" />
        ) : (
          <List
            dataSource={tasks}
            renderItem={(task) => (
              <List.Item>
                <Card
                  size="small"
                  className={currentTask?.task_uuid === task.task_uuid ? 'selected' : ''}
                  onClick={() => handleSelectTask(task)}
                  hoverable
                >
                  <div className="task-card-content">
                    <div className="task-header">
                      <Space>
                        <Tag color={getStatusColor(task.status)}>
                          {task.status}
                        </Tag>
                        <span className="task-id">{task.task_uuid}</span>
                      </Space>
                      {task.status === 'running' && (
                        <Button
                          size="small"
                          danger
                          icon={<StopOutlined />}
                          onClick={(e) => {
                            e.stopPropagation()
                            handleStopTask(task.task_uuid)
                          }}
                        >
                          停止
                        </Button>
                      )}
                    </div>
                    <div className="task-description">
                      {task.goal.target_description}
                    </div>
                    <div className="task-meta">
                      <span>节点数: {Object.keys(task.nodes || {}).length}</span>
                      {task.start_time && (
                        <span>
                          开始: {new Date(task.start_time).toLocaleString()}
                        </span>
                      )}
                    </div>
                  </div>
                </Card>
              </List.Item>
            )}
          />
        )}
      </div>
    </div>
  )
}

