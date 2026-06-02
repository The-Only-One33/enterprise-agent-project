import { useState, useRef, useEffect, useCallback } from 'react'
import {
  SendOutlined,
  RobotOutlined,
  UserOutlined,
  LoadingOutlined,
  BulbOutlined,
  DownloadOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons'
import { Spin, Collapse, Tag, Empty, message, Button, Alert } from 'antd'
import ReactMarkdown from 'react-markdown'
import {
  chatApi,
  StreamInterruptedError,
  weeklyExportDownloadUrl,
  type ReasoningStep,
  type Source,
} from '../services/chatApi'
import { useTypewriter } from '../hooks/useTypewriter'
import './ChatPage.css'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  reasoning?: ReasoningStep[]
  sources?: Source[]
  isClarification?: boolean
  clarificationType?: 'intent' | 'slot' | 'plan'
  conversationId?: number
  exportPath?: string
  /** 正在流式输出 / 打字机动画中 */
  isStreaming?: boolean
}

function clarificationHint(type?: string): string | null {
  switch (type) {
    case 'plan':
      return '可回复：全部项目总周报 / 单项目：项目名 / 上周 / 近两周'
    case 'slot':
      return '请根据上文补充缺失的业务参数'
    case 'intent':
      return '请明确你想执行的操作（查询、创建、周报等）'
    default:
      return null
  }
}

const QUICK_PROMPTS = [
  '帮我生成本周周报',
  '查询我的任务',
  '周报怎么写',
]

interface Conversation {
  id: number
  title: string
  message_count: number
  created_at: string
  updated_at: string
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversation, setActiveConversation] = useState<number | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const streamingMessageIdRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const pendingMetaRef = useRef<Partial<Message> | null>(null)

  const updateStreamingMessage = useCallback((content: string) => {
    const id = streamingMessageIdRef.current
    if (!id) return
    setMessages(prev =>
      prev.map(m => (m.id === id ? { ...m, content } : m)),
    )
  }, [])

  const finishStreamingMessage = useCallback(
    (patch: Partial<Message> = {}) => {
      const id = streamingMessageIdRef.current
      if (!id) return
      setMessages(prev =>
        prev.map(m =>
          m.id === id ? { ...m, isStreaming: false, ...patch } : m,
        ),
      )
      streamingMessageIdRef.current = null
    },
    [],
  )

  const handleTypewriterComplete = useCallback(() => {
    const patch = pendingMetaRef.current ?? {}
    pendingMetaRef.current = null
    finishStreamingMessage(patch)
  }, [finishStreamingMessage])

  const typewriter = useTypewriter(
    updateStreamingMessage,
    {},
    handleTypewriterComplete,
  )

  /** 流中断/超时：保留已生成内容并追加提示 */
  const finishStreamWithNotice = useCallback(
    (notice: string) => {
      typewriter.flushToReceived()
      const partial =
        typewriter.getReceivedText() || typewriter.getDisplayText()
      const patch = pendingMetaRef.current ?? {}
      pendingMetaRef.current = null
      const content = partial
        ? `${partial}\n\n---\n\n⚠️ ${notice}`
        : `⚠️ ${notice}`
      finishStreamingMessage({ content, ...patch })
    },
    [finishStreamingMessage, typewriter],
  )

  useEffect(() => {
    loadConversations()
  }, [])

  const loadConversations = async () => {
    try {
      const res = await chatApi.getConversations()
      setConversations(res.conversations)
    } catch (error) {
      console.error('加载会话列表失败:', error)
    }
  }

  const handleNewConversation = async () => {
    try {
      const res = await chatApi.createConversation()
      await loadConversations()
      setActiveConversation(res.id)
      setMessages([])
    } catch (error) {
      message.error('创建会话失败')
    }
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const userText = input.trim()
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: userText,
      timestamp: new Date().toLocaleTimeString(),
    }

    setMessages(prev => [...prev, userMessage])

    const pendingClarification = [...messages].reverse().find(m => m.isClarification)
    const conversationId =
      pendingClarification?.conversationId ?? activeConversation ?? undefined

    setInput('')
    setIsLoading(true)

    abortRef.current?.abort()
    abortRef.current = new AbortController()

    const assistantId = (Date.now() + 1).toString()
    streamingMessageIdRef.current = assistantId
    pendingMetaRef.current = null
    typewriter.reset()

    const placeholder: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toLocaleTimeString(),
      isStreaming: true,
    }
    setMessages(prev => [...prev, placeholder])
    setIsLoading(false)

    try {
      await chatApi.chatStream(
        userText,
        conversationId || undefined,
        {
          onToken: delta => typewriter.pushReceived(delta),
          onClarification: data => {
            typewriter.setImmediate(data.clarification_question)
            if (data.conversation_id) {
              setActiveConversation(data.conversation_id)
            }
            finishStreamingMessage({
              content: data.clarification_question,
              isClarification: true,
              clarificationType: data.clarification_type,
              conversationId: data.conversation_id,
              reasoning: (data.reasoning_steps || []).map(step => ({
                step: step.step,
                thought: step.thought,
                action: step.action,
              })),
            })
          },
          onMeta: meta => {
            if (meta.conversation_id) {
              setActiveConversation(meta.conversation_id)
            }
            pendingMetaRef.current = {
              reasoning: (meta.reasoning_steps || []).map(step => ({
                step: step.step,
                thought: step.thought,
                action: step.action,
              })),
              exportPath: meta.export_path || undefined,
            }
          },
          onError: errMsg => {
            message.error(errMsg)
            finishStreamWithNotice(errMsg || '生成回答时出错')
          },
          onInterrupted: (errMsg) => {
            message.warning(errMsg)
            finishStreamWithNotice(`${errMsg}，请重试`)
          },
          onDone: () => typewriter.markStreamDone(),
        },
        abortRef.current.signal,
      )
    } catch (error: unknown) {
      if (error instanceof Error && error.name === 'AbortError') {
        typewriter.flushToReceived()
        const partial =
          typewriter.getReceivedText() || typewriter.getDisplayText()
        typewriter.markStreamDone()
        if (partial) {
          finishStreamingMessage({ content: partial })
        } else {
          finishStreamingMessage()
        }
        return
      }
      if (error instanceof StreamInterruptedError) {
        message.warning(error.message)
        finishStreamWithNotice(`${error.message}，请重试`)
        return
      }
      const errMsg =
        error instanceof Error ? error.message : '请求失败，请检查后端服务'
      message.error(errMsg)
      finishStreamWithNotice(
        'Agent 服务暂时不可用，请检查后端服务后重试',
      )
    }
  }

  const getStepIcon = (step: string) => {
    switch (step) {
      case 'intent_recognition':
      case 'intent_clarification_resume':
        return <RobotOutlined />
      case 'graph_traverse':
        return <BulbOutlined />
      case 'db_query':
      case 'plan_query_data':
      case 'plan_rag_guide':
        return <BulbOutlined />
      case 'llm_reasoning':
        return <RobotOutlined />
      case 'clarification_interrupt':
      case 'react_fallback':
        return <QuestionCircleOutlined />
      default:
        return <BulbOutlined />
    }
  }

  const sendQuickPrompt = (text: string) => {
    setInput(text)
  }

  const getSourceColor = (type: string) => {
    switch (type) {
      case 'rag': return 'blue'
      case 'graph': return 'green'
      case 'db': return 'orange'
      default: return 'default'
    }
  }

  return (
    <div className="chat-page">
      <div className="conversation-list glass-card">
        <div className="conversation-header">
          <span>会话列表</span>
          <button className="new-chat-btn" onClick={handleNewConversation}>+ 新对话</button>
        </div>
        <div className="conversations">
          {conversations.map(conv => (
            <div 
              key={conv.id} 
              className={`conversation-item ${activeConversation === conv.id ? 'active' : ''}`}
              onClick={() => {
                abortRef.current?.abort()
                setActiveConversation(conv.id)
                chatApi.getMessages(conv.id).then(res => {
                  const msgs: Message[] = res.messages.map(m => ({
                    id: m.id.toString(),
                    role: m.role as 'user' | 'assistant',
                    content: m.content,
                    timestamp: m.created_at,
                  }))
                  setMessages(msgs)
                }).catch(console.error)
              }}
            >
              <span className="conv-title">{conv.title}</span>
              <span className="conv-time">{conv.updated_at}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="chat-area">
        <div className="messages-container">
          {messages.length === 0 ? (
            <div className="welcome-state">
              <RobotOutlined className="welcome-icon" />
              <h2>智能任务协同Agent</h2>
              <p>我是您的智能助手，可以帮助您：</p>
              <ul>
                <li>查询任务状态、评分和进度</li>
                <li>生成并导出本周周报（Planner + ReAct）</li>
                <li>知识库问答（如「周报怎么写」）</li>
                <li>创建和管理项目任务</li>
              </ul>
              <div className="quick-prompts">
                {QUICK_PROMPTS.map(text => (
                  <button
                    key={text}
                    type="button"
                    className="quick-prompt-chip"
                    onClick={() => sendQuickPrompt(text)}
                  >
                    {text}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map(msg => (
              <div key={msg.id} className={`message ${msg.role}`}>
                <div className="message-avatar">
                  {msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                </div>
                <div className="message-content">
                  {msg.isClarification && clarificationHint(msg.clarificationType) && (
                    <Alert
                      type="info"
                      showIcon
                      className="clarification-hint"
                      message={
                        msg.clarificationType === 'plan'
                          ? '周报范围确认'
                          : msg.clarificationType === 'slot'
                            ? '参数补充'
                            : '意图确认'
                      }
                      description={clarificationHint(msg.clarificationType)}
                    />
                  )}
                  <div className={`message-text ${msg.isStreaming ? 'is-streaming' : ''}`}>
                    {msg.content ? (
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    ) : msg.isStreaming ? (
                      <Spin indicator={<LoadingOutlined spin />} size="small" />
                    ) : null}
                    {msg.isStreaming && msg.content ? (
                      <span className="stream-cursor" aria-hidden />
                    ) : null}
                  </div>
                  {msg.exportPath && !msg.isStreaming && (
                    <Button
                      type="link"
                      icon={<DownloadOutlined />}
                      className="export-download-btn"
                      href={weeklyExportDownloadUrl(msg.exportPath)}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      下载周报 Markdown
                    </Button>
                  )}
                  {msg.reasoning && msg.reasoning.length > 0 && !msg.isStreaming && (
                    <Collapse
                      className="reasoning-collapse"
                      ghost
                      items={[{
                        key: '1',
                        label: <span className="reasoning-label"><BulbOutlined /> 查看Agent推理过程</span>,
                        children: (
                          <div className="reasoning-steps">
                            {msg.reasoning.map((step, idx) => (
                              <div key={idx} className="reasoning-step">
                                <div className="step-icon">{getStepIcon(step.step)}</div>
                                <div className="step-content">
                                  <span className="step-name">{step.step}</span>
                                  <span className="step-thought">{step.thought}</span>
                                  <Tag color="blue">{step.action}</Tag>
                                </div>
                              </div>
                            ))}
                          </div>
                        ),
                      }]}
                    />
                  )}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="sources">
                      <span className="sources-label">数据来源：</span>
                      {msg.sources.map((source, idx) => (
                        <Tag key={idx} color={getSourceColor(source.type)}>{source.type.toUpperCase()}</Tag>
                      ))}
                    </div>
                  )}
                  <span className="message-time">{msg.timestamp}</span>
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-area glass-card">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            placeholder="输入您的问题，按Enter发送..."
            rows={3}
            disabled={messages.some(m => m.isStreaming)}
          />
          <button
            className="send-btn"
            onClick={handleSend}
            disabled={!input.trim() || messages.some(m => m.isStreaming)}
          >
            <SendOutlined /> 发送
          </button>
        </div>
      </div>

      <div className="tools-panel glass-card">
        <div className="panel-header"><h3>工具面板</h3></div>
        <div className="panel-content">
          <div className="tool-section">
            <h4><BulbOutlined /> RAG检索结果</h4>
            <Empty description="暂无检索结果" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          </div>
          <div className="tool-section">
            <h4>图谱关系</h4>
            <Empty description="暂无图谱数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          </div>
        </div>
      </div>
    </div>
  )
}
