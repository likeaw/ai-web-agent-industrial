import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Tag, Tooltip } from 'antd'
import { ExecutionNodeStatus } from '../../types'
import './CustomNode.css'

interface CustomNodeData {
  label: string
  status: ExecutionNodeStatus
  priority: number
  reasoning: string
  confidence: number
  statusColor: string
  isSelected: boolean
  node: any
}

function CustomNode({ data }: NodeProps<CustomNodeData>) {
  const { label, status, priority, confidence, statusColor, isSelected } = data

  const getStatusText = (status: ExecutionNodeStatus) => {
    const statusMap: Record<ExecutionNodeStatus, string> = {
      [ExecutionNodeStatus.PENDING]: '等待',
      [ExecutionNodeStatus.RUNNING]: '运行中',
      [ExecutionNodeStatus.SUCCESS]: '成功',
      [ExecutionNodeStatus.FAILED]: '失败',
      [ExecutionNodeStatus.PRUNED]: '已剪枝',
      [ExecutionNodeStatus.SKIPPED]: '已跳过',
    }
    return statusMap[status] || status
  }

  return (
    <div className={`custom-node ${isSelected ? 'selected' : ''}`}>
      <Handle type="target" position={Position.Top} />
      <div className="node-content">
        <div className="node-header">
          <span className="node-label">{label}</span>
          <Tag color={statusColor} style={{ margin: 0 }}>
            {getStatusText(status)}
          </Tag>
        </div>
        <div className="node-info">
          <span className="info-item">优先级: P{priority}</span>
          <Tooltip title={`置信度: ${(confidence * 100).toFixed(1)}%`}>
            <span className="info-item">置信度: {(confidence * 100).toFixed(0)}%</span>
          </Tooltip>
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

export default memo(CustomNode)

