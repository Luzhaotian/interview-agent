import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useChatStore } from '../stores/chat'
import type { ChatMessage } from '../lib/transcript'

function makeMessage(id: string, text = ''): ChatMessage {
  return { id, role: 'user', text }
}

describe('chat store 线程隔离', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('生成中也能切换与新建对话', () => {
    const chat = useChatStore()
    const first = chat.activeId
    chat.beginSend(first)

    // 切换不再被 sending 拦截
    chat.createNewThread()
    const second = chat.activeId
    expect(second).not.toBe(first)

    // sending 只对正在生成的那条线程为 true
    expect(chat.sending).toBe(false)
    expect(chat.anySending).toBe(true)
    expect(chat.isSending(first)).toBe(true)

    chat.selectThread(first)
    expect(chat.sending).toBe(true)

    chat.endSend(first)
    expect(chat.anySending).toBe(false)
  })

  it('addMessage/updateMessage 写入指定线程而非激活线程', () => {
    const chat = useChatStore()
    const first = chat.activeId
    chat.beginSend(first)
    chat.createNewThread()

    // 用户已切到新线程，流事件仍写回旧线程
    chat.addMessage(first, makeMessage('m1', '题目'))
    chat.updateMessage(first, 'm1', (message) => {
      message.text = '题目（已更新）'
    })

    const oldThread = chat.threadOf(first)
    expect(oldThread?.messages).toHaveLength(1)
    expect(oldThread?.messages[0]?.text).toBe('题目（已更新）')
    // 当前激活的新线程不受影响
    expect(chat.messages).toHaveLength(0)
  })

  it('生成中的线程不允许删除，其余可以', () => {
    const chat = useChatStore()
    const first = chat.activeId
    chat.beginSend(first)
    chat.createNewThread()
    const second = chat.activeId

    chat.removeThread(first)
    expect(chat.threadOf(first)).toBeTruthy()

    chat.removeThread(second)
    expect(chat.threadOf(second)).toBeUndefined()
  })

  it('endSend 后状态会持久化到 localStorage', async () => {
    const chat = useChatStore()
    const first = chat.activeId
    chat.beginSend(first)
    chat.addMessage(first, makeMessage('m1', '内容'))
    chat.endSend(first)

    await new Promise((resolve) => setTimeout(resolve, 0))
    const raw = localStorage.getItem('interview-agent.chats.v1')
    expect(raw).toContain('内容')
  })
})
