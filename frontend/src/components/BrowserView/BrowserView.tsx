import { useEffect, useState, useRef, useCallback } from 'react'
import { Spin, Empty, Button, Space } from 'antd'
import { ReloadOutlined, FullscreenOutlined } from '@ant-design/icons'
import { useTaskStore } from '../../store/useTaskStore'
import { taskApi } from '../../services/api'
import './BrowserView.css'

interface BrowserViewProps {
  compact?: boolean
}

export default function BrowserView({ compact = false }: BrowserViewProps) {
  const { currentTask, browserViewUrl, setBrowserViewUrl } = useTaskStore()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const iframeRef = useRef<HTMLIFrameElement>(null)

  const loadBrowserView = useCallback(async () => {
    if (!currentTask) return

    setLoading(true)
    setError(null)

    try {
      // 获取浏览器视图URL
      const result = await taskApi.getBrowserCDPUrl(currentTask.task_uuid)
      
      if (result.status === 'waiting') {
        // 浏览器正在初始化，等待后重试
        setTimeout(() => {
          if (currentTask?.task_uuid) {
            loadBrowserView()
          }
        }, 2000)
        setError('浏览器正在初始化，请稍候...')
        setLoading(false)
        return
      }

      if (result.status === 'completed') {
        // 任务已完成，仍然可以显示截图
        setLoading(false)
      }

      if (result.url) {
        // 使用完整的URL（包含协议和主机）
        const fullUrl = result.url.startsWith('http') 
          ? result.url 
          : `${window.location.protocol}//${window.location.host}${result.url}`
        setBrowserViewUrl(fullUrl)
        setError(null) // 清除之前的错误
      } else if (result.status !== 'waiting') {
        setError('无法获取浏览器视图URL')
      }
    } catch (err: any) {
      console.error('加载浏览器视图失败:', err)
      const errorMsg = err.response?.data?.detail || err.message || '无法加载浏览器视图'
      setError(errorMsg)
      
      // 如果是400错误（浏览器未初始化），等待后重试
      if (err.response?.status === 400 && currentTask?.task_uuid) {
        setTimeout(() => {
          if (currentTask?.task_uuid) {
            loadBrowserView()
          }
        }, 2000)
      }
    } finally {
      setLoading(false)
    }
  }, [currentTask, setBrowserViewUrl])

  useEffect(() => {
    if (currentTask?.task_uuid) {
      loadBrowserView()
    }
    
    // 定期刷新截图
    let refreshInterval: NodeJS.Timeout | null = null
    if (currentTask?.task_uuid && browserViewUrl && browserViewUrl.includes('/screenshot')) {
      refreshInterval = setInterval(() => {
        const timestamp = Date.now()
        const newUrl = browserViewUrl.split('?')[0] + `?t=${timestamp}`
        setBrowserViewUrl(newUrl)
      }, 2000) // 每2秒刷新一次
    }
    
    return () => {
      if (refreshInterval) {
        clearInterval(refreshInterval)
      }
    }
  }, [currentTask?.task_uuid, browserViewUrl, loadBrowserView, setBrowserViewUrl])

  if (!currentTask) {
    return (
      <div className={`browser-view ${compact ? 'compact' : ''}`}>
        <Empty
          description="暂无浏览器视图"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      </div>
    )
  }

  if (loading) {
    return (
      <div className={`browser-view ${compact ? 'compact' : ''} loading`}>
        <Spin size="large" tip="加载浏览器视图..." />
      </div>
    )
  }

  if (error) {
    return (
      <div className={`browser-view ${compact ? 'compact' : ''} error`}>
        <Empty
          description={error}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Button type="primary" icon={<ReloadOutlined />} onClick={loadBrowserView}>
            重试
          </Button>
        </Empty>
      </div>
    )
  }

  return (
    <div className={`browser-view ${compact ? 'compact' : ''}`}>
      <div className="browser-view-header">
        <Space>
          <span className="browser-url">{browserViewUrl || '无URL'}</span>
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={loadBrowserView}
          >
            刷新
          </Button>
          {!compact && (
            <Button
              size="small"
              icon={<FullscreenOutlined />}
              onClick={() => {
                if (iframeRef.current?.requestFullscreen) {
                  iframeRef.current.requestFullscreen()
                }
              }}
            >
              全屏
            </Button>
          )}
        </Space>
      </div>
      <div className="browser-view-content">
        {browserViewUrl ? (
          browserViewUrl.includes('/screenshot') ? (
            // 截图模式：使用img标签并定期刷新
            <img
              src={browserViewUrl}
              alt="Browser Screenshot"
              className="browser-screenshot"
              onError={(e) => {
                console.error('Failed to load screenshot:', e)
                // 错误时重试
                setTimeout(() => {
                  loadBrowserView()
                }, 2000)
              }}
            />
          ) : (
            // CDP模式：使用iframe
            <iframe
              ref={iframeRef}
              src={browserViewUrl}
              className="browser-iframe"
              title="Browser View"
              sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
            />
          )
        ) : (
          <Empty description="浏览器视图不可用" />
        )}
      </div>
    </div>
  )
}

