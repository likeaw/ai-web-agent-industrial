import { Layout, Tabs } from 'antd'
import { useState } from 'react'
import Header from './Header'
import TaskPanel from '../TaskPanel/TaskPanel'
import DecisionTreeView from '../DecisionTree/DecisionTreeView'
import BrowserView from '../BrowserView/BrowserView'
import ChatPanel from '../Chat/ChatPanel'
import LogPanel from '../Log/LogPanel'
import TaskProgress from '../TaskProgress/TaskProgress'
import './MainLayout.css'

const { Content, Sider } = Layout

export default function MainLayout() {
  const [activeTab, setActiveTab] = useState('chat')

  return (
    <Layout className="main-layout">
      <Header />
      <Layout>
        <Sider width={400} className="left-sider" theme="light">
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={[
              {
                key: 'chat',
                label: '💬 对话',
                children: <ChatPanel />,
              },
              {
                key: 'tasks',
                label: '📋 任务',
                children: <TaskPanel />,
              },
              {
                key: 'logs',
                label: '📝 日志',
                children: <LogPanel />,
              },
            ]}
            className="left-tabs"
          />
        </Sider>
        <Content className="main-content">
          <Layout style={{ height: '100%' }}>
            <Content className="center-content">
              <Tabs
                defaultActiveKey="tree"
                items={[
                  {
                    key: 'tree',
                    label: '🌳 决策树',
                    children: <DecisionTreeView />,
                  },
                  {
                    key: 'browser',
                    label: '🌐 浏览器视图',
                    children: <BrowserView />,
                  },
                ]}
                className="center-tabs"
              />
            </Content>
            <Sider width={350} className="right-sider" theme="light">
              <div style={{ padding: '16px', height: '100%', overflow: 'auto' }}>
                <TaskProgress />
                <BrowserView compact />
              </div>
            </Sider>
          </Layout>
        </Content>
      </Layout>
    </Layout>
  )
}

