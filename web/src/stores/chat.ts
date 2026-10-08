import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'

import type { ChatMessage, Profile } from '@/lib/transcript'
import { uid } from '@/lib/uid'

const STORAGE_KEY = 'interview-agent.chats.v1'
/** 只持久化最近这么多会话，避免 localStorage 无限增长撑爆配额。 */
const MAX_PERSISTED_THREADS = 30

export type LongTermMemory = {
  focus: string
  years: string
  skills: string[]
  projects: string[]
  summary: string
  notes: string
  updatedAt: number
}

export type ChatThread = {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: number
  updatedAt: number
}

type PersistedState = {
  threads: ChatThread[]
  activeId: string
  memory: LongTermMemory
}

function emptyMemory(): LongTermMemory {
  return {
    focus: '',
    years: '',
    skills: [],
    projects: [],
    summary: '',
    notes: '',
    updatedAt: 0,
  }
}

function createThread(title = '新对话'): ChatThread {
  const now = Date.now()
  return {
    id: uid(),
    title,
    messages: [],
    createdAt: now,
    updatedAt: now,
  }
}

function loadState(): PersistedState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      const thread = createThread()
      return { threads: [thread], activeId: thread.id, memory: emptyMemory() }
    }
    const parsed = JSON.parse(raw) as PersistedState
    if (!parsed.threads?.length) {
      const thread = createThread()
      return { threads: [thread], activeId: thread.id, memory: parsed.memory || emptyMemory() }
    }
    const firstId = parsed.threads[0]?.id
    if (!firstId) {
      const thread = createThread()
      return { threads: [thread], activeId: thread.id, memory: parsed.memory || emptyMemory() }
    }
    return {
      threads: parsed.threads.map((thread) => ({
        ...thread,
        messages: (thread.messages || []).map((message) => ({
          ...message,
          streaming: false,
        })),
      })),
      activeId: parsed.activeId || firstId,
      memory: { ...emptyMemory(), ...parsed.memory },
    }
  } catch {
    const thread = createThread()
    return { threads: [thread], activeId: thread.id, memory: emptyMemory() }
  }
}

function previewTitle(messages: ChatMessage[]) {
  const firstUser = messages.find((item) => item.role === 'user')
  if (!firstUser) return '新对话'
  if (firstUser.fileName) return `简历 · ${firstUser.fileName}`
  const text = firstUser.text.trim().replace(/\s+/g, ' ')
  return text.slice(0, 28) || '新对话'
}

function memoryLines(memory: LongTermMemory) {
  const lines: string[] = []
  if (memory.focus) lines.push(`方向：${memory.focus}`)
  if (memory.years) lines.push(`年限：${memory.years}`)
  if (memory.skills.length) lines.push(`技能：${memory.skills.join('、')}`)
  if (memory.projects.length) lines.push(`项目：${memory.projects.join('、')}`)
  if (memory.summary) lines.push(`摘要：${memory.summary}`)
  if (memory.notes.trim()) lines.push(`备注：${memory.notes.trim()}`)
  return lines
}

export const useChatStore = defineStore('chat', () => {
  const initial = loadState()
  const threads = ref<ChatThread[]>(initial.threads)
  const activeId = ref(initial.activeId)
  const memory = ref<LongTermMemory>(initial.memory)
  /** 正在流式生成的线程 id。按线程隔离后，生成中也可以自由切换/新建对话。 */
  const sendingIds = ref(new Set<string>())
  const memoryOpen = ref(false)

  const sending = computed(() => sendingIds.value.has(activeId.value))
  const anySending = computed(() => sendingIds.value.size > 0)

  const activeThread = computed(
    () => threads.value.find((item) => item.id === activeId.value) || threads.value[0],
  )

  const messages = computed({
    get: () => activeThread.value?.messages || [],
    set: (next: ChatMessage[]) => {
      const thread = activeThread.value
      if (!thread) return
      thread.messages = next
      thread.updatedAt = Date.now()
      if (thread.title === '新对话' || thread.title.startsWith('简历 ·')) {
        thread.title = previewTitle(next)
      }
    },
  })

  const memoryText = computed(() => memoryLines(memory.value).join('\n'))
  const hasMemory = computed(() => memoryLines(memory.value).length > 0)

  watch(
    [threads, activeId, memory, sendingIds],
    () => {
      // 流式打字过程中不要同步写 localStorage，否则会把渲染拖成整段蹦出来；
      // sendingIds 在 beginSend/endSend 时整体替换，能触发本 watch，
      // 生成结束（集合清空）后 anySending 转 false，这里补写一次最终态。
      if (anySending.value) return
      persist()
    },
    { deep: true },
  )

  function buildPayload(keepReasoning: boolean): PersistedState {
    const sorted = [...threads.value].sort((a, b) => b.updatedAt - a.updatedAt)
    return {
      threads: sorted.slice(0, MAX_PERSISTED_THREADS).map((thread) => ({
        ...thread,
        messages: thread.messages.map((message) => ({
          ...message,
          streaming: false,
          // 配额吃紧时丢掉体积最大、又最不影响回顾的思考草稿
          ...(keepReasoning ? {} : { reasoning: '', thinking: [] }),
        })),
      })),
      activeId: activeId.value,
      memory: memory.value,
    }
  }

  function persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(buildPayload(true)))
    } catch {
      // 配额溢出（会话/思考文本太多）：先瘦身重写，仍失败就放弃这次持久化，
      // 但不能让异常冒到 deep watch 里，否则每次变更都抛错、持久化整体失效。
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(buildPayload(false)))
      } catch {
        // 彻底写不下就算了，内存态仍在，不影响当前使用
      }
    }
  }

  function selectThread(id: string) {
    if (threads.value.some((item) => item.id === id)) activeId.value = id
  }

  function createNewThread() {
    const thread = createThread()
    threads.value = [thread, ...threads.value]
    activeId.value = thread.id
  }

  function removeThread(id: string) {
    // 正在生成的线程不能删：流事件还要往里面写
    if (sendingIds.value.has(id)) return
    if (threads.value.length <= 1) {
      const thread = createThread()
      threads.value = [thread]
      activeId.value = thread.id
      return
    }
    threads.value = threads.value.filter((item) => item.id !== id)
    if (activeId.value === id) {
      const next = threads.value[0]
      activeId.value = next ? next.id : createThread().id
    }
  }

  function beginSend(threadId: string) {
    sendingIds.value = new Set(sendingIds.value).add(threadId)
  }

  function endSend(threadId: string) {
    const next = new Set(sendingIds.value)
    next.delete(threadId)
    sendingIds.value = next
  }

  function threadOf(threadId: string) {
    return threads.value.find((item) => item.id === threadId)
  }

  /** 按线程 id 追加消息；流式期间用户可能已切走，不能再依赖 activeThread。 */
  function addMessage(threadId: string, message: ChatMessage) {
    const thread = threadOf(threadId)
    if (!thread) return
    thread.messages.push(message)
    thread.updatedAt = Date.now()
    if (thread.title === '新对话' || thread.title.startsWith('简历 ·')) {
      thread.title = previewTitle(thread.messages)
    }
  }

  /** 按线程 id + 消息 id 定位并更新，找不到就静默跳过（线程可能已被删）。 */
  function updateMessage(threadId: string, messageId: string, updater: (message: ChatMessage) => void) {
    const message = threadOf(threadId)?.messages.find((item) => item.id === messageId)
    if (message) updater(message)
  }

  function isSending(threadId: string) {
    return sendingIds.value.has(threadId)
  }

  function touchActive(titleHint?: string) {
    const thread = activeThread.value
    if (!thread) return
    thread.updatedAt = Date.now()
    if (titleHint) thread.title = titleHint.slice(0, 28)
    else if (thread.messages.length) thread.title = previewTitle(thread.messages)
  }

  function mergeMemoryFromProfile(profile: Profile) {
    const next = { ...memory.value }
    if (profile.focus) next.focus = profile.focus
    if (profile.years) next.years = profile.years
    if (profile.skills?.length) {
      next.skills = Array.from(new Set([...next.skills, ...profile.skills]))
    }
    if (profile.projects?.length) {
      next.projects = Array.from(new Set([...next.projects, ...profile.projects]))
    }
    if (profile.summary) next.summary = profile.summary
    next.updatedAt = Date.now()
    memory.value = next
  }

  function updateMemoryNotes(notes: string) {
    memory.value = { ...memory.value, notes, updatedAt: Date.now() }
  }

  function clearMemory() {
    memory.value = emptyMemory()
  }

  return {
    threads,
    activeId,
    activeThread,
    messages,
    memory,
    memoryText,
    hasMemory,
    memoryOpen,
    sending,
    anySending,
    sendingIds,
    selectThread,
    createNewThread,
    removeThread,
    beginSend,
    endSend,
    addMessage,
    updateMessage,
    isSending,
    threadOf,
    touchActive,
    mergeMemoryFromProfile,
    updateMemoryNotes,
    clearMemory,
  }
})
