<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import { label, stageOrder } from '@/lib/labels'
import { renderMarkdown } from '@/lib/markdown'
import { readSse, type SseEvent } from '@/lib/sse'
import { createTypewriter } from '@/lib/typewriter'
import {
  messageText,
  transcriptMarkdown,
  type ChatMessage,
  type InterviewDecision,
  type Profile,
  type Question,
  type ResumeReport,
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

const allowedExt = ['.pdf', '.docx', '.md', '.markdown', '.txt']

const canSend = computed(
  () => session.connected && !chat.sending && (draft.value.trim().length > 0 || files.value.length > 0),
)

watch(
  () => {
    const last = chat.messages[chat.messages.length - 1]
    return [chat.messages.length, last?.text, last?.questions?.length]
  },
  async () => {
    await nextTick()
    const node = scroller.value
    if (node) node.scrollTop = node.scrollHeight
  },
)

watch(
  () => chat.activeId,
  async () => {
    await nextTick()
    const node = scroller.value
    if (node) node.scrollTop = node.scrollHeight
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

function latestContext() {
  const packs = chat.messages.filter((item) => item.questions?.length)
  const questionCtx = packs.length
    ? packs.map((item, index) => `【第 ${index + 1} 批题目】\n${messageText(item)}`).join('\n\n')
    : ''
  const memoryCtx = chat.memoryText
  if (memoryCtx && questionCtx) return `【长期记忆】\n${memoryCtx}\n\n【本轮题目上下文】\n${questionCtx}`
  if (memoryCtx) return `【长期记忆】\n${memoryCtx}`
  return questionCtx
}

function selectedQuestionIds() {
  const ids: string[] = []
  const seen = new Set<string>()
  for (const message of chat.messages) {
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

function push(message: ChatMessage) {
  chat.messages.push(message)
  chat.touchActive()
  return message
}

function patch(id: string, updater: (message: ChatMessage) => void) {
  const target = chat.messages.find((item) => item.id === id)
  if (target) updater(target)
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

function isScreenRequest(text: string) {
  return text.includes('可约面试') || text.includes('是否进入')
}

function groupedQuestions(questions: Question[]) {
  return stageOrder
    .map((stage) => ({
      stage,
      items: questions.filter((item) => item.stage === stage),
    }))
    .filter((group) => group.items.length)
}

async function send() {
  if (!canSend.value) return
  notice.value = ''
  const text = draft.value.trim()
  const attachments = [...files.value]
  draft.value = ''
  clearFiles()
  push({
    id: crypto.randomUUID(),
    role: 'user',
    text: text || `请根据这份简历出 ${count.value} 道题，按基础到经历排布`,
    fileName: attachments.map((item) => item.name).join('、') || undefined,
  })
  const assistant = push({
    id: crypto.randomUUID(),
    role: 'assistant',
    text: '',
    thinking: [],
    questions: [],
    streaming: true,
  })
  chat.sending = true
  try {
    if (attachments.length && isScreenRequest(text)) {
      await screenStream(attachments, assistant.id)
    } else if (attachments.length) {
      await recommendStream(attachments, assistant.id)
    } else {
      await replyStream(text, assistant.id)
    }
  } catch (error) {
    patch(assistant.id, (message) => {
      message.error = true
      message.text = error instanceof Error ? error.message : '生成失败'
      message.streaming = false
    })
  } finally {
    chat.sending = false
    chat.touchActive()
  }
}

async function screenStream(attachments: File[], messageId: string) {
  const body = new FormData()
  for (const item of attachments) body.append('files', item)
  const response = await fetch('/api/screen/stream', { method: 'POST', body })
  await readSse(response, (event) => {
    applyStreamEvent(messageId, event)
  })
  patch(messageId, (message) => {
    message.streaming = false
  })
}

function applyStreamEvent(messageId: string, event: SseEvent, reportKey = '') {
  if (event.type === 'resume' && event.name) {
    const name = event.name
    const key = reportKey || `${event.index ?? 0}-${name}`
    if ((event.total ?? 1) > 1) skipMemory.add(messageId)
    patch(messageId, (message) => {
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
    patch(messageId, (message) => {
      const report = currentReport(message)
      if (!report) return
      report.error = event.detail || '处理失败'
      attached = true
    })
    if (!attached) throw new Error(event.detail || '处理失败')
    return
  }
  patch(messageId, (message) => {
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
    } else if (event.type === 'token' && event.text) {
      if (report) report.text += event.text
      else message.text += event.text
    }
  })
}

async function recommendStream(attachments: File[], messageId: string) {
  const body = new FormData()
  for (const item of attachments) body.append('files', item)
  body.append('count', String(count.value))
  const response = await fetch('/api/recommend/stream', { method: 'POST', body })
  let activeKey = ''
  const typewriter = createTypewriter((chunk, key) => {
    patch(messageId, (message) => {
      const report = key ? message.reports?.find((item) => item.key === key) : undefined
      if (report) report.text += chunk
      else message.text += chunk
    })
  })
  try {
    await readSse(response, (event) => {
      if (event.type === 'resume' && event.name) {
        activeKey = `${event.index ?? 0}-${event.name}`
        applyStreamEvent(messageId, event, activeKey)
        return
      }
      if (event.type === 'token' && event.text) {
        typewriter.push(event.text, activeKey || undefined)
        return
      }
      applyStreamEvent(messageId, event)
    })
    await typewriter.flush()
    patch(messageId, (message) => {
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

async function replyStream(text: string, messageId: string) {
  const history = chat.messages
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
      context: latestContext(),
      selected_ids: selectedQuestionIds(),
      profile: profilePayload(),
      count: 5,
    }),
  })
  const typewriter = createTypewriter((chunk) => {
    patch(messageId, (message) => {
      message.text += chunk
    })
  })
  try {
    await readSse(response, (event) => {
      if (event.type === 'thinking' && event.text) {
        patch(messageId, (message) => {
          applyThinking(message, event)
        })
      } else if (event.type === 'question') {
        patch(messageId, (message) => {
          message.questions = [...(message.questions || []), event.question as Question]
        })
      } else if (event.type === 'decision' && event.decision) {
        patch(messageId, (message) => {
          message.decision = event.decision
        })
      } else if (event.type === 'token' && event.text) {
        typewriter.push(event.text)
      } else if (event.type === 'error') {
        throw new Error(event.detail || '回复失败')
      }
    })
    await typewriter.flush()
    patch(messageId, (message) => {
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
    class="chat"
    @dragenter.prevent="onDragOver"
    @dragover.prevent="onDragOver"
    @dragleave.prevent="onDragLeave"
    @drop.prevent="onDrop"
  >
    <div v-if="dragging" class="drop-mask">松开即可上传，支持多份简历</div>
    <div class="toolbar">
      <div class="actions">
        <button type="button" class="ghost" :disabled="!chat.messages.length" @click="copyAll">
          复制
        </button>
        <button type="button" class="ghost" :disabled="!chat.messages.length" @click="exportChat">
          导出
        </button>
      </div>
      <p v-if="notice" class="notice">{{ notice }}</p>
    </div>

    <div ref="scroller" class="transcript">
      <div v-if="!chat.messages.length" class="empty">
        <h2>从一份简历或一句追问起</h2>
        <p>生成时展示思考过程，并以打字效果输出说明。</p>
        <button
          type="button"
          class="empty-upload"
          :disabled="!session.connected || chat.sending"
          @click="pickFile"
        >
          选择简历文件
        </button>
        <p class="empty-hint">也可以把 PDF、DOCX、Markdown、TXT 拖到这里，一次多份。</p>
        <p v-if="files.length" class="empty-file">
          已选 {{ files.map((item) => item.name).join('、') }} · 题数 {{ count }}，在下方发送即可
        </p>
      </div>

      <article
        v-for="message in chat.messages"
        :key="message.id"
        class="bubble"
        :data-role="message.role"
        :data-error="message.error || undefined"
      >
        <div class="bubble-head">
          <strong>{{ message.role === 'user' ? '你' : '助手' }}</strong>
          <button type="button" class="ghost tiny" @click="copyText(messageText(message))">
            复制
          </button>
        </div>

        <p v-if="message.fileName" class="file">简历 · {{ message.fileName }}</p>

        <template v-if="message.reports?.length">
          <section v-for="report in message.reports" :key="report.key" class="resume-result">
            <h2>{{ report.name }}</h2>
            <details
              v-if="report.reasoning || report.thinking.length"
              class="thinking"
              :open="message.streaming || undefined"
            >
              <summary>{{ message.streaming ? '正在思考…' : '思考过程' }}</summary>
              <p v-if="report.reasoning" class="reason-stream">{{ report.reasoning }}</p>
              <ol v-if="report.thinking.length">
                <li v-for="(step, index) in report.thinking" :key="`${report.key}-think-${index}`">
                  {{ step }}
                </li>
              </ol>
            </details>
            <p v-if="report.error" class="report-error">{{ report.error }}</p>
            <div
              v-if="report.text"
              class="text md"
              :data-streaming="message.streaming || undefined"
              v-html="renderMarkdown(report.text)"
            />
            <div v-if="report.decision" class="decision" :data-ok="report.decision.recommend">
              <h3>{{ report.decision.recommend ? '推荐面试' : '不推荐面试' }}</h3>
              <ul>
                <li
                  v-for="(reason, index) in report.decision.reasons"
                  :key="`${report.key}-reason-${index}`"
                >
                  {{ reason }}
                </li>
              </ul>
            </div>
            <div v-if="report.profile" class="profile">
              <div>
                <span>方向</span>
                <strong>{{ label(report.profile.focus) }}</strong>
              </div>
              <div>
                <span>年限</span>
                <strong>{{ report.profile.years }}</strong>
              </div>
              <div class="wide">
                <span>技能</span>
                <strong>{{ report.profile.skills.join('、') || '未识别' }}</strong>
              </div>
              <div class="wide">
                <span>摘要</span>
                <strong>{{ report.profile.summary || '无' }}</strong>
              </div>
            </div>
            <div v-if="report.questions.length" class="packs">
              <section v-for="group in groupedQuestions(report.questions)" :key="group.stage">
                <h3>{{ label(group.stage) }}</h3>
                <article
                  v-for="(item, index) in group.items"
                  :key="`${report.key}-${item.id}`"
                  class="q-card"
                >
                  <p class="q-title">
                    <span>{{ index + 1 }}</span>
                    {{ item.question }}
                  </p>
                  <p class="q-meta">
                    {{ label(item.category) }} · {{ item.topic }} · {{ label(item.difficulty) }}
                    <span v-if="item.source === 'web'" class="src">联网</span>
                    <span v-else-if="item.source === 'probe'" class="src probe">追问</span>
                    <span v-else-if="item.source === 'resume'" class="src resume">简历</span>
                  </p>
                  <p v-if="item.source === 'web' && item.source_url" class="q-source">
                    来源
                    <a :href="item.source_url" target="_blank" rel="noreferrer">{{
                      item.source_title || item.source_url
                    }}</a>
                  </p>
                  <p v-if="item.reason"><em>为什么问</em>{{ item.reason }}</p>
                  <p><em>回答方向</em>{{ item.answer_direction }}</p>
                  <p><em>参考答案</em>{{ item.reference_answer }}</p>
                </article>
              </section>
            </div>
          </section>
        </template>

        <template v-else>
        <details
          v-if="message.reasoning || message.thinking?.length"
          class="thinking"
          :open="message.streaming || undefined"
        >
          <summary>{{ message.streaming ? '正在思考…' : '思考过程' }}</summary>
          <p v-if="message.reasoning" class="reason-stream">{{ message.reasoning }}</p>
          <ol v-if="message.thinking?.length">
            <li v-for="(step, index) in message.thinking" :key="`${message.id}-${index}`">
              {{ step }}
            </li>
          </ol>
        </details>

        <div
          v-if="message.role === 'assistant' && message.text"
          class="text md"
          :data-streaming="message.streaming || undefined"
          v-html="renderMarkdown(message.text)"
        />
        <p v-else-if="message.text" class="text" :data-streaming="message.streaming || undefined">
          {{ message.text }}
        </p>

        <div v-if="message.decision" class="decision" :data-ok="message.decision.recommend">
          <h3>{{ message.decision.recommend ? '推荐面试' : '不推荐面试' }}</h3>
          <ul>
            <li v-for="(reason, index) in message.decision.reasons" :key="`${message.id}-reason-${index}`">
              {{ reason }}
            </li>
          </ul>
        </div>

        <div v-if="message.profile" class="profile">
          <div>
            <span>方向</span>
            <strong>{{ label(message.profile.focus) }}</strong>
          </div>
          <div>
            <span>年限</span>
            <strong>{{ message.profile.years }}</strong>
          </div>
          <div class="wide">
            <span>技能</span>
            <strong>{{ message.profile.skills.join('、') || '未识别' }}</strong>
          </div>
          <div class="wide">
            <span>摘要</span>
            <strong>{{ message.profile.summary || '无' }}</strong>
          </div>
        </div>

        <div v-if="message.questions?.length" class="packs">
          <section v-for="group in groupedQuestions(message.questions)" :key="group.stage">
            <h3>{{ label(group.stage) }}</h3>
            <article v-for="(item, index) in group.items" :key="item.id" class="q-card">
              <p class="q-title">
                <span>{{ index + 1 }}</span>
                {{ item.question }}
              </p>
              <p class="q-meta">
                {{ label(item.category) }} · {{ item.topic }} · {{ label(item.difficulty) }}
                <span v-if="item.source === 'web'" class="src">联网</span>
                <span v-else-if="item.source === 'probe'" class="src probe">追问</span>
                <span v-else-if="item.source === 'resume'" class="src resume">简历</span>
              </p>
              <p v-if="item.source === 'web' && item.source_url" class="q-source">
                来源
                <a :href="item.source_url" target="_blank" rel="noreferrer">{{
                  item.source_title || item.source_url
                }}</a>
              </p>
              <p v-if="item.reason"><em>为什么问</em>{{ item.reason }}</p>
              <p><em>回答方向</em>{{ item.answer_direction }}</p>
              <p><em>参考答案</em>{{ item.reference_answer }}</p>
            </article>
          </section>
        </div>
        </template>
        <span v-if="message.streaming" class="caret" />
      </article>
    </div>

    <form class="composer" @submit.prevent>
      <input
        ref="fileInput"
        class="sr-only"
        type="file"
        multiple
        accept=".pdf,.docx,.md,.markdown,.txt"
        :disabled="!session.connected || chat.sending"
        @change="onFileChange"
      />

      <div v-if="files.length" class="attach-bar">
        <div v-for="(item, index) in files" :key="`${item.name}-${item.size}`" class="attach-chip">
          <span class="attach-name">{{ item.name }}</span>
          <button type="button" class="ghost tiny" @click="removeFile(index)">移除</button>
        </div>
        <label class="attach-count">
          题数
          <input v-model.number="count" type="number" min="10" max="20" :disabled="chat.sending" />
        </label>
      </div>

      <div class="prompts">
        <button
          v-for="item in prompts"
          :key="item"
          type="button"
          class="prompt"
          :disabled="!session.connected || chat.sending"
          @click="usePrompt(item)"
        >
          {{ item }}
        </button>
      </div>
      <div class="composer-box">
        <textarea
          v-model="draft"
          rows="2"
          placeholder="追问某一道：先说回答方向，再给参考答案。Enter 发送，Shift+Enter 换行。"
          :disabled="!session.connected || chat.sending"
          @keydown="onComposerKeydown"
        />
        <div class="composer-foot">
          <button
            type="button"
            class="attach-btn"
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
          <button type="button" class="send" :disabled="!canSend" @click="send">
            {{ chat.sending ? '生成中' : '发送' }}
          </button>
        </div>
      </div>
    </form>
  </section>
</template>

<style scoped>
.chat {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  padding: 8px 24px 14px;
}

.drop-mask {
  position: absolute;
  inset: 12px;
  z-index: 4;
  display: grid;
  place-items: center;
  border: 1.5px dashed var(--accent);
  border-radius: 16px;
  background: color-mix(in srgb, var(--accent) 12%, #fff);
  color: var(--accent);
  font-size: 15px;
  font-weight: 650;
  pointer-events: none;
}

.toolbar {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  flex: none;
  min-height: 28px;
}

.actions {
  display: flex;
  gap: 8px;
}

.ghost,
.send,
.attach-btn,
.empty-upload {
  border-radius: 12px;
  border: 1px solid var(--line);
  background: var(--panel-strong);
  padding: 8px 12px;
}

.ghost.tiny {
  padding: 4px 8px;
  font-size: 13px;
}

.send {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
  min-width: 84px;
}

.notice {
  margin: 0;
  color: var(--accent);
  font-size: 13px;
}

.transcript {
  flex: 1;
  min-height: 0;
  overflow: auto;
  margin-top: 8px;
  padding-right: 4px;
}

.empty {
  display: grid;
  place-content: center;
  justify-items: center;
  min-height: 100%;
  max-width: 420px;
  margin: 0 auto;
  text-align: center;
  animation: rise 500ms ease both;
}

.empty h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 24px;
}

.empty p {
  margin: 8px 0 0;
  color: var(--muted);
  font-size: 14px;
}

.empty-upload {
  margin-top: 12px;
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
  font-weight: 650;
}

.empty-hint {
  margin-top: 10px !important;
}

.empty-file {
  margin-top: 10px !important;
  color: var(--accent) !important;
  font-weight: 600;
}

.bubble {
  box-sizing: border-box;
  width: 92%;
  max-width: none;
  margin: 0 0 16px;
  padding: 18px 22px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel);
  backdrop-filter: blur(10px);
  box-shadow: var(--shadow);
  animation: rise 320ms ease both;
}

.bubble[data-role='user'] {
  margin-left: auto;
  background: linear-gradient(180deg, #e7f7f2, #dff3ec);
}

.bubble[data-role='assistant'] {
  margin-right: auto;
}

.bubble[data-error='true'] {
  background: #fff1f0;
  border-color: #ffd1cc;
}

.bubble-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.file {
  margin: 0 0 8px;
  color: var(--accent);
  font-size: 14px;
  font-weight: 600;
}

.thinking {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(18, 32, 46, 0.04);
}

.thinking summary {
  cursor: pointer;
  font-weight: 650;
  color: var(--muted);
}

.thinking ol {
  margin: 10px 0 0;
  padding-left: 18px;
  color: var(--muted);
  font-size: 14px;
}

.reason-stream {
  margin: 10px 0 0;
  white-space: pre-wrap;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.65;
}

.thinking li + li {
  margin-top: 4px;
}

.text {
  margin: 0;
  white-space: pre-wrap;
}

.text.md {
  white-space: normal;
}

.text.md :deep(p) {
  margin: 0 0 0.75em;
}

.text.md :deep(p:last-child) {
  margin-bottom: 0;
}

.text.md :deep(ul),
.text.md :deep(ol) {
  margin: 0.4em 0 0.75em;
  padding-left: 1.35em;
}

.text.md :deep(li + li) {
  margin-top: 0.25em;
}

.text.md :deep(strong) {
  font-weight: 700;
}

.text.md :deep(code) {
  padding: 0.1em 0.35em;
  border-radius: 6px;
  background: rgba(18, 32, 46, 0.06);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.92em;
}

.text.md :deep(pre) {
  overflow: auto;
  margin: 0.6em 0;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(18, 32, 46, 0.06);
}

.text.md :deep(pre code) {
  padding: 0;
  background: transparent;
}

.text.md :deep(h1),
.text.md :deep(h2),
.text.md :deep(h3) {
  margin: 0.9em 0 0.4em;
  font-family: var(--font-display);
  line-height: 1.25;
}

.text.md :deep(h1:first-child),
.text.md :deep(h2:first-child),
.text.md :deep(h3:first-child) {
  margin-top: 0;
}

.text[data-streaming='true'] {
  min-height: 1.5em;
}

.caret {
  display: inline-block;
  width: 0.55ch;
  height: 1em;
  margin-left: 2px;
  background: var(--accent);
  vertical-align: -0.1em;
  animation: blink 1s steps(1) infinite;
}

.profile {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.profile div {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.7);
}

.profile .wide {
  grid-column: 1 / -1;
}

.profile span {
  display: block;
  color: var(--muted);
  font-size: 12px;
}

.profile strong {
  display: block;
  margin-top: 4px;
  font-weight: 650;
}

.packs {
  display: grid;
  gap: 18px;
  margin-top: 18px;
}

.resume-result {
  display: grid;
  gap: 12px;
  margin-top: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--line, #e7e5e4);
}

.resume-result h2 {
  margin: 0;
  font-size: 15px;
}

.report-error {
  margin: 0;
  color: #9f1239;
}

.packs h3 {
  margin: 0 0 10px;
  font-family: var(--font-display);
  font-size: 22px;
}

.q-card {
  padding: 14px;
  border-radius: 14px;
  background: var(--panel-strong);
  border: 1px solid var(--line);
  animation: rise 280ms ease both;
}

.q-card + .q-card {
  margin-top: 10px;
}

.q-title {
  display: flex;
  gap: 10px;
  margin: 0;
  font-weight: 700;
  line-height: 1.45;
}

.q-title span {
  display: inline-grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 12px;
  flex: none;
}

.q-meta {
  margin: 6px 0 10px;
  color: var(--muted);
  font-size: 13px;
}

.q-meta .src {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 8px;
  border-radius: 999px;
  background: #e8eef8;
  color: #2f5f9e;
  font-size: 12px;
  font-weight: 700;
}

.q-meta .src.probe {
  background: #f3e8f8;
  color: #6b3d8f;
}

.q-meta .src.resume {
  background: var(--accent-soft);
  color: var(--accent);
}

.q-source {
  margin: -4px 0 10px !important;
  color: var(--muted);
  font-size: 13px;
}

.q-source a {
  color: var(--accent);
  text-decoration: none;
}

.q-source a:hover {
  text-decoration: underline;
}

.q-card p {
  margin: 0;
  line-height: 1.65;
}

.q-card p + p {
  margin-top: 8px;
}

.q-card em {
  display: inline-block;
  margin-right: 8px;
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-style: normal;
  font-size: 12px;
  font-weight: 700;
}

.composer {
  flex: none;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--line);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}

.attach-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 10px;
}

.attach-chip {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  max-width: 100%;
  padding: 6px 8px 6px 12px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 13px;
  font-weight: 600;
}

.attach-name {
  overflow: hidden;
  max-width: 220px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.attach-count {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-weight: 500;
}

.attach-count input {
  width: 56px;
  padding: 2px 6px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  color: var(--ink);
}

.prompts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.prompt {
  border-radius: 999px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.8);
  padding: 6px 12px;
  color: var(--muted);
  font-size: 13px;
  text-align: left;
}

.prompt:hover:not(:disabled) {
  color: var(--accent);
  border-color: rgba(11, 122, 106, 0.35);
  background: var(--accent-soft);
}

.decision {
  margin-top: 12px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid #ffd1cc;
  background: #fff6f5;
}

.decision[data-ok='true'] {
  border-color: rgba(11, 122, 106, 0.28);
  background: #f3fbf8;
}

.decision h3 {
  margin: 0 0 8px;
  font-family: var(--font-display);
  font-size: 22px;
}

.decision ul {
  margin: 0;
  padding-left: 1.2em;
}

.decision li + li {
  margin-top: 6px;
}

.composer-box {
  display: grid;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: var(--shadow);
}

.composer-box textarea {
  width: 100%;
  resize: vertical;
  min-height: 56px;
  padding: 4px 4px 0;
  border: 0;
  background: transparent;
  outline: none;
}

.composer-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.attach-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  background: transparent;
}

.attach-btn:hover:not(:disabled) {
  color: var(--accent);
  border-color: rgba(11, 122, 106, 0.35);
  background: var(--accent-soft);
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

@media (max-width: 860px) {
  .chat {
    padding: 8px 16px 12px;
  }

  .profile {
    grid-template-columns: 1fr;
  }
}
</style>
