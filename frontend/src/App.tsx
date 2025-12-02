import { Layout } from 'antd'
import { useState } from 'react'
import MainLayout from './components/Layout/MainLayout'
import './App.css'

function App() {
  return (
    <Layout style={{ height: '100vh', overflow: 'hidden' }}>
      <MainLayout />
    </Layout>
  )
}

export default App

