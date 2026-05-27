/**
 * useTypewriter — 流式对话「打字机」效果
 *
 * ## 为什么需要这个 Hook？
 * SSE 推送的 token 到达时间不均匀（有时一次很多字，有时很久才来一点）。
 * 若每个 token 直接 setState 上屏，界面会一顿一顿。
 *
 * ## 核心思路：双缓冲
 *   received（接收缓冲）← pushReceived(delta)  网络来了就往里塞
 *   display（展示缓冲）← tick 每帧切一点      屏幕按固定节奏显示
 *
 * ## 数据流（配合 ChatPage）
 *   chatStream.onToken  → pushReceived
 *   chatStream.onDone   → markStreamDone（网络结束，但字可能还没打完）
 *   onDisplay(text)     → 更新当前 assistant 消息的 content
 *   onCatchUpComplete   → 字打完且网络已结束 → 关光标、展示推理步骤等
 *
 *   中断/超时           → flushToReceived（立刻显示全文，不再动画）
 */
import { useCallback, useEffect, useRef } from 'react'

// ---------------------------------------------------------------------------
// 类型与配置
// ---------------------------------------------------------------------------

export interface UseTypewriterOptions {
  /** 基准打字速度：每秒大约显示多少个字符（仅控制「上屏」节奏，与 SSE 到达速度无关） */
  charsPerSecond?: number
  /** 每帧至少显示几个字符，避免 dt 很小时长时间「一个字都不动」 */
  minPerFrame?: number
  /** 积压很多时单帧最多显示几个字符，避免一帧跳出一大段破坏打字感 */
  maxPerFrame?: number
}

/** 传给 countCharsThisFrame 的速度参数（纯数据，便于单测） */
interface TypewriterSpeed {
  charsPerSecond: number
  minPerFrame: number
  maxPerFrame: number
}

/**
 * 当「已收到但未显示」的字数超过该阈值时，适当加速追赶。
 * 场景：网络一次推了很长一段，若仍按 48 字/秒慢慢打，用户会等很久才看完。
 */
const BACKLOG_SPEEDUP_THRESHOLD = 80

/**
 * 加速公式：每积压 BACKLOG_SPEEDUP_STEP 个字，本帧多显示 1 个字（上限见 maxPerFrame）。
 * 例：backlog=200 → 额外 +5 字/帧，但仍受 maxPerFrame 限制。
 */
const BACKLOG_SPEEDUP_STEP = 40

// ---------------------------------------------------------------------------
// 纯函数（与 React 无关，命名即文档）
// ---------------------------------------------------------------------------

/**
 * 计算「这一帧」应该从 received 里再拿出多少个字显示到屏幕上。
 *
 * @param backlog  还未显示的字符数 = received.length - display.length
 * @param dtMs     距离上一帧的时间间隔（毫秒），来自 requestAnimationFrame
 * @param speed    速度配置
 * @returns 本帧应显示的字符数，0 表示本帧不更新 display
 */
function countCharsThisFrame(
  backlog: number,
  dtMs: number,
  speed: TypewriterSpeed,
): number {
  if (backlog <= 0) return 0

  // 按「字/秒 × 时间」计算本帧基础字数；第一帧 dtMs=0 时靠 minPerFrame 保证至少 1 字
  const baseCount = Math.max(
    speed.minPerFrame,
    Math.floor((speed.charsPerSecond * dtMs) / 1000),
  )

  // 积压过大时附加加速，避免流已结束但屏幕还在慢慢追
  const speedup =
    backlog > BACKLOG_SPEEDUP_THRESHOLD
      ? Math.floor(backlog / BACKLOG_SPEEDUP_STEP)
      : 0

  const count = Math.min(speed.maxPerFrame, baseCount + speedup)

  // 不能超过实际积压，避免 slice 越界或重复
  return Math.min(count, backlog)
}

/**
 * 是否还需要继续 requestAnimationFrame 循环。
 *
 * 两个条件满足任一即继续：
 * 1. display 还没追上 received（字没打完）
 * 2. 网络还没 markStreamDone（可能还有 token 要来，即使暂时 display 已追上也要空转等待）
 */
function shouldKeepAnimating(
  displayLength: number,
  receivedLength: number,
  streamDone: boolean,
): boolean {
  return displayLength < receivedLength || !streamDone
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useTypewriter(
  /** 每帧更新展示文本时调用（ChatPage 里用来 setMessages 更新当前流式消息） */
  onDisplay: (text: string) => void,
  options: UseTypewriterOptions = {},
  /** 动画彻底结束：display 已追上 received，且 streamDone 为 true */
  onCatchUpComplete?: () => void,
) {
  const {
    charsPerSecond = 48,
    minPerFrame = 1,
    maxPerFrame = 14,
  } = options

  // ----- 双缓冲与状态（用 ref：tick 高频执行，避免每帧触发 React 重渲染） -----

  /** 网络已收到的完整文本（SSE onToken 不断 append） */
  const receivedRef = useRef('')

  /** 当前应显示在 UI 上的文本（tick 每帧从 received 头部 slice 出来） */
  const displayRef = useRef('')

  /**
   * 网络流是否已结束（chatStream 收到 event: done 后由 markStreamDone 置 true）。
   * 注意：done 只表示「不会再有新 token」，不代表屏幕已经打完字。
   */
  const streamDoneRef = useRef(false)

  /** 当前 rAF 循环 id，用于 cancelAnimationFrame */
  const rafIdRef = useRef<number | null>(null)

  /** 上一帧的时间戳，用于计算 dtMs */
  const lastTsRef = useRef(0)

  /**
   * 回调放进 ref，避免 tick 闭包捕获过期的 onDisplay / onCatchUpComplete。
   * 父组件 re-render 时通过 useEffect 同步最新回调。
   */
  const onDisplayRef = useRef(onDisplay)
  const onCatchUpCompleteRef = useRef(onCatchUpComplete)

  useEffect(() => {
    onDisplayRef.current = onDisplay
  }, [onDisplay])

  useEffect(() => {
    onCatchUpCompleteRef.current = onCatchUpComplete
  }, [onCatchUpComplete])

  /** 停止 rAF 循环并清零时间戳（组件卸载、reset、动画正常结束都会调用） */
  const stopLoop = useCallback(() => {
    if (rafIdRef.current != null) {
      cancelAnimationFrame(rafIdRef.current)
      rafIdRef.current = null
    }
    lastTsRef.current = 0
  }, [])

  /**
   * 每一帧执行一次（与显示器刷新率同步，通常约 60fps）。
   * 职责：算本帧显示字数 → 更新 display → 决定下一帧是否继续。
   */
  const tick = useCallback(
    (timestamp: number) => {
      // --- 1. 计算帧间隔 ---
      const dtMs = lastTsRef.current ? timestamp - lastTsRef.current : 0
      lastTsRef.current = timestamp

      // --- 2. 读取双缓冲，计算积压 ---
      const received = receivedRef.current
      const displayedLength = displayRef.current.length
      const backlog = received.length - displayedLength

      // --- 3. 从 received 头部再切一段给 display（始终用前缀，保证顺序正确） ---
      const charsToShow = countCharsThisFrame(backlog, dtMs, {
        charsPerSecond,
        minPerFrame,
        maxPerFrame,
      })

      if (charsToShow > 0) {
        displayRef.current = received.slice(0, displayedLength + charsToShow)
        onDisplayRef.current(displayRef.current)
      }

      // --- 4. 继续下一帧，或结束动画 ---
      const keepGoing = shouldKeepAnimating(
        displayRef.current.length,
        received.length,
        streamDoneRef.current,
      )

      if (keepGoing) {
        rafIdRef.current = requestAnimationFrame(tick)
        return
      }

      stopLoop()
      onCatchUpCompleteRef.current?.()
    },
    [charsPerSecond, minPerFrame, maxPerFrame, stopLoop],
  )

  /** 启动 rAF 循环（若已在跑则忽略，避免重复 requestAnimationFrame） */
  const startLoop = useCallback(() => {
    if (rafIdRef.current != null) return
    rafIdRef.current = requestAnimationFrame(tick)
  }, [tick])

  // ----- 对外 API -----

  /**
   * 收到 SSE token 时调用。
   * 只写入 received，不直接改 UI；由 tick 按节奏写入 display。
   */
  const pushReceived = useCallback(
    (delta: string) => {
      if (!delta) return
      receivedRef.current += delta
      startLoop()
    },
    [startLoop],
  )

  /**
   * SSE 收到 event: done 时调用。
   * 表示网络侧不会再推 token，但 tick 会继续直到 display 追上 received。
   */
  const markStreamDone = useCallback(() => {
    streamDoneRef.current = true
    startLoop()
  }, [startLoop])

  /**
   * 开始一条新的流式消息前调用（ChatPage handleSend 开头）。
   * 清空缓冲、停止旧循环，避免和上一条消息的动画串在一起。
   */
  const reset = useCallback(() => {
    stopLoop()
    receivedRef.current = ''
    displayRef.current = ''
    streamDoneRef.current = false
    onDisplayRef.current('')
  }, [stopLoop])

  /**
   * 不需要打字机动画时一次性展示全文。
   * 用于：澄清消息、服务端 error 事件等无需逐字输出的场景。
   */
  const setImmediate = useCallback(
    (text: string) => {
      stopLoop()
      receivedRef.current = text
      displayRef.current = text
      streamDoneRef.current = true
      onDisplayRef.current(text)
    },
    [stopLoop],
  )

  /**
   * 流中断 / 读超时 / 用户取消时：立刻把已收到的内容全部显示，并停止 rAF。
   * 避免 streamDone 一直为 false 导致 tick 空转。
   */
  const flushToReceived = useCallback(() => {
    stopLoop()
    displayRef.current = receivedRef.current
    streamDoneRef.current = true
    onDisplayRef.current(displayRef.current)
  }, [stopLoop])

  /** 取当前已显示文本（中断收尾时拼 partial 提示用） */
  const getDisplayText = useCallback(() => displayRef.current, [])

  /** 取当前已接收全文（通常比 display 更完整，优先用这个拼 partial） */
  const getReceivedText = useCallback(() => receivedRef.current, [])

  // 组件卸载时取消未结束的 rAF，防止内存泄漏或卸载后 setState
  useEffect(() => () => stopLoop(), [stopLoop])

  return {
    pushReceived,
    markStreamDone,
    reset,
    setImmediate,
    flushToReceived,
    getDisplayText,
    getReceivedText,
    stopLoop,
  }
}
