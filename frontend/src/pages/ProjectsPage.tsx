import { Card, Progress, Tag, Button, Row, Col, Descriptions, Table } from 'antd'
import { PlusOutlined, TeamOutlined, CheckCircleOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import ReactECharts from 'echarts-for-react'
import './ProjectsPage.css'

interface Project {
  id: number
  name: string
  description: string
  status: string
  progress: number
  owner: { id: number; name: string }
  taskCount: number
  memberCount: number
}

const mockProjects: Project[] = [
  { id: 1, name: '智能协同平台', description: '企业级智能任务协同Agent系统', status: 'active', progress: 45, owner: { id: 1, name: '张三' }, taskCount: 12, memberCount: 5 },
  { id: 2, name: '知识图谱建设', description: '构建企业知识图谱', status: 'active', progress: 30, owner: { id: 2, name: '李四' }, taskCount: 8, memberCount: 3 },
  { id: 3, name: '数据中台', description: '企业数据统一管理平台', status: 'active', progress: 60, owner: { id: 1, name: '张三' }, taskCount: 15, memberCount: 4 },
]

export default function ProjectsPage() {
  const columns: ColumnsType<any> = [
    { title: '任务', dataIndex: 'title', key: 'title' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => <Tag color={s === 'completed' ? 'success' : 'processing'}>{s === 'completed' ? '已完成' : '进行中'}</Tag> },
    { title: '负责人', dataIndex: 'assignee', key: 'assignee' },
  ]

  const chartOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['已完成', '进行中', '待处理'], textStyle: { color: '#94A3B8' } },
    xAxis: { type: 'category', data: ['智能协同平台', '知识图谱建设', '数据中台'], axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94A3B8' } },
    yAxis: { type: 'value', axisLine: { lineStyle: { color: '#334155' } }, splitLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94A3B8' } },
    series: [
      { name: '已完成', type: 'bar', data: [5, 3, 8], itemStyle: { color: '#10B981' } },
      { name: '进行中', type: 'bar', data: [4, 3, 5], itemStyle: { color: '#3B82F6' } },
      { name: '待处理', type: 'bar', data: [3, 2, 2], itemStyle: { color: '#94A3B8' } },
    ],
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  }

  return (
    <div className="projects-page">
      <div className="page-header">
        <h1>项目管理</h1>
        <Button type="primary" icon={<PlusOutlined />}>创建项目</Button>
      </div>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={16}>
          <Card className="glass-card" title="项目进度概览">
            <ReactECharts option={chartOption} style={{ height: 300 }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card className="glass-card" title="团队协作统计">
            <div className="team-stats">
              <div className="team-stat"><TeamOutlined /><span>总项目数: <strong>3</strong></span></div>
              <div className="team-stat"><CheckCircleOutlined /><span>进行中: <strong>3</strong></span></div>
              <div className="team-stat"><CheckCircleOutlined /><span>已完成: <strong>0</strong></span></div>
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        {mockProjects.map(project => (
          <Col span={8} key={project.id} style={{ marginBottom: 16 }}>
            <Card className="project-card glass-card" hoverable>
              <div className="project-header">
                <h3>{project.name}</h3>
                <Tag color={project.status === 'active' ? 'processing' : 'default'}>{project.status === 'active' ? '进行中' : '已结束'}</Tag>
              </div>
              <p className="project-desc">{project.description}</p>
              <Progress percent={project.progress} strokeColor="#3B82F6" />
              <Descriptions size="small" column={1} className="project-meta">
                <Descriptions.Item label="负责人">{project.owner.name}</Descriptions.Item>
                <Descriptions.Item label="任务/成员">{project.taskCount} / {project.memberCount}</Descriptions.Item>
              </Descriptions>
            </Card>
          </Col>
        ))}
      </Row>

      <Card className="glass-card" title="项目任务看板" style={{ marginTop: 16 }}>
        <Table columns={columns} dataSource={[
          { key: '1', title: '需求文档', status: 'completed', assignee: '张三' },
          { key: '2', title: '代码开发', status: 'in_progress', assignee: '李四' },
        ]} pagination={false} />
      </Card>
    </div>
  )
}
