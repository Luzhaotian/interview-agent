<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { label } from '@/lib/labels'
import KnowledgeView from '@/views/KnowledgeView.vue'
import McpView from '@/views/McpView.vue'
import ChatView from '@/views/ChatView.vue'
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
const chat = useChatStore()

const panel = ref<'memory' | 'kb' | 'mcp' | null>(null)
const memoryDraft = ref(chat.memory.notes)

const sortedThreads = computed(() =>
  [...chat.threads].sort((a, b) => b.updatedAt - a.updatedAt),
)

const panelTitle = computed(() => {
  if (panel.value === 'memory') return '长期记忆'
  if (panel.value === 'kb') return '知识库'
  if (panel.value === 'mcp') return 'MCP'
  return ''
})

watch(
  () => chat.memory.notes,
  (notes) => {
    memoryDraft.value = notes
  },
)

watch(panel, (name) => {
  if (name === 'memory') memoryDraft.value = chat.memory.notes
})

function formatTime(ts: number) {
  if (!ts) return ''
  const date = new Date(ts)
  const now = new Date()
  const sameDay = date.toDateString() === now.toDateString()
  if (sameDay) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}

function openPanel(name: 'memory' | 'kb' | 'mcp') {
  panel.value = panel.value === name ? null : name
}

function closePanel() {
  panel.value = null
}

function saveMemoryNotes() {
  chat.updateMemoryNotes(memoryDraft.value)
}

function clearMemory() {
  chat.clearMemory()
  memoryDraft.value = ''
}

function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape') closePanel()
}

onMounted(() => {
  void session.refresh()
  window.addEventListener('keydown', onKey)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div class="shell">
    <aside class="rail">
      <div class="brand-block">
        <img class="logo" src="/logo.svg" alt="" width="32" height="32" />
        <div>
          <p class="brand">面试助手</p>
          <p class="tagline">由浅入深</p>
        </div>
      </div>

      <button type="button" class="new-chat" :disabled="chat.sending" @click="chat.createNewThread()">
        <span aria-hidden="true">+</span>
        新建对话
      </button>

      <div class="thread-list" role="list">
        <button
          v-for="thread in sortedThreads"
          :key="thread.id"
          type="button"
          class="thread"
          role="listitem"
          :data-active="thread.id === chat.activeId"
          :disabled="chat.sending"
          @click="chat.selectThread(thread.id)"
        >
          <span class="thread-main">
            <span class="thread-title">{{ thread.title }}</span>
            <span class="thread-meta">
              {{ thread.messages.length }} 条 · {{ formatTime(thread.updatedAt) }}
            </span>
          </span>
          <span class="thread-delete" title="删除" @click.stop="chat.removeThread(thread.id)">
            ×
          </span>
        </button>
      </div>

      <div class="rail-foot">
        <p class="status" :data-ok="session.connected">{{ session.statusText }}</p>
        <p v-if="session.kb" class="kb-count">题库 {{ session.kb.total }} 道</p>
      </div>
    </aside>

    <main class="workspace">
      <header class="topbar">
        <div class="topbar-copy">
          <p class="eyebrow">Interview Studio</p>
          <h1>{{ chat.activeThread?.title || '对话出题' }}</h1>
          <p class="topbar-lead">当前会话上下文随请求带上；本机可缓存画像备查。</p>
        </div>
        <div class="topbar-tools">
          <button
            type="button"
            class="tool"
            :data-on="panel === 'memory'"
            @click="openPanel('memory')"
          >
            长期记忆
            <span v-if="chat.hasMemory" class="dot" />
          </button>
          <button type="button" class="tool" :data-on="panel === 'kb'" @click="openPanel('kb')">
            知识库
          </button>
          <button type="button" class="tool" :data-on="panel === 'mcp'" @click="openPanel('mcp')">
            MCP
          </button>
        </div>
      </header>
      <ChatView class="stage" />
    </main>

    <div v-if="panel" class="drawer-backdrop" @click="closePanel" />
    <aside v-if="panel" class="drawer" :aria-label="panelTitle">
      <div class="drawer-head">
        <strong>{{ panelTitle }}</strong>
        <button type="button" class="ghost" @click="closePanel">关闭</button>
      </div>
      <div class="drawer-body">
        <div v-if="panel === 'memory'" class="memory-drawer">
          <p class="memory-hint">
            后端不做长期记忆落库：追问时只接收前端传来的
            <code>context</code>（最多约 1.2 万字）和当前会话
            <code>messages</code>，请求结束即丢弃。下面内容仅缓存在本机，方便你查看或手动补充。
          </p>
          <div v-if="chat.hasMemory" class="memory-facts">
            <p v-if="chat.memory.focus"><em>方向</em>{{ label(chat.memory.focus) }}</p>
            <p v-if="chat.memory.years"><em>年限</em>{{ chat.memory.years }}</p>
            <p v-if="chat.memory.skills.length"><em>技能</em>{{ chat.memory.skills.join('、') }}</p>
            <p v-if="chat.memory.projects.length">
              <em>项目</em>{{ chat.memory.projects.join('、') }}
            </p>
            <p v-if="chat.memory.summary"><em>摘要</em>{{ chat.memory.summary }}</p>
          </div>
          <p v-else class="memory-empty">还没有画像。上传简历出题后，会把摘要缓存在本机。</p>
          <label class="memory-notes">
            备注
            <textarea
              v-model="memoryDraft"
              rows="4"
              placeholder="例如：偏前端工程化，少问算法。"
            />
          </label>
          <div class="memory-actions">
            <button type="button" class="ghost" @click="clearMemory">清空</button>
            <button type="button" class="accent" @click="saveMemoryNotes">保存备注</button>
          </div>
        </div>
        <KnowledgeView v-else-if="panel === 'kb'" embedded />
        <McpView v-else embedded />
      </div>
    </aside>
  </div>
</template>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: 200px minmax(0, 1fr);
  height: 100vh;
  overflow: hidden;
  position: relative;
}

.rail {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  padding: 16px 12px;
  background:
    linear-gradient(180deg, rgba(18, 32, 46, 0.98), rgba(14, 58, 56, 0.92)),
    #12202e;
  color: #f4faf8;
  box-shadow: inset -1px 0 0 rgba(255, 255, 255, 0.06);
}

.brand-block {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo {
  display: block;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  flex: none;
}

.brand {
  margin: 0;
  font-family: var(--font-display);
  font-size: 22px;
  line-height: 1.1;
  letter-spacing: -0.03em;
}

.tagline {
  margin: 4px 0 0;
  color: rgba(244, 250, 248, 0.62);
  font-size: 11px;
}

.new-chat {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 12px;
  width: 100%;
  height: 32px;
  padding: 0 8px;
  border: 1px dashed rgba(255, 255, 255, 0.28);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  color: inherit;
  font-size: 13px;
  font-weight: 650;
}

.new-chat:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.12);
}

.new-chat span {
  font-size: 15px;
  line-height: 1;
}

.thread-list {
  display: grid;
  grid-auto-rows: min-content;
  align-content: start;
  gap: 4px;
  margin-top: 10px;
  overflow: auto;
  flex: 1;
  min-height: 0;
}

.thread {
  display: flex;
  align-items: center;
  align-self: start;
  gap: 4px;
  width: 100%;
  padding: 6px 8px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: inherit;
  text-align: left;
}

.thread:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
}

.thread[data-active='true'] {
  background: rgba(255, 255, 255, 0.14);
}

.thread-main {
  display: grid;
  gap: 1px;
  min-width: 0;
  flex: 1;
}

.thread-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.25;
}

.thread-meta {
  color: rgba(244, 250, 248, 0.5);
  font-size: 11px;
  line-height: 1.2;
}

.thread-delete {
  display: none;
  width: 20px;
  height: 20px;
  place-items: center;
  border-radius: 6px;
  color: rgba(244, 250, 248, 0.7);
  font-size: 14px;
  flex: none;
}

.thread:hover .thread-delete,
.thread[data-active='true'] .thread-delete {
  display: grid;
}

.thread-delete:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
}

.rail-foot {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.status {
  margin: 0;
  color: #ffb4a8;
  font-size: 12px;
}

.status[data-ok='true'] {
  color: #9ef0d4;
}

.kb-count {
  margin: 4px 0 0;
  color: rgba(244, 250, 248, 0.55);
  font-size: 12px;
}

.workspace {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex: none;
  padding: 12px 24px 10px;
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.55);
}

.eyebrow {
  margin: 0;
  color: var(--accent);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-size: 10px;
  font-weight: 700;
}

.topbar h1 {
  margin: 2px 0 0;
  font-family: var(--font-display);
  font-size: 18px;
  line-height: 1.2;
  letter-spacing: -0.02em;
  font-weight: 600;
}

.topbar-lead {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 12px;
}

.topbar-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.tool,
.ghost,
.accent {
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--panel-strong);
  padding: 6px 12px;
  font-size: 13px;
}

.tool {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.tool .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
}

.tool[data-on='true'] {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.tool[data-on='true'] .dot {
  background: #fff;
}

.accent {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.stage {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.drawer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(18, 32, 46, 0.28);
  backdrop-filter: blur(2px);
  z-index: 20;
}

.drawer {
  position: fixed;
  top: 0;
  right: 0;
  z-index: 30;
  display: flex;
  flex-direction: column;
  width: min(480px, 100vw);
  height: 100vh;
  background: #f7faf8;
  box-shadow: -18px 0 50px rgba(18, 32, 46, 0.16);
}

.drawer-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.9);
}

.drawer-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.memory-drawer {
  padding: 16px 18px 28px;
}

.memory-hint {
  margin: 0 0 14px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(18, 32, 46, 0.04);
  color: var(--muted);
  font-size: 13px;
  line-height: 1.55;
}

.memory-hint code {
  font-size: 12px;
}

.memory-facts {
  display: grid;
  gap: 8px;
}

.memory-facts p,
.memory-empty {
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
}

.memory-empty {
  color: var(--muted);
}

.memory-facts em {
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

.memory-notes {
  display: grid;
  gap: 6px;
  margin-top: 14px;
  font-size: 13px;
  color: var(--muted);
}

.memory-notes textarea {
  width: 100%;
  resize: vertical;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fff;
  color: var(--ink);
  font: inherit;
}

.memory-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

@media (max-width: 860px) {
  .shell {
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(0, 1fr);
    height: auto;
    min-height: 100vh;
    overflow: visible;
  }

  .rail {
    max-height: 36vh;
  }

  .thread-list {
    max-height: 140px;
  }

  .topbar {
    flex-direction: column;
  }

  .workspace {
    min-height: 60vh;
  }
}
</style>
