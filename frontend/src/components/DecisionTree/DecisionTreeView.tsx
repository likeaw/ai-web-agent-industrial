import { useEffect, useCallback } from 'react'
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  NodeTypes,
  useNodesState,
  useEdgesState,
  Connection,
  addEdge,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { useTaskStore } from '../../store/useTaskStore'
import { ExecutionNodeStatus } from '../../types'
import CustomNode from './CustomNode'
import './DecisionTreeView.css'

const nodeTypes: NodeTypes = {
  custom: CustomNode,
}

export default function DecisionTreeView() {
  const { currentTask, selectedNodeId, setSelectedNodeId } = useTaskStore()
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])

  const getStatusColor = (status: ExecutionNodeStatus) => {
    switch (status) {
      case ExecutionNodeStatus.SUCCESS:
        return '#52c41a'
      case ExecutionNodeStatus.RUNNING:
        return '#faad14'
      case ExecutionNodeStatus.FAILED:
        return '#ff4d4f'
      case ExecutionNodeStatus.PENDING:
        return '#1890ff'
      case ExecutionNodeStatus.PRUNED:
        return '#8c8c8c'
      case ExecutionNodeStatus.SKIPPED:
        return '#d9d9d9'
      default:
        return '#1890ff'
    }
  }

  const buildGraph = useCallback(() => {
    if (!currentTask || !currentTask.nodes) {
      setNodes([])
      setEdges([])
      return
    }

    const taskNodes: Node[] = []
    const taskEdges: Edge[] = []

    Object.values(currentTask.nodes).forEach((node) => {
      const statusColor = getStatusColor(node.current_status)
      const isSelected = selectedNodeId === node.node_id

      taskNodes.push({
        id: node.node_id,
        type: 'custom',
        position: { x: 0, y: 0 },
        data: {
          label: node.action.tool_name,
          status: node.current_status,
          priority: node.execution_order_priority,
          reasoning: node.action.reasoning,
          confidence: node.action.confidence_score,
          statusColor,
          isSelected,
          node,
        },
        style: {
          border: isSelected ? '3px solid #1890ff' : `2px solid ${statusColor}`,
          borderRadius: '8px',
          background: '#fff',
          width: 200,
          padding: 10,
        },
      })

      if (node.parent_id && currentTask.nodes[node.parent_id]) {
        taskEdges.push({
          id: `${node.parent_id}-${node.node_id}`,
          source: node.parent_id,
          target: node.node_id,
          label: `P${node.execution_order_priority}`,
          style: { stroke: statusColor },
        })
      }
    })

    // 简单的布局算法（层次布局）
    if (taskNodes.length > 0 && currentTask.root_node_id) {
      const layoutedNodes = layoutNodes(taskNodes, taskEdges, currentTask.root_node_id)
      setNodes(layoutedNodes)
    } else {
      setNodes(taskNodes)
    }
    setEdges(taskEdges)
  }, [currentTask, selectedNodeId, setNodes, setEdges])

  useEffect(() => {
    buildGraph()
  }, [buildGraph])

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  )

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedNodeId(node.id)
    },
    [setSelectedNodeId]
  )

  if (!currentTask) {
    return (
      <div className="empty-tree">
        <p>暂无任务执行数据</p>
        <p className="hint">请在对话面板中创建新任务</p>
      </div>
    )
  }

  return (
    <div className="decision-tree-view">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        attributionPosition="bottom-left"
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  )
}

// 简单的层次布局算法
function layoutNodes(nodes: Node[], edges: Edge[], rootId: string): Node[] {
  const nodeMap = new Map(nodes.map((n) => [n.id, n]))
  const childrenMap = new Map<string, string[]>()
  const levels = new Map<string, number>()

  // 构建子节点映射
  edges.forEach((edge) => {
    if (!childrenMap.has(edge.source)) {
      childrenMap.set(edge.source, [])
    }
    childrenMap.get(edge.source)!.push(edge.target)
  })

  // 计算每个节点的层级
  const calculateLevel = (nodeId: string): number => {
    if (levels.has(nodeId)) {
      return levels.get(nodeId)!
    }
    const node = nodeMap.get(nodeId)
    if (!node) return 0
    if (!node.data.node.parent_id) {
      levels.set(nodeId, 0)
      return 0
    }
    const level = calculateLevel(node.data.node.parent_id) + 1
    levels.set(nodeId, level)
    return level
  }

  nodes.forEach((node) => {
    calculateLevel(node.id)
  })

  // 按层级分组
  const nodesByLevel = new Map<number, Node[]>()
  nodes.forEach((node) => {
    const level = levels.get(node.id) || 0
    if (!nodesByLevel.has(level)) {
      nodesByLevel.set(level, [])
    }
    nodesByLevel.get(level)!.push(node)
  })

  // 布局
  const layoutedNodes: Node[] = []
  const levelWidth = 300
  const nodeHeight = 150

  nodesByLevel.forEach((levelNodes, level) => {
    const y = level * nodeHeight
    const totalWidth = levelNodes.length * levelWidth
    const startX = -totalWidth / 2

    levelNodes.forEach((node, index) => {
      layoutedNodes.push({
        ...node,
        position: {
          x: startX + index * levelWidth,
          y,
        },
      })
    })
  })

  return layoutedNodes
}

