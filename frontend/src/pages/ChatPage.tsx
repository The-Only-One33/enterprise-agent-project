import { useState, useRef, useEffect, useCallback } from 'react'
import { SendOutlined, RobotOutlined, UserOutlined, LoadingOutlined, BulbOutlined } from '@ant-design/icons'
import { Spin, Collapse, Tag, Empty, message } from 'antd'
import ReactMarkdown from 'react-markdown'
import { chatApi, type ReasoningStep, type Source } from '../services/chatApi'
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
  conversationId?: number
  /** 正在流式输出 / 打字机动画中 */
  isStreaming?: boolean
}

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

    const lastAssistantMsg = messages.find(m => m.isClarification)
    // 这个没看懂
    const conversationId = lastAssistantMsg?.conversationId || activeConversation

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
            finishStreamingMessage({
              content: data.clarification_question,
              isClarification: true,
              conversationId: data.conversation_id,
              reasoning: (data.reasoning_steps || []).map(step => ({
                step: step.step,
                thought: step.thought,
                action: step.action,
              })),
            })
          },
          onMeta: meta => {
            pendingMetaRef.current = {
              reasoning: (meta.reasoning_steps || []).map(step => ({
                step: step.step,
                thought: step.thought,
                action: step.action,
              })),
            }
          },
          onError: errMsg => {
            message.error(errMsg)
            typewriter.setImmediate('抱歉，生成回答时出错。')
            finishStreamingMessage({ content: '抱歉，生成回答时出错。' })
          },
          onDone: () => typewriter.markStreamDone(),
        },
        abortRef.current.signal,
      )
    } catch (error: unknown) {
      if (error instanceof Error && error.name === 'AbortError') {
        typewriter.markStreamDone()
        finishStreamingMessage()
        return
      }
      const errMsg =
        error instanceof Error ? error.message : '请求失败，请检查后端服务'
      message.error(errMsg)
      typewriter.setImmediate('抱歉，Agent 服务暂时不可用。请确保后端服务已启动。')
      finishStreamingMessage({
        content: '抱歉，Agent 服务暂时不可用。请确保后端服务已启动。',
      })
    }
  }

  const getStepIcon = (step: string) => {
    switch (step) {
      case 'intent_recognition': return <RobotOutlined />
      case 'graph_traverse': return <BulbOutlined />
      case 'db_query': return <BulbOutlined />
      case 'llm_reasoning': return <RobotOutlined />
      default: return <BulbOutlined />
    }
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
                <li>查找相似历史任务</li>
                <li>分析员工-项目-任务的关联关系</li>
                <li>创建和管理项目任务</li>
              </ul>
            </div>
          ) : (
            messages.map(msg => (
              <div key={msg.id} className={`message ${msg.role}`}>
                <div className="message-avatar">
                  {msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                </div>
                <div className="message-content">
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
