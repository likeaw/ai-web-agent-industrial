import { Layout, Space, Switch, Badge, Tooltip } from 'antd'
import { ThunderboltOutlined, ApiOutlined, GlobalOutlined } from '@ant-design/icons'
import { useTaskStore } from '../../store/useTaskStore'
import './Header.css'

const { Header: AntHeader } = Layout

export default function Header() {
  const { isConnected } = useTaskStore()

  return (
    <AntHeader className="app-header">
      <div className="header-left">
        <Space>
          <ThunderboltOutlined className="logo-icon" />
          <span className="logo-text">AI Web Agent Industrial</span>
        </Space>
      </div>
      <div className="header-right">
        <Space size="large">
          <Tooltip title={isConnected ? 'WebSocket 已连接' : 'WebSocket 未连接'}>
            <Badge status={isConnected ? 'success' : 'error'} text="WebSocket" />
          </Tooltip>
          <Space>
            <GlobalOutlined />
            <span>浏览器模式:</span>
            <Switch
              checkedChildren="无头"
              unCheckedChildren="可见"
              defaultChecked={false}
              disabled
            />
          </Space>
          <Space>
            <ApiOutlined />
            <span>运行模式:</span>
            <Switch
              checkedChildren="前端"
              unCheckedChildren="命令行"
              defaultChecked={true}
              disabled
            />
          </Space>
        </Space>
      </div>
    </AntHeader>
  )
}

