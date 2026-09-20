/** 把流式片段拆成逐字展示，更接近常见聊天工具的打字感。 */
export function createTypewriter(onChar: (chunk: string, meta?: string) => void, delayMs = 16) {
  const queue: { char: string; meta?: string }[] = []
  let running = false
  let closed = false

  async function pump() {
    if (running) return
    running = true
    while (queue.length && !closed) {
      const item = queue.shift()
      if (item?.char) onChar(item.char, item.meta)
      if (delayMs > 0) await wait(delayMs)
    }
    running = false
  }

  return {
    push(text: string, meta?: string) {
      if (!text || closed) return
      for (const char of text) queue.push({ char, meta })
      void pump()
    },
    async flush() {
      while (!closed && (queue.length > 0 || running)) {
        await wait(Math.max(delayMs, 8))
      }
    },
    stop() {
      closed = true
      queue.length = 0
      running = false
    },
  }
}

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
