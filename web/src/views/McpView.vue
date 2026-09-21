<script setup lang="ts">
import { onMounted, ref } from 'vue'

defineProps<{ embedded?: boolean }>()

type Parameter = {
  name: string
  type: string
  required: boolean
  description: string
  default?: string | number
}

type Tool = {
  name: string
  title: string
  description: string
  parameters: Parameter[]
}

type ServerInfo = {
  name: string
  transport: string
  config: string
  command: string
  summary: string
}

const server = ref<ServerInfo | null>(null)
const tools = ref<Tool[]>([])
const loading = ref(true)
const errorText = ref('')

async function load() {
  loading.value = true
  errorText.value = ''
  try {
    const response = await fetch('/api/mcp')
    if (!response.ok) throw new Error(`请求失败（${response.status}）`)
    const payload = (await response.json()) as { server: ServerInfo; tools: Tool[] }
    server.value = payload.server
    tools.value = payload.tools
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section :class="embedded ? 'page-embedded scroll-thin' : 'page-shell scroll-thin'">
    <header v-if="!embedded">
      <p class="eyebrow">Protocol</p>
      <h1 class="mt-1.5 mb-0 font-display text-[clamp(32px,4vw,44px)] tracking-[-0.03em]">MCP</h1>
      <p class="text-muted">当前注册给 Cursor 的本地接口。页面只读，不在浏览器里调用这些工具。</p>
    </header>
    <p v-else class="m-0 text-muted">
      推荐流程在知识库缺口时会自动调用联网查题；本页只展示接口说明，不在浏览器里直接搜。
    </p>

    <p v-if="loading">正在读取接口…</p>
    <p v-else-if="errorText" class="text-warn">{{ errorText }}</p>
    <template v-else-if="server">
      <section class="panel-card mt-[18px] max-w-[760px] px-5 py-[18px]">
        <h2 class="m-0 font-display text-2xl">{{ server.name }}</h2>
        <p class="text-muted">{{ server.summary }}</p>
        <dl class="mt-3 mb-0 grid gap-2">
          <div class="grid grid-cols-[52px_1fr] gap-2">
            <dt class="text-muted">传输</dt>
            <dd class="m-0">{{ server.transport }}</dd>
          </div>
          <div class="grid grid-cols-[52px_1fr] gap-2">
            <dt class="text-muted">配置</dt>
            <dd class="m-0">{{ server.config }}</dd>
          </div>
          <div class="grid grid-cols-[52px_1fr] gap-2">
            <dt class="text-muted">启动</dt>
            <dd class="m-0">
              <code class="font-mono text-[13px]">{{ server.command }}</code>
            </dd>
          </div>
        </dl>
      </section>

      <article v-for="tool in tools" :key="tool.name" class="panel-card mt-[18px] max-w-[760px] px-5 py-[18px]">
        <h2 class="m-0 font-display text-2xl">{{ tool.title }}</h2>
        <p class="mb-2 mt-1 font-mono text-[13px] text-muted">{{ tool.name }}</p>
        <p class="text-muted">{{ tool.description }}</p>
        <table class="mt-3 w-full border-collapse text-sm">
          <thead>
            <tr>
              <th class="border-t border-line/10 px-1.5 py-2 text-left align-top">参数</th>
              <th class="border-t border-line/10 px-1.5 py-2 text-left align-top">类型</th>
              <th class="border-t border-line/10 px-1.5 py-2 text-left align-top">必填</th>
              <th class="border-t border-line/10 px-1.5 py-2 text-left align-top">说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="param in tool.parameters" :key="param.name">
              <td class="border-t border-line/10 px-1.5 py-2 text-left align-top">{{ param.name }}</td>
              <td class="border-t border-line/10 px-1.5 py-2 text-left align-top">{{ param.type }}</td>
              <td class="border-t border-line/10 px-1.5 py-2 text-left align-top">
                {{ param.required ? '是' : '否' }}
              </td>
              <td class="border-t border-line/10 px-1.5 py-2 text-left align-top">
                {{ param.description }}
                <span v-if="param.default !== undefined">默认 {{ param.default }}。</span>
              </td>
            </tr>
          </tbody>
        </table>
      </article>
    </template>
  </section>
</template>
