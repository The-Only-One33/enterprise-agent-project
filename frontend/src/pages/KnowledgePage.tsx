import {
  Card,
  Input,
  Table,
  Tag,
  Button,
  Space,
  Row,
  Col,
  Modal,
  Form,
  Tree,
  Select,
  message,
  Spin,
  Typography,
} from 'antd'
import { PlusOutlined, SearchOutlined, FileTextOutlined, FolderOutlined, ReloadOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { DataNode } from 'antd/es/tree'
import ReactECharts from 'echarts-for-react'
import {
  knowledgeApi,
  type KnowledgeDocument,
  type KnowledgeCreatePayload,
} from '../services/chatApi'
import './KnowledgePage.css'

const { Text } = Typography

const DEFAULT_TENANT = 'TENANT_DEFAULT'

interface DocumentFormValues {
  title: string
  content: string
  category?: string
  tags?: string[]
}

const graphData = {
  nodes: [
    { name: '智能协同平台', category: 0 },
    { name: '张三', category: 1 },
    { name: '李四', category: 1 },
    { name: '任务管理', category: 2 },
    { name: 'Agent开发', category: 2 },
  ],
  links: [
    { source: '张三', target: '智能协同平台' },
    { source: '李四', target: '智能协同平台' },
    { source: '任务管理', target: '智能协同平台' },
    { source: 'Agent开发', target: '智能协同平台' },
  ],
  categories: [{ name: '项目' }, { name: '人员' }, { name: '任务' }],
}

function buildTreeData(documents: KnowledgeDocument[]): DataNode[] {
  const byCategory = new Map<string, KnowledgeDocument[]>()
  for (const doc of documents) {
    const cat = doc.category?.trim() || '未分类'
    if (!byCategory.has(cat)) byCategory.set(cat, [])
    byCategory.get(cat)!.push(doc)
  }

  return Array.from(byCategory.entries()).map(([category, docs], idx) => ({
    title: category,
    key: `cat-${idx}`,
    icon: <FolderOutlined />,
    children: docs.map((d) => ({
      title: d.title,
      key: d.doc_id,
      icon: <FileTextOutlined />,
      isLeaf: true,
    })),
  }))
}

export default function KnowledgePage() {
  const [form] = Form.useForm<DocumentFormValues>()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('documents')
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [chunkCount, setChunkCount] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [searchInput, setSearchInput] = useState('')

  const loadDocuments = useCallback(async (searchKeyword?: string) => {
    setLoading(true)
    try {
      const [listRes, statsRes] = await Promise.all([
        knowledgeApi.list(searchKeyword),
        knowledgeApi.stats(),
      ])
      setDocuments(listRes.documents)
      setChunkCount(statsRes.chunk_count)
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined
      message.error(detail || '加载知识库失败，请确认后端已启动')
      setDocuments([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (activeTab === 'documents') {
      loadDocuments(keyword || undefined)
    }
  }, [activeTab, keyword, loadDocuments])

  const handleSearch = () => {
    setKeyword(searchInput.trim())
  }

  const handleOpenModal = () => {
    form.resetFields()
    setIsModalOpen(true)
  }

  const handleCloseModal = () => {
    setIsModalOpen(false)
    form.resetFields()
  }

  const handleSave = async (values: DocumentFormValues) => {
    setSaving(true)
    const payload: KnowledgeCreatePayload = {
      title: values.title.trim(),
      content: values.content.trim(),
      tenant_id: DEFAULT_TENANT,
      source_type: 'manual',
      doc_type: 'manual',
      category: values.category?.trim() || '',
      tags: values.tags || [],
    }

    try {
      const result = await knowledgeApi.create(payload)
      message.success(`已入库：${result.title}（${result.chunk_count} 个片段）`)
      handleCloseModal()
      await loadDocuments(keyword || undefined)
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined
      message.error(detail || '保存失败，请检查内容与网络')
    } finally {
      setSaving(false)
    }
  }

  const treeData = useMemo(() => buildTreeData(documents), [documents])

  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 120,
      render: (c: string) => (c ? <Tag color="blue">{c}</Tag> : <Text type="secondary">未分类</Text>),
    },
    {
      title: '类型',
      dataIndex: 'doc_type',
      key: 'doc_type',
      width: 100,
      render: (t: string) => <Tag>{t || 'manual'}</Tag>,
    },
    {
      title: '文档 ID',
      dataIndex: 'doc_id',
      key: 'doc_id',
      width: 180,
      ellipsis: true,
      render: (id: string) => <Text copyable={{ text: id }}>{id}</Text>,
    },
  ]

  const chartOption = {
    tooltip: { trigger: 'item', triggerOn: 'mousemove' },
    legend: { data: graphData.categories.map((c) => c.name), textStyle: { color: '#94A3B8' } },
    series: [
      {
        type: 'graph',
        layout: 'force',
        data: graphData.nodes.map((n) => ({ name: n.name, category: n.category })),
        links: graphData.links.map((l) => ({ source: l.source, target: l.target })),
        categories: graphData.categories,
        roam: true,
        label: { show: true, color: '#fff' },
        lineStyle: { color: '#334155' },
        emphasis: { focus: 'adjacency' },
        force: { repulsion: 100 },
      },
    ],
  }

  return (
    <div className="knowledge-page">
      <div className="page-header">
        <h1>知识图谱</h1>
        <Space>
          <Button type={activeTab === 'documents' ? 'primary' : 'default'} onClick={() => setActiveTab('documents')}>
            文档库
          </Button>
          <Button type={activeTab === 'graph' ? 'primary' : 'default'} onClick={() => setActiveTab('graph')}>
            关系图谱
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleOpenModal}>
            添加文档
          </Button>
        </Space>
      </div>

      {activeTab === 'documents' && (
        <Row gutter={16}>
          <Col span={6}>
            <Card
              className="glass-card"
              title="文档目录"
              extra={
                chunkCount != null ? (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {chunkCount} chunks
                  </Text>
                ) : null
              }
            >
              <Spin spinning={loading}>
                {treeData.length > 0 ? (
                  <Tree treeData={treeData} defaultExpandAll showIcon />
                ) : (
                  <Text type="secondary">暂无文档，点击右上角添加</Text>
                )}
              </Spin>
            </Card>
          </Col>
          <Col span={18}>
            <Card className="glass-card">
              <Space style={{ marginBottom: 16 }}>
                <Input
                  placeholder="搜索文档标题..."
                  prefix={<SearchOutlined />}
                  style={{ width: 300 }}
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  onPressEnter={handleSearch}
                  allowClear
                  onClear={() => {
                    setSearchInput('')
                    setKeyword('')
                  }}
                />
                <Button type="primary" onClick={handleSearch}>
                  搜索
                </Button>
                <Button icon={<ReloadOutlined />} onClick={() => loadDocuments(keyword || undefined)}>
                  刷新
                </Button>
              </Space>
              <Table
                columns={columns}
                dataSource={documents}
                rowKey="doc_id"
                loading={loading}
                pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 篇` }}
              />
            </Card>
          </Col>
        </Row>
      )}

      {activeTab === 'graph' && (
        <Card className="glass-card">
          <ReactECharts option={chartOption} style={{ height: 600 }} />
        </Card>
      )}

      <Modal
        title="添加文档"
        open={isModalOpen}
        onCancel={handleCloseModal}
        footer={null}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item
            label="标题"
            name="title"
            rules={[{ required: true, message: '请输入标题' }, { max: 200, message: '标题过长' }]}
          >
            <Input placeholder="例如：任务创建操作指南" />
          </Form.Item>
          <Form.Item label="分类" name="category">
            <Input placeholder="例如：任务管理、制度文件" />
          </Form.Item>
          <Form.Item label="标签" name="tags">
            <Select mode="tags" placeholder="输入后回车添加标签" tokenSeparators={[',']} />
          </Form.Item>
          <Form.Item
            label="内容"
            name="content"
            rules={[{ required: true, message: '请输入正文' }, { min: 10, message: '内容至少 10 个字符' }]}
          >
            <Input.TextArea rows={8} placeholder="支持 Markdown 正文，保存后将自动分块并写入向量库" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={saving}>
                保存并入库
              </Button>
              <Button onClick={handleCloseModal}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
