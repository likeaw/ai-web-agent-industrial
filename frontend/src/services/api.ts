import axios from 'axios'
import { TaskGoal, TaskExecution } from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export const taskApi = {
  createTask: async (description: string, headless: boolean = false) => {
    const response = await api.post<TaskExecution>('/tasks', {
      description,
      headless,
    })
    return response.data
  },

  getTask: async (taskId: string) => {
    const response = await api.get<TaskExecution>(`/tasks/${taskId}`)
    return response.data
  },

  listTasks: async () => {
    const response = await api.get<{ tasks: TaskExecution[] }>('/tasks')
    return response.data.tasks
  },

  stopTask: async (taskId: string) => {
    const response = await api.post(`/tasks/${taskId}/stop`)
    return response.data
  },

  getBrowserScreenshot: async (taskId: string) => {
    const response = await api.get(`/tasks/${taskId}/screenshot`, {
      responseType: 'blob',
    })
    return URL.createObjectURL(response.data)
  },

  getBrowserCDPUrl: async (taskId: string) => {
    const response = await api.get<{ url: string; status: string; message?: string }>(`/tasks/${taskId}/cdp-url`)
    return response.data
  },
}

export default api

