import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
})

export interface ReasoningStep {
  step: string
  thought: string
  action: string
}

export interface Source {
  type: 'rag' | 'graph' | 'db'
  content: string
  score?: number
}

export interface AgentResponse {
  type: string
  response?: string
  intent: string
  confidence: number
  routing_target: string
  reasoning_steps: ReasoningStep[]
  sources?: Source[]
  conversation_id?: number
}

// 澄清响应接口
export interface ClarificationResponse {
  type: 'clarification'
  clarification_question: string
  conversation_id: number
  reasoning_steps: ReasoningStep[]
  clarification_type?: 'intent' | 'slot' | 'plan'
  missing_slots?: string[]
}

export interface Conversation {
  id: number
  title: string
  message_count: number
  created_at: string
  updated_at: string
}

export interface AgentStreamMeta {
  intent: string
  confidence: number
  routing_target: string
  reasoning_steps: ReasoningStep[]
  conversation_id?: number
  resolved_query?: string
  /** 周报等 Planner 导出路径，如 data/exports/weekly_xxx.md */
  export_path?: string | null
}

/** 从 export_path 拼下载 URL（仅文件名传给后端） */
export function weeklyExportDownloadUrl(exportPath: string): string {
  const filename = exportPath.split('/').filter(Boolean).pop() || exportPath
  return `${API_BASE_URL}/agent/exports/${encodeURIComponent(filename)}`
}

/** 流式读超时（单次 read 无新数据） */
export const STREAM_READ_TIMEOUT_MS = 60_000

export type StreamInterruptReason = 'timeout' | 'disconnect'

export class StreamInterruptedError extends Error {
  readonly reason: StreamInterruptReason

  constructor(message: string, reason: StreamInterruptReason) {
    super(message)
    this.name = 'StreamInterruptedError'
    this.reason = reason
  }
}

export interface AgentStreamHandlers {
  onToken: (delta: string) => void
  onClarification?: (data: ClarificationResponse) => void
  onMeta?: (meta: AgentStreamMeta) => void
  onDone?: () => void
  onError?: (message: string) => void
  /** 连接结束但未收到 done，或读超时 */
  onInterrupted?: (message: string, reason: StreamInterruptReason) => void
}

function readStreamChunkWithTimeout(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  timeoutMs: number,
  signal?: AbortSignal,
): Promise<ReadableStreamReadResult<Uint8Array>> {
  if (signal?.aborted) {
    return Promise.reject(new DOMException('The operation was aborted.', 'AbortError'))
  }

  return new Promise((resolve, reject) => {
    let settled = false

    const timer = window.setTimeout(() => {
      if (settled) return
      settled = true
      reject(
        new StreamInterruptedError(
          '长时间未收到数据，连接可能已超时',
          'timeout',
        ),
      )
    }, timeoutMs)

    const onAbort = () => {
      if (settled) return
      settled = true
      window.clearTimeout(timer)
      reject(new DOMException('The operation was aborted.', 'AbortError'))
    }

    signal?.addEventListener('abort', onAbort, { once: true })

    reader.read().then(
      result => {
        if (settled) return
        settled = true
        window.clearTimeout(timer)
        signal?.removeEventListener('abort', onAbort)
        resolve(result)
      },
      err => {
        if (settled) return
        settled = true
        window.clearTimeout(timer)
        signal?.removeEventListener('abort', onAbort)
        reject(err)
      },
    )
  })
}

/** 解析 SSE 文本块 */
function parseSseBlock(block: string): { event: string; data: string } | null {
  const lines = block.trim().split('\n')
  if (!lines.length) return null
  let event = 'message'
  const dataLines: string[] = []
  for (const line of lines) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (!dataLines.length) return null
  return { event, data: dataLines.join('\n') }
}

// 对话 API - 返回类型可能是 AgentResponse 或 ClarificationResponse
export const chatApi = {
  // 与 Agent 对话（非流式，保留兼容）
  chat: (message: string, conversationId?: number): Promise<AgentResponse | ClarificationResponse> =>
    apiClient.post<AgentResponse | ClarificationResponse>('/agent/chat', { 
      message,
      conversation_id: conversationId,
    }).then(res => res.data),

  /** SSE 流式对话：token 事件交给调用方写入接收缓冲 */
  chatStream: async (
    message: string,
    conversationId: number | undefined,
    handlers: AgentStreamHandlers,
    signal?: AbortSignal,
    readTimeoutMs: number = STREAM_READ_TIMEOUT_MS,
  ): Promise<void> => {
    const res = await fetch(`${API_BASE_URL}/agent/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
      }),
      signal,
    })

    if (!res.ok) {
      let detail = res.statusText
      try {
        const err = await res.json()
        detail = err.detail || detail
      } catch {
        /* ignore */
      }
      throw new Error(detail)
    }

    const reader = res.body?.getReader()
    if (!reader) throw new Error('浏览器不支持流式响应')

    const decoder = new TextDecoder()
    let buffer = ''
    let receivedDoneEvent = false

    const dispatch = (block: string) => {
      const parsed = parseSseBlock(block)
      if (!parsed) return
      let payload: Record<string, unknown> = {}
      try {
        payload = JSON.parse(parsed.data) as Record<string, unknown>
      } catch {
        return
      }

      switch (parsed.event) {
        case 'token':
          handlers.onToken(String(payload.delta ?? ''))
          break
        case 'clarification':
          handlers.onClarification?.(payload as unknown as ClarificationResponse)
          break
        case 'meta':
          handlers.onMeta?.(payload as unknown as AgentStreamMeta)
          break
        case 'error':
          handlers.onError?.(String(payload.message ?? '流式请求失败'))
          break
        case 'done':
          receivedDoneEvent = true
          handlers.onDone?.()
          break
        default:
          break
      }
    }

    try {
      while (true) {
        const { done, value } = await readStreamChunkWithTimeout(
          reader,
          readTimeoutMs,
          signal,
        )
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''
        for (const part of parts) dispatch(part)
      }

      if (buffer.trim()) dispatch(buffer)

      if (!receivedDoneEvent) {
        handlers.onInterrupted?.(
          '连接已断开，生成可能未完成',
          'disconnect',
        )
      }
    } catch (err) {
      throw err
    } finally {
      try {
        await reader.cancel()
      } catch {
        /* ignore */
      }
    }
  },

  // 获取对话列表
  getConversations: (): Promise<{ conversations: Conversation[]; total: number }> =>
    apiClient.get<{ conversations: Conversation[]; total: number }>('/chat/conversations').then(res => res.data),

  // 创建新对话
  createConversation: (title?: string): Promise<{ id: number; title: string }> =>
    apiClient.post('/chat/conversations', { title }).then(res => res.data),

  // 获取消息历史
  getMessages: (conversationId: number): Promise<{ messages: any[] }> =>
    apiClient.get(`/chat/conversations/${conversationId}/messages`).then(res => res.data),
}

// 任务 API
export const taskApi = {
  list: (status?: string) => apiClient.get('/tasks/', { params: { status } }).then(res => res.data),
  get: (id: number) => apiClient.get(`/tasks/${id}`).then(res => res.data),
  create: (data: any) => apiClient.post('/tasks/', data).then(res => res.data),
}

// 项目 API
export const projectApi = {
  list: (status?: string) => apiClient.get('/projects/', { params: { status } }).then(res => res.data),
  get: (id: number) => apiClient.get(`/projects/${id}`).then(res => res.data),
  create: (data: any) => apiClient.post('/projects/', data).then(res => res.data),
}

// 监控 API
export interface TokenBudgetStatus {
  level: 'normal' | 'warning' | 'critical'
  daily: { used: number; limit: number }
  monthly: { used: number; limit: number }
  daily_ratio: number
  monthly_ratio: number
  db_available?: boolean
}

export interface UsageReportDay {
  date: string
  tokens: number
  cost: number
  requests: number
}

export interface UsageReport {
  period: string
  total_tokens: number
  total_cost: number
  total_requests: number
  daily_breakdown: UsageReportDay[]
  data_source?: 'mysql' | 'unavailable'
}

export interface CostDistribution {
  by_intent: { intent: string; tokens: number; percentage: number }[]
  by_model: { model: string; tokens: number; percentage: number }[]
}

export interface MonitorActivityItem {
  timestamp: string
  level: string
  service: string
  message: string
}

export const monitorApi = {
  getTokenBudget: () =>
    apiClient.get<TokenBudgetStatus>('/monitor/token-budget').then(res => res.data),
  getUsageReport: (days?: number) =>
    apiClient.get<UsageReport>('/monitor/usage-report', { params: { days } }).then(res => res.data),
  getCostDistribution: (days?: number) =>
    apiClient.get<CostDistribution>('/monitor/cost-distribution', { params: { days } }).then(res => res.data),
  getRecentActivity: (limit?: number) =>
    apiClient
      .get<{ items: MonitorActivityItem[] }>('/monitor/recent-activity', { params: { limit } })
      .then(res => res.data),
}

// 知识库 API
export interface KnowledgeDocument {
  doc_id: string
  title: string
  doc_type?: string
  category?: string
  tenant_id?: string
}

export interface KnowledgeCreatePayload {
  title: string
  content: string
  tags?: string[]
  source_type?: string
  tenant_id?: string
  doc_type?: string
  category?: string
}

export interface KnowledgeCreateResponse {
  doc_id: string
  chunk_count: number
  chunk_ids: string[]
  title: string
}

export const knowledgeApi = {
  list: (keyword?: string) =>
    apiClient
      .get<{ documents: KnowledgeDocument[]; total: number }>('/knowledge/', {
        params: keyword ? { keyword } : undefined,
      })
      .then((res) => res.data),

  create: (data: KnowledgeCreatePayload) =>
    apiClient.post<KnowledgeCreateResponse>('/knowledge/', data).then((res) => res.data),

  get: (docId: string) => apiClient.get(`/knowledge/${docId}`).then((res) => res.data),

  stats: () => apiClient.get<{ chunk_count: number }>('/knowledge/stats').then((res) => res.data),
}
