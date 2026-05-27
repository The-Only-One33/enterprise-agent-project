import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from 'antd'
import Sidebar from './components/Layout/Sidebar'
import Header from './components/Layout/Header'
import ChatPage from './pages/ChatPage'
import TasksPage from './pages/TasksPage'
import ProjectsPage from './pages/ProjectsPage'
import KnowledgePage from './pages/KnowledgePage'
import MonitorPage from './pages/MonitorPage'
import './App.css'

const { Content } = Layout

function App() {
  return (
    <Layout className="app-layout">
      <Sidebar />
      <Layout className="main-layout">
        <Header />
        <Content className="content">
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/tasks" element={<TasksPage />} />
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/knowledge" element={<KnowledgePage />} />
            <Route path="/monitor" element={<MonitorPage />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  )
}

export default App
