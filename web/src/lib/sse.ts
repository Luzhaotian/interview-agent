import type { InterviewDecision } from '@/lib/transcript'

export type SseEvent = {
  type: string
  text?: string
  detail?: string
  profile?: unknown
  question?: unknown
  candidates?: unknown
  append?: boolean
  decision?: InterviewDecision
  name?: string
  index?: number
  total?: number
}

export async function readSse(
  response: Response,
  onEvent: (event: SseEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  if (!response.ok) {
    let detail = `请求失败（${response.status}）`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // ignore
    }
    throw new Error(detail)
  }
  if (!response.body) throw new Error('浏览器不支持流式响应')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const onAbort = () => {
    void reader.cancel()
  }
  if (signal) {
    if (signal.aborted) {
      await reader.cancel()
      throw new DOMException('Aborted', 'AbortError')
    }
    signal.addEventListener('abort', onAbort, { once: true })
  }

  try {
    while (true) {
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const chunks = buffer.split('\n\n')
      buffer = chunks.pop() || ''
      for (const chunk of chunks) {
        // SSE 规范里一个事件可能有多行 data:，需按出现顺序拼接
        const dataLines = chunk
          .split('\n')
          .map((part) => part.trim())
          .filter((part) => part.startsWith('data:'))
        if (!dataLines.length) continue
        const raw = dataLines
          .map((line) => line.slice(5).trim())
          .filter(Boolean)
          .join('\n')
        if (!raw) continue
        let event: SseEvent
        try {
          event = JSON.parse(raw) as SseEvent
        } catch {
          // 畸形/被截断的分片：跳过这一块，别让整条流断掉
          continue
        }
        onEvent(event)
      }
    }
  } finally {
    signal?.removeEventListener('abort', onAbort)
  }
}

export function isAbortError(error: unknown) {
  return (
    (error instanceof DOMException && error.name === 'AbortError') ||
    (error instanceof Error && error.name === 'AbortError')
  )
}

/**
 * 追踪流是否收到后端的 done 事件。
 * 后端 worker 崩溃/进程重启/代理断链时，连接会「正常关闭」但永远等不到 done；
 * 没有这个检查，前端会把截断的流当成成功收尾，用户只看到内容戛然而止、无报错。
 */
export function createDoneTracker() {
  let done = false
  return {
    mark(event: SseEvent) {
      if (event.type === 'done') done = true
    },
    assert() {
      if (!done) {
        throw new Error('连接中断：本次生成未正常结束（后端可能重启或网络断开），请重试')
      }
    },
  }
}
