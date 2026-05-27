import { Layout, Input, Badge, Avatar, Dropdown, Space, MenuProps } from 'antd'
import {
  SearchOutlined,
  BellOutlined,
  UserOutlined,
  SettingOutlined,
  LogoutOutlined,
} from '@ant-design/icons'
import './Header.css'

const { Header: AntHeader } = Layout

export default function Header() {
  const userMenuItems: MenuProps['items'] = [
    { key: 'profile', icon: <UserOutlined />, label: '个人中心' },
    { key: 'settings', icon: <SettingOutlined />, label: '系统设置' },
    { type: 'divider' },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录' },
  ]

  return (
    <AntHeader className="header">
      <div className="header-left">
        <Input
          placeholder="搜索任务、项目、知识..."
          prefix={<SearchOutlined />}
          className="search-input"
        />
      </div>
      <div className="header-right">
        <Badge count={3} size="small">
          <BellOutlined className="header-icon" />
        </Badge>
        <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
          <Space className="user-info">
            <Avatar size={36} icon={<UserOutlined />} />
            <span className="user-name">系统管理员</span>
          </Space>
        </Dropdown>
      </div>
    </AntHeader>
  )
}
