<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import IGButton from '@/components/IGButton.vue'
import IGDrawer from '@/components/IGDrawer.vue'
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

onMounted(() => {
  void session.refresh()
})
</script>

<template>
  <div
    class="relative grid grid-cols-[200px_minmax(0,1fr)] h-screen overflow-hidden max-md:grid-cols-1 max-md:grid-rows-[auto_minmax(0,1fr)] max-md:h-auto max-md:min-h-screen max-md:overflow-visible"
  >
    <aside
      class="bg-rail flex flex-col min-h-0 overflow-hidden px-3 py-4 text-[#f4faf8] shadow-[inset_-1px_0_0_rgba(255,255,255,0.06)] max-md:max-h-[36vh]"
    >
      <div class="flex items-center gap-2.5">
        <img class="block size-8 rounded-lg flex-none" src="/logo.svg" alt="" width="32" height="32" />
        <div>
          <p class="m-0 font-display text-[22px] leading-[1.1] tracking-[-0.03em]">面试助手</p>
          <p class="mt-1 mb-0 text-[11px] text-[rgba(244,250,248,0.62)]">由浅入深</p>
        </div>
      </div>

      <button
        type="button"
        class="mt-3 flex h-8 w-full items-center justify-center gap-1 rounded-lg border border-dashed border-[rgba(255,255,255,0.28)] bg-[rgba(255,255,255,0.06)] px-2 text-[13px] [font-weight:650] text-inherit hover:bg-[rgba(255,255,255,0.12)]"
        @click="chat.createNewThread()"
      >
        <span class="text-[15px] leading-none" aria-hidden="true">+</span>
        新建对话
      </button>

      <div
        class="scroll-thin-on-dark mt-2.5 grid flex-1 min-h-0 auto-rows-min content-start gap-1 overflow-auto max-md:max-h-[140px]"
        role="list"
      >
        <button
          v-for="thread in sortedThreads"
          :key="thread.id"
          type="button"
          class="group flex w-full items-center self-start gap-1 rounded-lg border-0 bg-transparent px-2 py-1.5 text-left text-inherit hover:bg-[rgba(255,255,255,0.08)] data-[active=true]:bg-[rgba(255,255,255,0.14)]"
          role="listitem"
          :data-active="thread.id === chat.activeId"
          @click="chat.selectThread(thread.id)"
        >
          <span class="grid flex-1 min-w-0 gap-px">
            <span
              class="flex items-center gap-1.5 overflow-hidden text-ellipsis whitespace-nowrap text-[13px] font-semibold leading-[1.25]"
            >
              <!-- 生成中的会话：呼吸点提示，切换回来可继续看流式输出 -->
              <span
                v-if="chat.sendingIds.has(thread.id)"
                class="size-1.5 flex-none animate-pulse rounded-full bg-[#9ef0d4]"
                aria-label="生成中"
              />
              <span class="overflow-hidden text-ellipsis whitespace-nowrap">{{ thread.title }}</span>
            </span>
            <span class="text-[11px] leading-[1.2] text-[rgba(244,250,248,0.5)]">
              {{ thread.messages.length }} 条 · {{ formatTime(thread.updatedAt) }}
            </span>
          </span>
          <span
            v-if="!chat.sendingIds.has(thread.id)"
            class="hidden size-5 flex-none place-items-center rounded-md text-[14px] text-[rgba(244,250,248,0.7)] group-hover:grid group-data-[active=true]:grid hover:bg-[rgba(255,255,255,0.12)] hover:text-white"
            title="删除"
            @click.stop="chat.removeThread(thread.id)"
          >
            ×
          </span>
        </button>
      </div>

      <div class="mt-2.5 border-t border-[rgba(255,255,255,0.1)] pt-2.5">
        <p class="m-0 text-xs text-[#ffb4a8] data-[ok=true]:text-[#9ef0d4]" :data-ok="session.connected">
          {{ session.statusText }}
        </p>
        <p v-if="session.kb" class="mt-1 mb-0 text-xs text-[rgba(244,250,248,0.55)]">
          题库 {{ session.kb.total }} 道
        </p>
      </div>
    </aside>

    <main class="flex min-w-0 min-h-0 flex-col overflow-hidden max-md:min-h-[60vh]">
      <header
        class="flex flex-none items-start justify-between gap-4 border-b border-line/10 bg-white/90 px-6 py-3 pb-2.5 max-md:flex-col"
      >
        <div>
          <p class="eyebrow tracking-[0.12em] text-[10px]">Interview Studio</p>
          <h1 class="mt-0.5 mb-0 font-display text-lg leading-[1.2] tracking-[-0.02em] font-semibold">
            {{ chat.activeThread?.title || '对话出题' }}
          </h1>
          <p class="mt-1 mb-0 text-xs text-muted">当前会话上下文随请求带上；本机可缓存画像备查。</p>
        </div>
        <div class="flex flex-wrap justify-end gap-2">
          <IGButton
            variant="tool"
            class="group"
            :active="panel === 'memory'"
            @click="openPanel('memory')"
          >
            长期记忆
            <span
              v-if="chat.hasMemory"
              class="size-1.5 rounded-full bg-accent group-data-[on=true]:bg-white"
            />
          </IGButton>
          <IGButton variant="tool" :active="panel === 'kb'" @click="openPanel('kb')">知识库</IGButton>
          <IGButton variant="tool" :active="panel === 'mcp'" @click="openPanel('mcp')">MCP</IGButton>
        </div>
      </header>
      <ChatView class="min-h-0 flex-1 overflow-hidden" />
    </main>

    <IGDrawer
      :open="!!panel"
      :title="panelTitle"
      :size="panel === 'kb' ? 'lg' : 'sm'"
      :body-scroll="panel !== 'kb'"
      @close="closePanel"
    >
      <div v-if="panel === 'memory'" class="px-[18px] py-4 pb-7">
        <p
          class="mb-3.5 mt-0 rounded-xl bg-[rgba(18,32,46,0.04)] px-3 py-2.5 text-[13px] leading-[1.55] text-muted"
        >
          后端不做长期记忆落库：追问时只接收前端传来的
          <code class="text-xs">context</code>（最多约 1.2 万字）和当前会话
          <code class="text-xs">messages</code>，请求结束即丢弃。下面内容仅缓存在本机，方便你查看或手动补充。
        </p>
        <div v-if="chat.hasMemory" class="grid gap-2">
          <p v-if="chat.memory.focus" class="m-0 text-sm leading-normal">
            <em class="pill-em">方向</em>{{ label(chat.memory.focus) }}
          </p>
          <p v-if="chat.memory.years" class="m-0 text-sm leading-normal">
            <em class="pill-em">年限</em>{{ chat.memory.years }}
          </p>
          <p v-if="chat.memory.skills.length" class="m-0 text-sm leading-normal">
            <em class="pill-em">技能</em>{{ chat.memory.skills.join('、') }}
          </p>
          <p v-if="chat.memory.projects.length" class="m-0 text-sm leading-normal">
            <em class="pill-em">项目</em>{{ chat.memory.projects.join('、') }}
          </p>
          <p v-if="chat.memory.summary" class="m-0 text-sm leading-normal">
            <em class="pill-em">摘要</em>{{ chat.memory.summary }}
          </p>
        </div>
        <p v-else class="m-0 text-sm leading-normal text-muted">
          还没有画像。上传简历出题后，会把摘要缓存在本机。
        </p>
        <label class="mt-3.5 grid gap-1.5 text-[13px] text-muted">
          备注
          <textarea
            v-model="memoryDraft"
            class="w-full resize-y rounded-xl border border-line/10 bg-white px-3 py-2.5 font-inherit text-ink"
            rows="4"
            placeholder="例如：偏前端工程化，少问算法。"
          />
        </label>
        <div class="mt-3 flex justify-end gap-2">
          <IGButton size="sm" @click="clearMemory">清空</IGButton>
          <IGButton variant="accent" size="sm" @click="saveMemoryNotes">保存备注</IGButton>
        </div>
      </div>
      <KnowledgeView v-else-if="panel === 'kb'" embedded />
      <McpView v-else-if="panel === 'mcp'" embedded />
    </IGDrawer>
  </div>
</template>
