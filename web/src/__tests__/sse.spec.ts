import { describe, expect, it } from 'vitest'

import { createDoneTracker, readSse, type SseEvent } from '../lib/sse'

function sseResponse(chunks: string[]) {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder()
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
  return { ok: true, status: 200, body: stream } as unknown as Response
}

describe('readSse', () => {
  it('parses events split across chunks', async () => {
    const events: SseEvent[] = []
    // 一个事件的 data 行被拆到两个网络分片里
    await readSse(sseResponse(['data: {"type":"tok', 'en","text":"你好"}\n\n']), (event) => {
      events.push(event)
    })
    expect(events).toEqual([{ type: 'token', text: '你好' }])
  })

  it('skips malformed JSON without breaking the stream', async () => {
    const events: SseEvent[] = []
    await readSse(
      sseResponse([
        'data: {不是合法 JSON}\n\n',
        'data: {"type":"token","text":"ok"}\n\n',
      ]),
      (event) => events.push(event),
    )
    // 坏块被跳过，后面的好事件仍然送达
    expect(events).toEqual([{ type: 'token', text: 'ok' }])
  })

  it('joins multi-line data fields per SSE spec', async () => {
    const events: SseEvent[] = []
    await readSse(
      sseResponse(['data: {"type":"token",\ndata: "text":"多行"}\n\n']),
      (event) => events.push(event),
    )
    expect(events).toEqual([{ type: 'token', text: '多行' }])
  })

  it('throws with detail from error response body', async () => {
    const response = {
      ok: false,
      status: 400,
      json: async () => ({ detail: '简历是空的' }),
    } as unknown as Response
    await expect(readSse(response, () => {})).rejects.toThrow('简历是空的')
  })
})

describe('createDoneTracker', () => {
  it('passes when done event arrived', () => {
    const tracker = createDoneTracker()
    tracker.mark({ type: 'token', text: 'x' })
    tracker.mark({ type: 'done' })
    expect(() => tracker.assert()).not.toThrow()
  })

  it('throws when stream closed without done', () => {
    const tracker = createDoneTracker()
    tracker.mark({ type: 'thinking', text: 'x' })
    // 后端 worker 崩溃 / 进程重启：连接正常关闭但没有 done
    expect(() => tracker.assert()).toThrow('连接中断')
  })
})
