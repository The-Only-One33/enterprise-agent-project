import { Layout, Menu } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  RobotOutlined,
  CheckCircleOutlined,
  ProjectOutlined,
  BookOutlined,
  DashboardOutlined,
} from '@ant-design/icons'
import './Sidebar.css'

const { Sider } = Layout

const menuItems = [
  { key: '/chat', icon: <RobotOutlined />, label: '智能对话' },
  { key: '/tasks', icon: <CheckCircleOutlined />, label: '任务中心' },
  { key: '/projects', icon: <ProjectOutlined />, label: '项目管理' },
  { key: '/knowledge', icon: <BookOutlined />, label: '知识图谱' },
  { key: '/monitor', icon: <DashboardOutlined />, label: '监控中心' },
]

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <Sider className="sidebar" width={240}>
      <div className="logo">
        <RobotOutlined className="logo-icon" />
        <span className="logo-text">协同Agent</span>
      </div>
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[location.pathname]}
        items={menuItems}
        onClick={({ key }) => navigate(key)}
        className="sidebar-menu"
      />
    </Sider>
  )
}
