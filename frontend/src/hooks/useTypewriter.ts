import { useCallback, useEffect, useRef } from 'react'

export interface UseTypewriterOptions {
  /** 基准打字速度（字符/秒） */
  charsPerSecond?: number
  /** 每帧最少吐出字符数 */
  minPerFrame?: number
  /** 积压较多时每帧最多吐出字符数 */
  maxPerFrame?: number
}

/**
 * 双缓冲打字机：网络 chunk 写入 received，rAF 按节奏写入 display 并回调 onDisplay。
 */
export function useTypewriter(
  onDisplay: (text: string) => void,
  options: UseTypewriterOptions = {},
  onCatchUpComplete?: () => void,
) {
  const {
    charsPerSecond = 48,
    minPerFrame = 1,
    maxPerFrame = 14,
  } = options

  const receivedRef = useRef('')
  const displayRef = useRef('')
  const streamDoneRef = useRef(false)
  const rafIdRef = useRef<number | null>(null)
  const lastTsRef = useRef(0)
  const onDisplayRef = useRef(onDisplay)
  const onCatchUpCompleteRef = useRef(onCatchUpComplete)

  useEffect(() => {
    onDisplayRef.current = onDisplay
  }, [onDisplay])

  useEffect(() => {
    onCatchUpCompleteRef.current = onCatchUpComplete
  }, [onCatchUpComplete])

  const stopLoop = useCallback(() => {
    if (rafIdRef.current != null) {
      cancelAnimationFrame(rafIdRef.current)
      rafIdRef.current = null
    }
    lastTsRef.current = 0
  }, [])

  const tick = useCallback(
    (ts: number) => {
      const dt = lastTsRef.current ? ts - lastTsRef.current : 0
      lastTsRef.current = ts

      const received = receivedRef.current
      const displayed = displayRef.current
      const backlog = received.length - displayed.length

      if (backlog > 0) {
        let n = Math.max(minPerFrame, Math.floor((charsPerSecond * dt) / 1000))
        if (backlog > 80) {
          n = Math.min(maxPerFrame, n + Math.floor(backlog / 40))
        }
        n = Math.min(n, backlog)
        displayRef.current = received.slice(0, displayed.length + n)
        onDisplayRef.current(displayRef.current)
      }

      const stillCatchingUp = displayRef.current.length < receivedRef.current.length
      if (stillCatchingUp || !streamDoneRef.current) {
        rafIdRef.current = requestAnimationFrame(tick)
      } else {
        stopLoop()
        onCatchUpCompleteRef.current?.()
      }
    },
    [charsPerSecond, minPerFrame, maxPerFrame, stopLoop],
  )

  const startLoop = useCallback(() => {
    if (rafIdRef.current != null) return
    rafIdRef.current = requestAnimationFrame(tick)
  }, [tick])

  /** 收到 SSE token，写入接收缓冲 */
  const pushReceived = useCallback(
    (delta: string) => {
      if (!delta) return
      receivedRef.current += delta
      startLoop()
    },
    [startLoop],
  )

  /** 网络流结束；展示缓冲会继续追到 received 末尾 */
  const markStreamDone = useCallback(() => {
    streamDoneRef.current = true
    startLoop()
  }, [startLoop])

  /** 新一条消息开始前重置 */
  const reset = useCallback(() => {
    stopLoop()
    receivedRef.current = ''
    displayRef.current = ''
    streamDoneRef.current = false
    onDisplayRef.current('')
  }, [stopLoop])

  /** 历史消息等：直接展示全文，不跑动画 */
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

  useEffect(() => () => stopLoop(), [stopLoop])

  return {
    pushReceived,
    markStreamDone,
    reset,
    setImmediate,
    stopLoop,
  }
}
