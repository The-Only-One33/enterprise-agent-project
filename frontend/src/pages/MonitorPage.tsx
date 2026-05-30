import { useCallback, useEffect, useMemo, useState } from 'react'
import { Card, Row, Col, Statistic, Progress, Table, Tag, Select, Spin, Alert } from 'antd'
import { LineChartOutlined, DollarOutlined, ClockCircleOutlined, AlertOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import {
  monitorApi,
  type MonitorActivityItem,
  type TokenBudgetStatus,
  type UsageReport,
} from '../services/chatApi'
import './MonitorPage.css'

const levelTag: Record<string, { color: string; text: string }> = {
  normal: { color: 'success', text: '正常' },
  warning: { color: 'warning', text: '预警' },
  critical: { color: 'error', text: '严重' },
}

export default function MonitorPage() {
  const [timeRange, setTimeRange] = useState('7d')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [budget, setBudget] = useState<TokenBudgetStatus | null>(null)
  const [report, setReport] = useState<UsageReport | null>(null)
  const [costDist, setCostDist] = useState<{
    by_intent: { intent: string; tokens: number; percentage: number }[]
    by_model: { model: string; tokens: number; percentage: number }[]
  } | null>(null)
  const [activity, setActivity] = useState<MonitorActivityItem[]>([])

  const days = timeRange === '30d' ? 30 : 7

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [budgetRes, reportRes, distRes, activityRes] = await Promise.all([
        monitorApi.getTokenBudget(),
        monitorApi.getUsageReport(days),
        monitorApi.getCostDistribution(days),
        monitorApi.getRecentActivity(20),
      ])
      setBudget(budgetRes)
      setReport(reportRes)
      setCostDist(distRes)
      setActivity(activityRes.items || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载监控数据失败')
    } finally {
      setLoading(false)
    }
  }, [days])

  useEffect(() => {
    loadData()
  }, [loadData])

  const tokenChartOption = useMemo(() => {
    const breakdown = report?.daily_breakdown || []
    return {
      tooltip: { trigger: 'axis' as const },
      legend: { data: ['Token消耗', '请求次数'], textStyle: { color: '#94A3B8' } },
      xAxis: {
        type: 'category' as const,
        data: breakdown.map(d => d.date.slice(5)),
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94A3B8' },
      },
      yAxis: [
        {
          type: 'value' as const,
          name: 'Token',
          axisLine: { lineStyle: { color: '#334155' } },
          splitLine: { lineStyle: { color: '#334155' } },
          axisLabel: { color: '#94A3B8' },
        },
        {
          type: 'value' as const,
          name: '请求',
          axisLine: { lineStyle: { color: '#334155' } },
          splitLine: { lineStyle: { color: '#334155' } },
          axisLabel: { color: '#94A3B8' },
        },
      ],
      series: [
        {
          name: 'Token消耗',
          type: 'line' as const,
          data: breakdown.map(d => d.tokens),
          smooth: true,
          areaStyle: { color: 'rgba(59, 130, 246, 0.2)' },
          lineStyle: { color: '#3B82F6' },
        },
        {
          name: '请求次数',
          type: 'line' as const,
          yAxisIndex: 1,
          data: breakdown.map(d => d.requests),
          smooth: true,
          lineStyle: { color: '#10B981' },
        },
      ],
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    }
  }, [report])

  const costDistOption = useMemo(() => {
    const byModel = costDist?.by_model || []
    return {
      tooltip: { trigger: 'item' as const },
      legend: { data: byModel.map(m => m.model), textStyle: { color: '#94A3B8' } },
      series: [
        {
          type: 'pie' as const,
          radius: ['40%', '70%'],
          data: byModel.map((m, i) => ({
            value: m.tokens,
            name: m.model,
            itemStyle: { color: ['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6'][i % 4] },
          })),
          label: { color: '#94A3B8' },
        },
      ],
    }
  }, [costDist])

  const columns = [
    { title: '时间', dataIndex: 'timestamp', key: 'timestamp', width: 180 },
    {
      title: '级别',
      dataIndex: 'level',
      key: 'level',
      render: (level: string) => (
        <Tag color={level === 'ERROR' ? 'red' : level === 'WARNING' ? 'orange' : 'blue'}>{level}</Tag>
      ),
    },
    { title: '服务', dataIndex: 'service', key: 'service' },
    { title: '消息', dataIndex: 'message', key: 'message' },
  ]

  const dailyLimit = budget?.daily?.limit ?? 10000
  const monthlyLimit = budget?.monthly?.limit ?? 300000
  const dailyPercent = Math.min(100, Math.round((budget?.daily_ratio ?? 0) * 100))
  const monthlyPercent = Math.min(100, Math.round((budget?.monthly_ratio ?? 0) * 100))
  const budgetLevel = budget?.level ?? 'normal'

  if (loading && !report) {
    return (
      <div className="monitor-page" style={{ textAlign: 'center', padding: 80 }}>
        <Spin size="large" tip="加载监控数据..." />
      </div>
    )
  }

  return (
    <div className="monitor-page">
      <div className="page-header">
        <h1>监控中心</h1>
        <Select
          value={timeRange}
          onChange={setTimeRange}
          options={[
            { value: '7d', label: '近7天' },
            { value: '30d', label: '近30天' },
          ]}
        />
      </div>

      {error && <Alert type="warning" message={error} showIcon style={{ marginBottom: 16 }} closable />}

      {report?.data_source === 'unavailable' && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="MySQL 未连接或暂无数据"
          description="请配置 backend/.env 的 MYSQL_*，执行 python scripts/init_mysql_db.py 后重启后端；与 Agent 对话后会写入 token_usage_log。"
        />
      )}

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card className="glass-card">
            <Statistic title="Token消耗" value={report?.total_tokens ?? 0} prefix={<LineChartOutlined />} suffix="Tokens" />
          </Card>
        </Col>
        <Col span={6}>
          <Card className="glass-card">
            <Statistic title="预估成本" value={report?.total_cost ?? 0} prefix={<DollarOutlined />} suffix="USD" precision={4} />
          </Card>
        </Col>
        <Col span={6}>
          <Card className="glass-card">
            <Statistic title={`${days}日总请求`} value={report?.total_requests ?? 0} prefix={<ClockCircleOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card className="glass-card">
            <Statistic
              title="预算告警"
              value={budgetLevel === 'normal' ? 0 : 1}
              prefix={<AlertOutlined />}
              valueStyle={{ color: budgetLevel === 'normal' ? '#10B981' : '#F59E0B' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={16}>
          <Card className="glass-card" title="Token消耗趋势">
            <ReactECharts option={tokenChartOption} style={{ height: 300 }} notMerge />
          </Card>
        </Col>
        <Col span={8}>
          <Card className="glass-card" title="模型使用分布">
            {costDist?.by_model?.length ? (
              <ReactECharts option={costDistOption} style={{ height: 300 }} notMerge />
            ) : (
              <div style={{ color: '#94A3B8', padding: 48, textAlign: 'center' }}>暂无模型用量</div>
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card className="glass-card" title="Token预算状态">
            <div className="budget-item">
              <span>日预算 ({dailyLimit.toLocaleString()})</span>
              <Progress percent={dailyPercent} strokeColor="#3B82F6" />
            </div>
            <div className="budget-item">
              <span>月预算 ({monthlyLimit.toLocaleString()})</span>
              <Progress percent={monthlyPercent} strokeColor="#10B981" />
            </div>
            <div style={{ marginTop: 16 }}>
              <Tag color={levelTag[budgetLevel]?.color}>{levelTag[budgetLevel]?.text}</Tag>
              <span style={{ color: '#94A3B8', marginLeft: 8 }}>
                {budget?.db_available !== false ? '数据来自 MySQL' : '数据库未连接'}
              </span>
            </div>
          </Card>
        </Col>
        <Col span={8}>
          <Card className="glass-card" title="意图分布">
            {(costDist?.by_intent || []).map(item => (
              <div key={item.intent} className="intent-item">
                <span>{item.intent}</span>
                <Progress percent={Math.round(item.percentage)} size="small" strokeColor="#3B82F6" />
              </div>
            ))}
            {!costDist?.by_intent?.length && <div style={{ color: '#94A3B8' }}>暂无意图统计</div>}
          </Card>
        </Col>
        <Col span={8}>
          <Card className="glass-card" title="服务健康">
            <div className="health-item">
              <span>MySQL</span>
              <Tag color={budget?.db_available !== false ? 'success' : 'warning'}>
                {budget?.db_available !== false ? '已连接' : '未连接'}
              </Tag>
            </div>
            <div className="health-item">
              <span>数据源</span>
              <Tag color="blue">{report?.data_source || '-'}</Tag>
            </div>
          </Card>
        </Col>
      </Row>

      <Card className="glass-card" title="最近 LLM 调用记录">
        <Table
          columns={columns}
          dataSource={activity}
          rowKey={(r, i) => `${r.timestamp}-${i}`}
          pagination={false}
          size="small"
          locale={{ emptyText: '暂无记录，请先进行 Agent 对话' }}
        />
      </Card>
    </div>
  )
}
