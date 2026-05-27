import { Card, Row, Col, Statistic, Progress, Table, Tag, Select, DatePicker, Space } from 'antd'
import { LineChartOutlined, DollarOutlined, ClockCircleOutlined, AlertOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { useState } from 'react'
import './MonitorPage.css'

const mockLogs = [
  { timestamp: '2026-05-15 10:00:00', level: 'INFO', service: 'agent', message: '意图识别完成', intent: 'query_score', confidence: 0.95 },
  { timestamp: '2026-05-15 09:59:55', level: 'INFO', service: 'rag', message: 'RAG检索完成', results_count: 5 },
  { timestamp: '2026-05-15 09:59:50', level: 'WARNING', service: 'cost', message: 'Token使用率达80%', daily_ratio: 0.8 },
  { timestamp: '2026-05-15 09:59:45', level: 'ERROR', service: 'graph', message: 'Neo4j连接超时', error: 'Connection timeout' },
]

export default function MonitorPage() {
  const [timeRange, setTimeRange] = useState('7d')

  const tokenChartOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['Token消耗', '请求次数'], textStyle: { color: '#94A3B8' } },
    xAxis: { type: 'category', data: ['05-09', '05-10', '05-11', '05-12', '05-13', '05-14', '05-15'], axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94A3B8' } },
    yAxis: [
      { type: 'value', name: 'Token', axisLine: { lineStyle: { color: '#334155' } }, splitLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94A3B8' } },
      { type: 'value', name: '请求', axisLine: { lineStyle: { color: '#334155' } }, splitLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94A3B8' } },
    ],
    series: [
      { name: 'Token消耗', type: 'line', data: [8200, 9320, 9010, 12340, 12930, 13300, 15200], smooth: true, areaStyle: { color: 'rgba(59, 130, 246, 0.2)' }, lineStyle: { color: '#3B82F6' } },
      { name: '请求次数', type: 'line', yAxisIndex: 1, data: [120, 135, 128, 156, 178, 192, 210], smooth: true, lineStyle: { color: '#10B981' } },
    ],
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  }

  const costDistOption = {
    tooltip: { trigger: 'item' },
    legend: { data: ['gpt-4-turbo', 'gpt-3.5-turbo'], textStyle: { color: '#94A3B8' } },
    series: [{
      type: 'pie', radius: ['40%', '70%'],
      data: [
        { value: 335, name: 'gpt-4-turbo', itemStyle: { color: '#3B82F6' } },
        { value: 234, name: 'gpt-3.5-turbo', itemStyle: { color: '#10B981' } },
      ],
      label: { color: '#94A3B8' },
    }],
  }

  const columns = [
    { title: '时间', dataIndex: 'timestamp', key: 'timestamp', width: 180 },
    { title: '级别', dataIndex: 'level', key: 'level', render: (level: string) => <Tag color={level === 'ERROR' ? 'red' : level === 'WARNING' ? 'orange' : 'blue'}>{level}</Tag> },
    { title: '服务', dataIndex: 'service', key: 'service' },
    { title: '消息', dataIndex: 'message', key: 'message' },
  ]

  return (
    <div className="monitor-page">
      <div className="page-header">
        <h1>监控中心</h1>
        <Space>
          <Select value={timeRange} onChange={setTimeRange} options={[{ value: '7d', label: '近7天' }, { value: '30d', label: '近30天' }]} />
          <DatePicker.RangePicker />
        </Space>
      </div>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}><Card className="glass-card"><Statistic title="Token消耗" value={75600} prefix={<LineChartOutlined />} suffix="Tokens" /></Card></Col>
        <Col span={6}><Card className="glass-card"><Statistic title="预估成本" value={2.38} prefix={<DollarOutlined />} suffix="USD" precision={2} /></Card></Col>
        <Col span={6}><Card className="glass-card"><Statistic title="日均请求" value={168} prefix={<ClockCircleOutlined />} /></Card></Col>
        <Col span={6}><Card className="glass-card"><Statistic title="异常告警" value={1} prefix={<AlertOutlined />} valueStyle={{ color: '#F59E0B' }} /></Card></Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={16}>
          <Card className="glass-card" title="Token消耗趋势">
            <ReactECharts option={tokenChartOption} style={{ height: 300 }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card className="glass-card" title="模型使用分布">
            <ReactECharts option={costDistOption} style={{ height: 300 }} />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card className="glass-card" title="Token预算状态">
            <div className="budget-item"><span>日预算 (10,000)</span><Progress percent={76} strokeColor="#3B82F6" /></div>
            <div className="budget-item"><span>月预算 (300,000)</span><Progress percent={25} strokeColor="#10B981" /></div>
            <div style={{ marginTop: 16 }}>
              <Tag color="success">正常</Tag>
              <span style={{ color: '#94A3B8', marginLeft: 8 }}>当前消耗在预算范围内</span>
            </div>
          </Card>
        </Col>
        <Col span={8}>
          <Card className="glass-card" title="意图分布">
            <div className="intent-item"><span>task_create</span><Progress percent={25} size="small" strokeColor="#3B82F6" /></div>
            <div className="intent-item"><span>complex_reasoning</span><Progress percent={40} size="small" strokeColor="#10B981" /></div>
            <div className="intent-item"><span>query_score</span><Progress percent={15} size="small" strokeColor="#F59E0B" /></div>
            <div className="intent-item"><span>rag_search</span><Progress percent={20} size="small" strokeColor="#8B5CF6" /></div>
          </Card>
        </Col>
        <Col span={8}>
          <Card className="glass-card" title="服务健康">
            <div className="health-item"><span>Agent</span><Tag color="success">健康</Tag></div>
            <div className="health-item"><span>RAG</span><Tag color="success">健康</Tag></div>
            <div className="health-item"><span>Graph</span><Tag color="warning">亚健康</Tag></div>
            <div className="health-item"><span>Database</span><Tag color="success">健康</Tag></div>
          </Card>
        </Col>
      </Row>

      <Card className="glass-card" title="实时日志">
        <Table columns={columns} dataSource={mockLogs} rowKey="timestamp" pagination={false} size="small" />
      </Card>
    </div>
  )
}
