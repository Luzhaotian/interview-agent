import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'

import type { ChatMessage, Profile } from '@/lib/transcript'

const STORAGE_KEY = 'interview-agent.chats.v1'

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
    id: crypto.randomUUID(),
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
      memory: { ...emptyMemory(), ...(parsed.memory || {}) },
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
  const sending = ref(false)
  const memoryOpen = ref(false)

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
    [threads, activeId, memory, sending],
    () => {
      // 流式打字过程中不要同步写 localStorage，否则会把渲染拖成整段蹦出来
      if (sending.value) return
      const payload: PersistedState = {
        threads: threads.value.map((thread) => ({
          ...thread,
          messages: thread.messages.map((message) => ({
            ...message,
            streaming: false,
          })),
        })),
        activeId: activeId.value,
        memory: memory.value,
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
    },
    { deep: true },
  )

  function selectThread(id: string) {
    if (sending.value) return
    if (threads.value.some((item) => item.id === id)) activeId.value = id
  }

  function createNewThread() {
    if (sending.value) return
    const thread = createThread()
    threads.value = [thread, ...threads.value]
    activeId.value = thread.id
  }

  function removeThread(id: string) {
    if (sending.value) return
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
    selectThread,
    createNewThread,
    removeThread,
    touchActive,
    mergeMemoryFromProfile,
    updateMemoryNotes,
    clearMemory,
  }
})
