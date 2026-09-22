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
        const line = chunk
          .split('\n')
          .map((part) => part.trim())
          .find((part) => part.startsWith('data:'))
        if (!line) continue
        const raw = line.slice(5).trim()
        if (!raw) continue
        onEvent(JSON.parse(raw) as SseEvent)
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
