<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import IGButton from '@/components/IGButton.vue'
import IGQuestionCard from '@/components/IGQuestionCard.vue'
import { label, stageOrder } from '@/lib/labels'
import { renderMarkdown } from '@/lib/markdown'
import { createDoneTracker, isAbortError, readSse, type SseEvent } from '@/lib/sse'
import { createTypewriter } from '@/lib/typewriter'
import { uid } from '@/lib/uid'
import {
  messageText,
  transcriptMarkdown,
  type ChatMessage,
  type Profile,
  type Question,
  type ResumeReport,
  type WebCandidate,
} from '@/lib/transcript'
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
const chat = useChatStore()

const draft = ref('')
const files = ref<File[]>([])
const count = ref(15)
const fileInput = ref<HTMLInputElement | null>(null)
const scroller = ref<HTMLElement | null>(null)
const notice = ref('')
const dragging = ref(false)
const stickToBottom = ref(true)
const showJumpBottom = ref(false)
const BOTTOM_GAP = 72
let scrollingProgrammatically = false
let jumpTimer = 0
/** 每个线程各自持有 AbortController：生成中切走后，停止按钮只作用于当前线程。 */
const aborts = new Map<string, AbortController>()
const activeMarkerId = ref('')
const hoveredMarkerId = ref('')

const allowedExt = ['.pdf', '.docx', '.md', '.markdown', '.txt']

const canSend = computed(
  () => session.connected && !chat.sending && (draft.value.trim().length > 0 || files.value.length > 0),
)

const userMarkers = computed(() =>
  chat.messages
    .filter((item) => item.role === 'user')
    .map((item) => ({
      id: item.id,
      preview: truncatePreview(item.text || (item.fileName ? `简历 · ${item.fileName}` : '（空消息）')),
    })),
)

function truncatePreview(text: string, max = 42) {
  const value = text.trim().replace(/\s+/g, ' ')
  if (value.length <= max) return value
  return `${value.slice(0, max)}…`
}

function distanceFromBottom(node: HTMLElement) {
  return node.scrollHeight - node.scrollTop - node.clientHeight
}

function isNearBottom(node: HTMLElement) {
  return distanceFromBottom(node) <= BOTTOM_GAP
}

function scrollToBottom(smooth = false) {
  const node = scroller.value
  if (!node) return
  stickToBottom.value = true
  showJumpBottom.value = false
  scrollingProgrammatically = true
  window.clearTimeout(jumpTimer)
  if (smooth) {
    node.scrollTo({ top: node.scrollHeight, behavior: 'smooth' })
    jumpTimer = window.setTimeout(() => {
      scrollingProgrammatically = false
      if (scroller.value && isNearBottom(scroller.value)) {
        stickToBottom.value = true
        showJumpBottom.value = false
      }
    }, 420)
  } else {
    node.scrollTop = node.scrollHeight
    requestAnimationFrame(() => {
      scrollingProgrammatically = false
    })
  }
}

function onTranscriptScroll() {
  if (scrollingProgrammatically) return
  const node = scroller.value
  if (!node) return
  if (isNearBottom(node)) {
    stickToBottom.value = true
    showJumpBottom.value = false
  } else {
    stickToBottom.value = false
    showJumpBottom.value = true
  }
  updateActiveMarker()
}

function updateActiveMarker() {
  const node = scroller.value
  const markers = userMarkers.value
  if (!node || !markers.length) {
    activeMarkerId.value = ''
    return
  }
  const top = node.scrollTop + 28
  let current = markers[0]?.id || ''
  for (const item of markers) {
    const el = node.querySelector(`#msg-${CSS.escape(item.id)}`) as HTMLElement | null
    if (!el) continue
    if (el.offsetTop <= top) current = item.id
    else break
  }
  activeMarkerId.value = current
}

function jumpToMessage(id: string) {
  const node = scroller.value
  const target = node?.querySelector(`#msg-${CSS.escape(id)}`) as HTMLElement | null
  if (!node || !target) return
  stickToBottom.value = false
  showJumpBottom.value = true
  activeMarkerId.value = id
  scrollingProgrammatically = true
  window.clearTimeout(jumpTimer)
  target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  jumpTimer = window.setTimeout(() => {
    scrollingProgrammatically = false
    onTranscriptScroll()
  }, 420)
}

watch(
  () => {
    const last = chat.messages[chat.messages.length - 1]
    const report = last?.reports?.[last.reports.length - 1]
    return [
      chat.messages.length,
      last?.text,
      last?.reasoning,
      last?.thinking?.length,
      last?.questions?.length,
      last?.reports?.length,
      report?.text,
      report?.reasoning,
      report?.thinking?.length,
      report?.questions?.length,
      chat.sending,
    ]
  },
  async () => {
    if (!stickToBottom.value) {
      await nextTick()
      updateActiveMarker()
      return
    }
    await nextTick()
    scrollToBottom()
    updateActiveMarker()
  },
)

watch(
  () => chat.activeId,
  async () => {
    stickToBottom.value = true
    showJumpBottom.value = false
    activeMarkerId.value = ''
    hoveredMarkerId.value = ''
    await nextTick()
    scrollToBottom()
    updateActiveMarker()
  },
)

function addFiles(list: FileList | File[] | null | undefined) {
  if (!list?.length) return
  const next = [...files.value]
  const skipped: string[] = []
  for (const item of Array.from(list)) {
    const dot = item.name.lastIndexOf('.')
    const ext = dot >= 0 ? item.name.slice(dot).toLowerCase() : ''
    if (!allowedExt.includes(ext)) {
      skipped.push(item.name)
      continue
    }
    const exists = next.some((file) => file.name === item.name && file.size === item.size)
    if (!exists) next.push(item)
  }
  files.value = next.slice(0, 8)
  if (next.length > 8) notice.value = '一次最多 8 个文件'
  else if (skipped.length) notice.value = `已跳过不支持的文件：${skipped.join('、')}`
  else notice.value = ''
  if (fileInput.value) fileInput.value.value = ''
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  addFiles(input.files)
}

function removeFile(index: number) {
  files.value = files.value.filter((_, item) => item !== index)
}

function clearFiles() {
  files.value = []
  if (fileInput.value) fileInput.value.value = ''
}

function pickFile() {
  fileInput.value?.click()
}

function isFileDrag(event: DragEvent) {
  return Array.from(event.dataTransfer?.types ?? []).includes('Files')
}

function onDragOver(event: DragEvent) {
  if (!isFileDrag(event)) return
  dragging.value = true
}

function onDragLeave(event: DragEvent) {
  const current = event.currentTarget as HTMLElement | null
  const related = event.relatedTarget as Node | null
  if (current && related && current.contains(related)) return
  dragging.value = false
}

function onDrop(event: DragEvent) {
  dragging.value = false
  if (chat.sending || !session.connected) return
  addFiles(event.dataTransfer?.files)
}

function latestContext(threadId: string) {
  const threadMessages = chat.threadOf(threadId)?.messages || chat.messages
  const packs = threadMessages.filter((item) => item.questions?.length)
  const questionCtx = packs.length
    ? packs.map((item, index) => `【第 ${index + 1} 批题目】\n${messageText(item)}`).join('\n\n')
    : ''
  const memoryCtx = chat.memoryText
  if (memoryCtx && questionCtx) return `【长期记忆】\n${memoryCtx}\n\n【本轮题目上下文】\n${questionCtx}`
  if (memoryCtx) return `【长期记忆】\n${memoryCtx}`
  return questionCtx
}

function selectedQuestionIds(threadId: string) {
  const threadMessages = chat.threadOf(threadId)?.messages || chat.messages
  const ids: string[] = []
  const seen = new Set<string>()
  for (const message of threadMessages) {
    for (const item of message.questions || []) {
      if (!item.id || seen.has(item.id)) continue
      seen.add(item.id)
      ids.push(item.id)
    }
  }
  return ids
}

function profilePayload() {
  return {
    years: chat.memory.years || '未知',
    focus: chat.memory.focus || 'frontend',
    skills: chat.memory.skills,
    projects: chat.memory.projects,
    summary: chat.memory.summary,
  }
}

function push(threadId: string, message: ChatMessage) {
  chat.addMessage(threadId, message)
  return message
}

function patch(threadId: string, id: string, updater: (message: ChatMessage) => void) {
  chat.updateMessage(threadId, id, updater)
}

const skipMemory = new Set<string>()

function currentReport(message: ChatMessage) {
  return message.reports?.[message.reports.length - 1]
}

function applyThinking(message: ChatMessage, event: { text?: string; append?: boolean }) {
  const text = event.text || ''
  if (!text) return
  const report = currentReport(message)
  if (report) {
    if (event.append) report.reasoning += text
    else report.thinking = [...report.thinking, text]
    return
  }
  if (event.append) {
    message.reasoning = `${message.reasoning || ''}${text}`
    return
  }
  message.thinking = [...(message.thinking || []), text]
}

const prompts = [
  '请根据这份简历出 15 道题，按基础到经历排布',
  '请根据这份简历，决定是否进入到可约面试环节',
]

function usePrompt(text: string) {
  draft.value = text
  if (text.includes('15 道题')) count.value = 15
}

function stopGeneration() {
  if (!chat.sending) return
  aborts.get(chat.activeId)?.abort()
}

function isScreenRequest(text: string) {
  return text.includes('可约面试') || text.includes('是否进入')
}

function groupedQuestions(questions: Question[]) {
  // index 是组内序号（卡片显示编号），stagger 是全局序号（错峰浮现用）：
  // 题卡由后端一次性 emit，逐张延迟出现避免「突然一大块」
  let globalIndex = 0
  return stageOrder
    .map((stage) => {
      const stageItems = questions.filter((item) => item.stage === stage)
      return {
        stage,
        items: stageItems.map((item, index) => ({ question: item, index, stagger: globalIndex++ })),
      }
    })
    .filter((group) => group.items.length)
}

async function send() {
  if (!canSend.value) return
  notice.value = ''
  stickToBottom.value = true
  showJumpBottom.value = false
  const text = draft.value.trim()
  const attachments = [...files.value]
  draft.value = ''
  clearFiles()
  // 绑定发起时的线程：生成期间用户切走后，SSE 事件仍写回这条线程，不会丢
  const threadId = chat.activeId
  push(threadId, {
    id: uid(),
    role: 'user',
    text: text || `请根据这份简历出 ${count.value} 道题，按基础到经历排布`,
    fileName: attachments.map((item) => item.name).join('、') || undefined,
  })
  const assistant = push(threadId, {
    id: uid(),
    role: 'assistant',
    text: '',
    thinking: [],
    questions: [],
    streaming: true,
  })
  const controller = new AbortController()
  aborts.set(threadId, controller)
  chat.beginSend(threadId)
  try {
    if (attachments.length && isScreenRequest(text)) {
      await screenStream(threadId, attachments, assistant.id, controller.signal)
    } else if (attachments.length) {
      await recommendStream(threadId, attachments, assistant.id, controller.signal)
    } else {
      await replyStream(threadId, text, assistant.id, controller.signal)
    }
  } catch (error) {
    if (isAbortError(error)) {
      patch(threadId, assistant.id, (message) => {
        message.streaming = false
        const hasContent =
          Boolean(message.text.trim()) ||
          Boolean(message.questions?.length) ||
          Boolean(message.reports?.some((item) => item.text || item.questions.length || item.decision))
        if (!hasContent) message.text = '已停止生成。'
      })
      if (threadId === chat.activeId) notice.value = '已停止'
    } else {
      patch(threadId, assistant.id, (message) => {
        message.error = true
        message.text = error instanceof Error ? error.message : '生成失败'
        message.streaming = false
      })
    }
  } finally {
    // Map 里可能已被新一次生成覆盖，只删属于自己的那个
    if (aborts.get(threadId) === controller) aborts.delete(threadId)
    chat.endSend(threadId)
  }
}

async function screenStream(
  threadId: string,
  attachments: File[],
  messageId: string,
  signal: AbortSignal,
) {
  const body = new FormData()
  for (const item of attachments) body.append('files', item)
  const response = await fetch('/api/screen/stream', { method: 'POST', body, signal })
  const tracker = createDoneTracker()
  await readSse(
    response,
    (event) => {
      tracker.mark(event)
      applyStreamEvent(threadId, messageId, event)
    },
    signal,
  )
  tracker.assert()
  patch(threadId, messageId, (message) => {
    message.streaming = false
  })
}

function applyStreamEvent(threadId: string, messageId: string, event: SseEvent, reportKey = '') {
  if (event.type === 'resume' && event.name) {
    const name = event.name
    const key = reportKey || `${event.index ?? 0}-${name}`
    if ((event.total ?? 1) > 1) skipMemory.add(messageId)
    patch(threadId, messageId, (message) => {
      const report: ResumeReport = {
        key,
        name,
        text: '',
        reasoning: '',
        thinking: [],
        questions: [],
      }
      message.reports = [...(message.reports || []), report]
    })
    return
  }
  if (event.type === 'error') {
    let attached = false
    patch(threadId, messageId, (message) => {
      const report = currentReport(message)
      if (!report) return
      report.error = event.detail || '处理失败'
      attached = true
    })
    if (!attached) throw new Error(event.detail || '处理失败')
    return
  }
  patch(threadId, messageId, (message) => {
    const report = currentReport(message)
    if (event.type === 'thinking' && event.text) {
      applyThinking(message, event)
    } else if (event.type === 'profile') {
      const profile = event.profile as Profile
      if (report) report.profile = profile
      else message.profile = profile
      if (!skipMemory.has(messageId)) chat.mergeMemoryFromProfile(profile)
    } else if (event.type === 'question') {
      const question = event.question as Question
      if (report) report.questions = [...report.questions, question]
      else message.questions = [...(message.questions || []), question]
    } else if (event.type === 'decision' && event.decision) {
      if (report) report.decision = event.decision
      else message.decision = event.decision
    } else if (event.type === 'web_candidates' && Array.isArray(event.candidates)) {
      const list = event.candidates as WebCandidate[]
      if (report) report.webCandidates = list
      else message.webCandidates = list
    } else if (event.type === 'token' && event.text) {
      if (report) report.text += event.text
      else message.text += event.text
    }
  })
}

async function recommendStream(
  threadId: string,
  attachments: File[],
  messageId: string,
  signal: AbortSignal,
) {
  const body = new FormData()
  for (const item of attachments) body.append('files', item)
  body.append('count', String(count.value))
  const response = await fetch('/api/recommend/stream', { method: 'POST', body, signal })
  let activeKey = ''
  const tracker = createDoneTracker()
  const typewriter = createTypewriter((chunk, key) => {
    patch(threadId, messageId, (message) => {
      const report = key ? message.reports?.find((item) => item.key === key) : undefined
      if (report) report.text += chunk
      else message.text += chunk
    })
  })
  try {
    await readSse(
      response,
      (event) => {
        tracker.mark(event)
        if (event.type === 'resume' && event.name) {
          activeKey = `${event.index ?? 0}-${event.name}`
          applyStreamEvent(threadId, messageId, event, activeKey)
          return
        }
        if (event.type === 'token' && event.text) {
          typewriter.push(event.text, activeKey || undefined)
          return
        }
        applyStreamEvent(threadId, messageId, event)
      },
      signal,
    )
    tracker.assert()
    await typewriter.flush()
    patch(threadId, messageId, (message) => {
      message.streaming = false
      if (!message.reports?.length && !message.text.trim()) {
        message.text = '题目已按基础 → 框架 → 架构经验 → 过往经历排好。可继续追问某一道。'
      }
    })
  } catch (error) {
    typewriter.stop()
    throw error
  }
}

async function replyStream(threadId: string, text: string, messageId: string, signal: AbortSignal) {
  // 历史/上下文在发起时取当前线程快照；send() 里同步调用，threadId 即 activeId
  const threadMessages = chat.threadOf(threadId)?.messages || chat.messages
  const history = threadMessages
    .filter((item) => !item.error && item.id !== messageId)
    .map((item) => ({ role: item.role, content: messageText(item) }))
  if (!history.length || history[history.length - 1]?.content !== text) {
    history.push({ role: 'user', content: text })
  }
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages: history,
      context: latestContext(threadId),
      selected_ids: selectedQuestionIds(threadId),
      profile: profilePayload(),
      count: 5,
    }),
    signal,
  })
  const tracker = createDoneTracker()
  const typewriter = createTypewriter((chunk) => {
    patch(threadId, messageId, (message) => {
      message.text += chunk
    })
  })
  try {
    await readSse(
      response,
      (event) => {
        tracker.mark(event)
        if (event.type === 'thinking' && event.text) {
          patch(threadId, messageId, (message) => {
            applyThinking(message, event)
          })
        } else if (event.type === 'question') {
          patch(threadId, messageId, (message) => {
            message.questions = [...(message.questions || []), event.question as Question]
          })
        } else if (event.type === 'decision' && event.decision) {
          patch(threadId, messageId, (message) => {
            message.decision = event.decision
          })
        } else if (event.type === 'token' && event.text) {
          typewriter.push(event.text)
        } else if (event.type === 'error') {
          throw new Error(event.detail || '回复失败')
        }
      },
      signal,
    )
    tracker.assert()
    await typewriter.flush()
    patch(threadId, messageId, (message) => {
      message.streaming = false
      if (!message.text.trim() && message.questions?.length) {
        message.text = '已补充题目，样式与首次出题一致。可继续追问某一道。'
      }
    })
  } catch (error) {
    typewriter.stop()
    throw error
  }
}

function onComposerKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter') return
  // 输入法选词中的 Enter 不发送
  if (event.isComposing || event.keyCode === 229) return
  if (event.shiftKey) {
    event.preventDefault()
    const el = event.target as HTMLTextAreaElement
    const start = el.selectionStart ?? draft.value.length
    const end = el.selectionEnd ?? start
    draft.value = `${draft.value.slice(0, start)}\n${draft.value.slice(end)}`
    void nextTick(() => {
      el.selectionStart = start + 1
      el.selectionEnd = start + 1
    })
    return
  }
  event.preventDefault()
  void send()
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    notice.value = '已复制'
  } catch {
    notice.value = '复制失败，请检查浏览器权限'
  }
}

function webCandidatesJson(items: WebCandidate[]) {
  return JSON.stringify({ questions: items }, null, 2)
}

async function copyWebCandidates(items: WebCandidate[]) {
  await copyText(webCandidatesJson(items))
  notice.value = '联网候选已复制，可粘贴进 kb/ 后执行 ingest'
}

function copyAll() {
  void copyText(transcriptMarkdown(chat.messages))
}

function exportChat() {
  const blob = new Blob([transcriptMarkdown(chat.messages)], {
    type: 'text/markdown;charset=utf-8',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  const day = new Date().toISOString().slice(0, 10)
  link.href = url
  link.download = `interview-chat-${day}.md`
  link.click()
  URL.revokeObjectURL(url)
  notice.value = '已导出 Markdown'
}
</script>

<template>
  <section
    class="relative flex h-full min-h-0 flex-col px-6 py-2 pb-3.5 max-md:px-4 max-md:pb-3"
    @dragenter.prevent="onDragOver"
    @dragover.prevent="onDragOver"
    @dragleave.prevent="onDragLeave"
    @drop.prevent="onDrop"
  >
    <div
      v-if="dragging"
      class="pointer-events-none absolute inset-3 z-4 grid place-items-center rounded-2xl border-[1.5px] border-dashed border-accent bg-[color-mix(in_srgb,var(--accent)_12%,#fff)] text-[15px] [font-weight:650] text-accent"
    >
      松开即可上传，支持多份简历
    </div>
    <div class="flex min-h-7 flex-none items-center justify-end gap-3">
      <div class="flex gap-2">
        <IGButton :disabled="!chat.messages.length" @click="copyAll">复制</IGButton>
        <IGButton :disabled="!chat.messages.length" @click="exportChat">导出</IGButton>
      </div>
      <p v-if="notice" class="m-0 text-[13px] text-accent">{{ notice }}</p>
    </div>

    <div class="relative mt-2 flex min-h-0 flex-1 flex-row items-stretch gap-2">
      <nav
        v-if="userMarkers.length"
        class="z-3 flex w-3.5 flex-none flex-col items-center gap-2.5 overflow-visible py-3.5 pb-6"
        aria-label="问题定位"
      >
        <button
          v-for="(item, index) in userMarkers"
          :key="item.id"
          type="button"
          class="group relative grid size-3.5 place-items-center border-0 bg-transparent p-0 cursor-pointer"
          :data-on="activeMarkerId === item.id"
          :aria-label="`第 ${index + 1} 条问题`"
          @click="jumpToMessage(item.id)"
          @mouseenter="hoveredMarkerId = item.id"
          @mouseleave="hoveredMarkerId = ''"
          @focus="hoveredMarkerId = item.id"
          @blur="hoveredMarkerId = ''"
        >
          <span
            class="block size-2 rounded-sm bg-[rgba(18,32,46,0.22)] transition-[transform,background,box-shadow] duration-160 ease-in-out group-hover:bg-[rgba(18,32,46,0.38)] group-focus-visible:bg-[rgba(18,32,46,0.38)] group-data-[on=true]:scale-150 group-data-[on=true]:bg-accent group-data-[on=true]:shadow-[0_0_0_3px_color-mix(in_srgb,var(--accent)_22%,transparent)]"
          />
          <span
            v-if="hoveredMarkerId === item.id"
            class="pointer-events-none absolute left-[calc(100%+10px)] top-1/2 z-5 w-max max-w-[min(240px,42vw)] -translate-y-1/2 overflow-hidden text-ellipsis whitespace-nowrap rounded-lg bg-ink px-2.5 py-1.5 text-xs leading-[1.4] text-[#f4faf8] shadow-preview"
          >{{ item.preview }}</span>
        </button>
      </nav>
      <div class="relative flex min-h-0 min-w-0 flex-1 flex-col">
        <div
          ref="scroller"
          class="scroll-thin min-h-0 flex-1 overflow-auto px-3 pt-2 pb-5"
          @scroll="onTranscriptScroll"
        >
          <div
            v-if="!chat.messages.length"
            class="animate-rise mx-auto grid min-h-full max-w-[420px] place-content-center justify-items-center text-center"
          >
            <h2 class="m-0 font-display text-2xl">从一份简历或一句追问起</h2>
            <p class="mt-2 mb-0 text-sm text-muted">生成时展示思考过程，并以打字效果输出说明。</p>
            <IGButton
              variant="accent"
              class="mt-3 [font-weight:650]"
              :disabled="!session.connected || chat.sending"
              @click="pickFile"
            >
              选择简历文件
            </IGButton>
            <p class="mt-2.5 mb-0 text-sm text-muted">也可以把 PDF、DOCX、Markdown、TXT 拖到这里，一次多份。</p>
            <p v-if="files.length" class="mt-2.5 mb-0 text-sm font-semibold text-accent">
              已选 {{ files.map((item) => item.name).join('、') }} · 题数 {{ count }}，在下方发送即可
            </p>
          </div>

          <article
            v-for="message in chat.messages"
            :id="message.role === 'user' ? `msg-${message.id}` : undefined"
            :key="message.id"
            class="animate-rise bubble-card box-border mb-4 w-[92%] max-w-none px-[22px] py-[18px] data-[role=user]:ml-auto data-[role=user]:scroll-mt-3 data-[role=user]:bg-bubble-user data-[role=assistant]:mr-auto data-[error=true]:border-[#ffd1cc] data-[error=true]:bg-[#fff1f0]"
            :data-role="message.role"
            :data-error="message.error || undefined"
          >
            <div class="mb-2 flex items-center justify-between">
              <strong>{{ message.role === 'user' ? '你' : '助手' }}</strong>
              <IGButton size="sm" class="rounded-xl px-2 py-1" @click="copyText(messageText(message))">
                复制
              </IGButton>
            </div>

            <p v-if="message.fileName" class="mb-2 mt-0 text-sm font-semibold text-accent">
              简历 · {{ message.fileName }}
            </p>

            <template v-if="message.reports?.length">
              <section
                v-for="report in message.reports"
                :key="report.key"
                class="mt-2 grid gap-3 border-t border-line/10 pt-3"
              >
                <h2 class="m-0 text-[15px]">{{ report.name }}</h2>
                <details
                  v-if="report.thinking.length || report.reasoning"
                  class="mb-0 rounded-xl border border-line/8 bg-white/60 px-3 py-2.5"
                  :open="message.streaming || undefined"
                >
                  <summary class="cursor-pointer text-[13px] font-semibold text-muted">
                    {{ message.streaming ? '正在思考…' : '步骤' }}
                    <span v-if="report.thinking.length" class="ml-1 font-normal opacity-70"
                      >{{ report.thinking.length }}</span
                    >
                  </summary>
                  <ol
                    v-if="report.thinking.length"
                    class="mt-2.5 mb-0 list-decimal pl-[1.2em] text-[13px] leading-relaxed text-muted"
                  >
                    <li
                      v-for="(step, index) in report.thinking"
                      :key="`${report.key}-think-${index}`"
                      class="mt-0 pl-1 [&+&]:mt-1.5"
                    >
                      {{ step }}
                    </li>
                  </ol>
                  <details v-if="report.reasoning" class="mt-2.5 border-t border-line/8 pt-2">
                    <summary class="cursor-pointer text-xs text-muted/80">模型草稿（可忽略）</summary>
                    <p class="mt-1.5 mb-0 max-h-40 overflow-auto whitespace-pre-wrap text-xs leading-snug text-muted/70">
                      {{ report.reasoning }}
                    </p>
                  </details>
                </details>

                <div
                  v-if="report.webCandidates?.length"
                  class="rounded-xl border border-dashed border-accent/35 bg-accent-soft/40 px-3 py-2.5"
                >
                  <div class="flex flex-wrap items-center justify-between gap-2">
                    <p class="m-0 text-[13px] font-semibold text-accent">
                      联网补题 {{ report.webCandidates.length }} 道（可沉淀进知识库）
                    </p>
                    <IGButton size="sm" class="rounded-xl px-2 py-1" @click="copyWebCandidates(report.webCandidates)">
                      复制 JSON
                    </IGButton>
                  </div>
                  <p class="mt-1 mb-0 text-xs text-muted">
                    已写入后端 <code class="text-xs">output/web-inbox-latest.json</code>；复制后可放进
                    <code class="text-xs">kb/</code> 再
                    <code class="text-xs">python main.py ingest</code>
                  </p>
                  <ul class="mt-2 mb-0 list-none p-0">
                    <li
                      v-for="item in report.webCandidates"
                      :key="item.id"
                      class="border-t border-line/8 py-1.5 text-[13px] leading-snug first:border-0 first:pt-0"
                    >
                      <span class="text-muted">{{ item.topic }} · </span>{{ item.question }}
                    </li>
                  </ul>
                </div>

                <p v-if="report.error" class="m-0 text-[#9f1239]">{{ report.error }}</p>
                <div
                  v-if="report.text"
                  class="md m-0 data-[streaming=true]:min-h-[1.5em]"
                  :data-streaming="message.streaming || undefined"
                  v-html="renderMarkdown(report.text)"
                />
                <div
                  v-if="report.decision"
                  class="mt-3 rounded-[14px] border border-[#ffd1cc] bg-[#fff6f5] px-4 py-3.5 data-[ok=true]:border-[rgba(11,122,106,0.28)] data-[ok=true]:bg-[#f3fbf8]"
                  :data-ok="report.decision.recommend"
                >
                  <h3 class="mb-2 mt-0 font-display text-[22px]">
                    {{ report.decision.recommend ? '推荐面试' : '不推荐面试' }}
                  </h3>
                  <ul class="m-0 pl-[1.2em]">
                    <li
                      v-for="(reason, index) in report.decision.reasons"
                      :key="`${report.key}-reason-${index}`"
                      class="mt-0 [&+&]:mt-1.5"
                    >
                      {{ reason }}
                    </li>
                  </ul>
                </div>
                <div
                  v-if="report.profile"
                  class="mt-3.5 grid grid-cols-2 gap-2.5 max-md:grid-cols-1"
                >
                  <div class="rounded-xl profile-cell px-3 py-2.5">
                    <span class="block text-xs text-muted">方向</span>
                    <strong class="mt-1 block [font-weight:650]">{{ label(report.profile.focus) }}</strong>
                  </div>
                  <div class="rounded-xl profile-cell px-3 py-2.5">
                    <span class="block text-xs text-muted">年限</span>
                    <strong class="mt-1 block [font-weight:650]">{{ report.profile.years }}</strong>
                  </div>
                  <div class="col-span-full rounded-xl profile-cell px-3 py-2.5">
                    <span class="block text-xs text-muted">技能</span>
                    <strong class="mt-1 block [font-weight:650]">{{
                      report.profile.skills.join('、') || '未识别'
                    }}</strong>
                  </div>
                  <div class="col-span-full rounded-xl profile-cell px-3 py-2.5">
                    <span class="block text-xs text-muted">摘要</span>
                    <strong class="mt-1 block [font-weight:650]">{{ report.profile.summary || '无' }}</strong>
                  </div>
                </div>
                <div v-if="report.questions.length" class="mt-[18px] grid gap-[18px]">
                  <section v-for="group in groupedQuestions(report.questions)" :key="group.stage">
                    <h3 class="mb-2.5 mt-0 font-display text-[22px]">{{ label(group.stage) }}</h3>
                    <IGQuestionCard
                      v-for="item in group.items"
                      :key="`${report.key}-${item.question.id}`"
                      :question="item.question"
                      :index="item.index"
                      :stagger="item.stagger"
                    />
                  </section>
                </div>
              </section>
            </template>

            <template v-else>
              <details
                v-if="message.thinking?.length || message.reasoning"
                class="mb-3 rounded-xl border border-line/8 bg-white/60 px-3 py-2.5"
                :open="message.streaming || undefined"
              >
                <summary class="cursor-pointer text-[13px] font-semibold text-muted">
                  {{ message.streaming ? '正在思考…' : '步骤' }}
                  <span v-if="message.thinking?.length" class="ml-1 font-normal opacity-70">{{
                    message.thinking.length
                  }}</span>
                </summary>
                <ol
                  v-if="message.thinking?.length"
                  class="mt-2.5 mb-0 list-decimal pl-[1.2em] text-[13px] leading-relaxed text-muted"
                >
                  <li
                    v-for="(step, index) in message.thinking"
                    :key="`${message.id}-${index}`"
                    class="mt-0 pl-1 [&+&]:mt-1.5"
                  >
                    {{ step }}
                  </li>
                </ol>
                <details v-if="message.reasoning" class="mt-2.5 border-t border-line/8 pt-2">
                  <summary class="cursor-pointer text-xs text-muted/80">模型草稿（可忽略）</summary>
                  <p class="mt-1.5 mb-0 max-h-40 overflow-auto whitespace-pre-wrap text-xs leading-snug text-muted/70">
                    {{ message.reasoning }}
                  </p>
                </details>
              </details>

              <div
                v-if="message.webCandidates?.length"
                class="mb-3 rounded-xl border border-dashed border-accent/35 bg-accent-soft/40 px-3 py-2.5"
              >
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <p class="m-0 text-[13px] font-semibold text-accent">
                    联网补题 {{ message.webCandidates.length }} 道（可沉淀进知识库）
                  </p>
                  <IGButton size="sm" class="rounded-xl px-2 py-1" @click="copyWebCandidates(message.webCandidates)">
                    复制 JSON
                  </IGButton>
                </div>
                <ul class="mt-2 mb-0 list-none p-0">
                  <li
                    v-for="item in message.webCandidates"
                    :key="item.id"
                    class="border-t border-line/8 py-1.5 text-[13px] leading-snug first:border-0 first:pt-0"
                  >
                    <span class="text-muted">{{ item.topic }} · </span>{{ item.question }}
                  </li>
                </ul>
              </div>

              <div
                v-if="message.role === 'assistant' && message.text"
                class="md m-0 data-[streaming=true]:min-h-[1.5em]"
                :data-streaming="message.streaming || undefined"
                v-html="renderMarkdown(message.text)"
              />
              <p
                v-else-if="message.text"
                class="m-0 whitespace-pre-wrap data-[streaming=true]:min-h-[1.5em]"
                :data-streaming="message.streaming || undefined"
              >
                {{ message.text }}
              </p>

              <div
                v-if="message.decision"
                class="mt-3 rounded-[14px] border border-[#ffd1cc] bg-[#fff6f5] px-4 py-3.5 data-[ok=true]:border-[rgba(11,122,106,0.28)] data-[ok=true]:bg-[#f3fbf8]"
                :data-ok="message.decision.recommend"
              >
                <h3 class="mb-2 mt-0 font-display text-[22px]">
                  {{ message.decision.recommend ? '推荐面试' : '不推荐面试' }}
                </h3>
                <ul class="m-0 pl-[1.2em]">
                  <li
                    v-for="(reason, index) in message.decision.reasons"
                    :key="`${message.id}-reason-${index}`"
                    class="mt-0 [&+&]:mt-1.5"
                  >
                    {{ reason }}
                  </li>
                </ul>
              </div>

              <div
                v-if="message.profile"
                class="mt-3.5 grid grid-cols-2 gap-2.5 max-md:grid-cols-1"
              >
                <div class="rounded-xl profile-cell px-3 py-2.5">
                  <span class="block text-xs text-muted">方向</span>
                  <strong class="mt-1 block [font-weight:650]">{{ label(message.profile.focus) }}</strong>
                </div>
                <div class="rounded-xl profile-cell px-3 py-2.5">
                  <span class="block text-xs text-muted">年限</span>
                  <strong class="mt-1 block [font-weight:650]">{{ message.profile.years }}</strong>
                </div>
                <div class="col-span-full rounded-xl profile-cell px-3 py-2.5">
                  <span class="block text-xs text-muted">技能</span>
                  <strong class="mt-1 block [font-weight:650]">{{
                    message.profile.skills.join('、') || '未识别'
                  }}</strong>
                </div>
                <div class="col-span-full rounded-xl profile-cell px-3 py-2.5">
                  <span class="block text-xs text-muted">摘要</span>
                  <strong class="mt-1 block [font-weight:650]">{{ message.profile.summary || '无' }}</strong>
                </div>
              </div>

              <div v-if="message.questions?.length" class="mt-[18px] grid gap-[18px]">
                <section v-for="group in groupedQuestions(message.questions)" :key="group.stage">
                  <h3 class="mb-2.5 mt-0 font-display text-[22px]">{{ label(group.stage) }}</h3>
                  <IGQuestionCard
                    v-for="item in group.items"
                    :key="item.question.id"
                    :question="item.question"
                    :index="item.index"
                    :stagger="item.stagger"
                  />
                </section>
              </div>
            </template>
            <span
              v-if="message.streaming"
              class="animate-blink ml-0.5 inline-block h-[1em] w-[0.55ch] align-[-0.1em] bg-accent"
            />
          </article>
        </div>
        <button
          v-if="showJumpBottom"
          type="button"
          class="absolute bottom-3 right-4 z-2 size-9 rounded-full border border-line/10 bg-panel-strong text-base leading-none text-ink shadow-jump hover:border-transparent hover:bg-accent-soft hover:text-accent"
          aria-label="回到底部"
          @click="scrollToBottom(true)"
        >
          ↓
        </button>
      </div>
    </div>

    <form class="mt-2.5 flex-none border-t border-line/10 pt-2.5" @submit.prevent>
      <input
        ref="fileInput"
        class="sr-only"
        type="file"
        multiple
        accept=".pdf,.docx,.md,.markdown,.txt"
        :disabled="!session.connected || chat.sending"
        @change="onFileChange"
      />

      <div v-if="files.length" class="mb-2.5 flex flex-wrap items-center gap-2">
        <div
          v-for="(item, index) in files"
          :key="`${item.name}-${item.size}`"
          class="inline-flex max-w-full items-center gap-2 rounded-full bg-accent-soft py-1.5 pl-3 pr-2 text-[13px] font-semibold text-accent"
        >
          <span class="max-w-[220px] overflow-hidden text-ellipsis whitespace-nowrap">{{
            item.name
          }}</span>
          <IGButton size="sm" class="rounded-xl px-2 py-1" @click="removeFile(index)">移除</IGButton>
        </div>
        <label class="inline-flex items-center gap-1.5 font-medium text-muted">
          题数
          <input
            v-model.number="count"
            class="w-14 rounded-lg border border-line/10 bg-white px-1.5 py-0.5 text-ink"
            type="number"
            min="10"
            max="20"
            :disabled="chat.sending"
          />
        </label>
      </div>

      <div class="mb-2.5 flex flex-wrap gap-2">
        <button
          v-for="item in prompts"
          :key="item"
          type="button"
          class="rounded-full border border-line/10 bg-white/90 px-3 py-1.5 text-left text-[13px] text-muted hover:border-[rgba(11,122,106,0.35)] hover:bg-accent-soft hover:text-accent"
          :disabled="!session.connected || chat.sending"
          @click="usePrompt(item)"
        >
          {{ item }}
        </button>
      </div>
      <div class="composer-box">
        <textarea
          v-model="draft"
          class="min-h-14 w-full resize-y border-0 bg-transparent px-1 pt-1 outline-none"
          rows="2"
          placeholder="追问某一道：先说回答方向，再给参考答案。Enter 发送，Shift+Enter 换行。"
          :disabled="!session.connected || chat.sending"
          @keydown="onComposerKeydown"
        />
        <div class="flex items-center justify-between gap-2.5">
          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-xl border border-line/10 bg-transparent px-3 py-2 text-muted hover:border-[rgba(11,122,106,0.35)] hover:bg-accent-soft hover:text-accent"
            :disabled="!session.connected || chat.sending"
            title="上传简历"
            @click="pickFile"
          >
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <path
                fill="currentColor"
                d="M16.5 6.5v9.25a4.5 4.5 0 1 1-9 0V6.75a3 3 0 0 1 6 0v8.5a1.5 1.5 0 1 1-3 0V7.5h-1.5v7.75a3 3 0 1 0 6 0V6.75a4.5 4.5 0 1 0-9 0v9a6 6 0 1 0 12 0V6.5H16.5z"
              />
            </svg>
            简历
          </button>
          <IGButton
            v-if="chat.sending"
            variant="danger"
            class="min-w-[84px]"
            @click="stopGeneration"
          >
            停止
          </IGButton>
          <IGButton v-else variant="accent" class="min-w-[84px]" :disabled="!canSend" @click="send">
            发送
          </IGButton>
        </div>
      </div>
    </form>
  </section>
</template>
