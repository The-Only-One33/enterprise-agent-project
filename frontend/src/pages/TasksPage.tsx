import { useState } from 'react'
import { Card, Table, Tag, Button, Input, Select, Badge, Modal, Form, DatePicker, Space } from 'antd'
import { PlusOutlined, SearchOutlined, FilterOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import './TasksPage.css'

interface Task {
  id: number
  title: string
  description: string
  status: 'pending' | 'in_progress' | 'review' | 'completed'
  priority: 'low' | 'medium' | 'high' | 'urgent'
  project: { id: number; name: string }
  assignee: { id: number; name: string }
  dueDate: string
  score?: number
}

const mockTasks: Task[] = [
  { id: 1, title: '完成需求文档', description: '撰写项目A的需求规格说明书', status: 'in_progress', priority: 'high', project: { id: 1, name: '智能协同平台' }, assignee: { id: 1, name: '张三' }, dueDate: '2026-05-20', score: undefined },
  { id: 2, title: '代码评审', description: '对模块B进行代码评审', status: 'pending', priority: 'medium', project: { id: 1, name: '智能协同平台' }, assignee: { id: 2, name: '李四' }, dueDate: '2026-05-18', score: 85.5 },
  { id: 3, title: '前端开发', description: '完成用户界面开发', status: 'review', priority: 'high', project: { id: 1, name: '智能协同平台' }, assignee: { id: 1, name: '张三' }, dueDate: '2026-05-22', score: 88 },
  { id: 4, title: '单元测试', description: '编写核心模块单元测试', status: 'completed', priority: 'medium', project: { id: 2, name: '知识图谱建设' }, assignee: { id: 3, name: '王五' }, dueDate: '2026-05-10', score: 92 },
  { id: 5, title: '性能优化', description: '系统性能调优', status: 'pending', priority: 'urgent', project: { id: 1, name: '智能协同平台' }, assignee: { id: 2, name: '李四' }, dueDate: '2026-05-16', score: undefined },
]

const statusMap = {
  pending: { color: 'default', text: '待处理' },
  in_progress: { color: 'processing', text: '进行中' },
  review: { color: 'warning', text: '待审核' },
  completed: { color: 'success', text: '已完成' },
}

const priorityMap = {
  low: { color: 'default', text: '低' },
  medium: { color: 'blue', text: '中' },
  high: { color: 'orange', text: '高' },
  urgent: { color: 'red', text: '紧急' },
}

export default function TasksPage() {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [form] = Form.useForm()

  const columns: ColumnsType<Task> = [
    { title: '任务名称', dataIndex: 'title', key: 'title', render: (text: string) => <a href="#">{text}</a> },
    { title: '状态', dataIndex: 'status', key: 'status', render: status => <Badge status={(statusMap as Record<string, {color: string; text: string}>)[status]?.color as any} text={(statusMap as Record<string, {color: string; text: string}>)[status]?.text} /> },
    { title: '优先级', dataIndex: 'priority', key: 'priority', render: priority => <Tag color={(priorityMap as Record<string, {color: string; text: string}>)[priority]?.color}>{(priorityMap as Record<string, {color: string; text: string}>)[priority]?.text}</Tag> },
    { title: '所属项目', dataIndex: 'project', key: 'project', render: project => project.name },
    { title: '负责人', dataIndex: 'assignee', key: 'assignee', render: assignee => assignee.name },
    { title: '截止日期', dataIndex: 'dueDate', key: 'dueDate' },
    { title: '评分', dataIndex: 'score', key: 'score', render: score => score ? <span style={{ color: score >= 90 ? '#10B981' : score >= 80 ? '#3B82F6' : '#F59E0B' }}>{score}分</span> : '-' },
    { title: '操作', key: 'action', render: () => <Button type="link" size="small">详情</Button> },
  ]

  const stats = [
    { title: '待处理', value: 2, color: '#94A3B8' },
    { title: '进行中', value: 1, color: '#3B82F6' },
    { title: '待审核', value: 1, color: '#F59E0B' },
    { title: '已完成', value: 1, color: '#10B981' },
  ]

  return (
    <div className="tasks-page">
      <div className="page-header">
        <h1>任务中心</h1>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setIsModalOpen(true)}>创建任务</Button>
      </div>

      <div className="stats-cards">
        {stats.map(stat => (
          <Card key={stat.title} className="stat-card glass-card">
            <div className="stat-value" style={{ color: stat.color }}>{stat.value}</div>
            <div className="stat-label">{stat.title}</div>
          </Card>
        ))}
      </div>

      <Card className="filter-card glass-card">
        <Space wrap>
          <Input placeholder="搜索任务..." prefix={<SearchOutlined />} style={{ width: 200 }} />
          <Select placeholder="状态" style={{ width: 120 }} options={[{ value: 'all', label: '全部' }, { value: 'pending', label: '待处理' }, { value: 'in_progress', label: '进行中' }]} />
          <Select placeholder="优先级" style={{ width: 120 }} options={[{ value: 'all', label: '全部' }, { value: 'high', label: '高' }, { value: 'medium', label: '中' }]} />
          <Button icon={<FilterOutlined />}>更多筛选</Button>
        </Space>
      </Card>

      <Card className="glass-card">
        <Table columns={columns} dataSource={mockTasks} rowKey="id" pagination={{ pageSize: 10 }} />
      </Card>

      <Modal title="创建任务" open={isModalOpen} onCancel={() => setIsModalOpen(false)} footer={null}>
        <Form form={form} layout="vertical">
          <Form.Item label="任务名称" name="title" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Space>
            <Form.Item label="优先级" name="priority">
              <Select options={[{ value: 'low', label: '低' }, { value: 'medium', label: '中' }, { value: 'high', label: '高' }, { value: 'urgent', label: '紧急' }]} />
            </Form.Item>
            <Form.Item label="截止日期" name="dueDate">
              <DatePicker />
            </Form.Item>
          </Space>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">创建</Button>
              <Button onClick={() => setIsModalOpen(false)}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
