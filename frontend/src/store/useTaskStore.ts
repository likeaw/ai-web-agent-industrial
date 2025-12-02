import { create } from 'zustand'
import { TaskExecution, LogEntry, ExecutionNode } from '../types'

interface TaskStore {
  currentTask: TaskExecution | null
  logs: LogEntry[]
  selectedNodeId: string | null
  browserViewUrl: string | null
  isConnected: boolean
  
  setCurrentTask: (task: TaskExecution | null) => void
  updateNode: (nodeId: string, updates: Partial<ExecutionNode>) => void
  addLog: (log: LogEntry) => void
  clearLogs: () => void
  setSelectedNodeId: (nodeId: string | null) => void
  setBrowserViewUrl: (url: string | null) => void
  setConnected: (connected: boolean) => void
}

export const useTaskStore = create<TaskStore>((set) => ({
  currentTask: null,
  logs: [],
  selectedNodeId: null,
  browserViewUrl: null,
  isConnected: false,

  setCurrentTask: (task) => set({ currentTask: task }),
  
  updateNode: (nodeId, updates) => set((state) => {
    if (!state.currentTask) return state
    const nodes = { ...state.currentTask.nodes }
    if (nodes[nodeId]) {
      nodes[nodeId] = { ...nodes[nodeId], ...updates }
    }
    return {
      currentTask: {
        ...state.currentTask,
        nodes,
      },
    }
  }),

  addLog: (log) => set((state) => ({
    logs: [...state.logs, log],
  })),

  clearLogs: () => set({ logs: [] }),

  setSelectedNodeId: (nodeId) => set({ selectedNodeId: nodeId }),
  
  setBrowserViewUrl: (url) => set({ browserViewUrl: url }),
  
  setConnected: (connected) => set({ isConnected: connected }),
}))

