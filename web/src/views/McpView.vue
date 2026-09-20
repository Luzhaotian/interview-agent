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
  <section class="page" :data-embedded="embedded || undefined">
    <header v-if="!embedded">
      <p class="eyebrow">Protocol</p>
      <h1>MCP</h1>
      <p>当前注册给 Cursor 的本地接口。页面只读，不在浏览器里调用这些工具。</p>
    </header>
    <p v-else class="embedded-lead">
      推荐流程在知识库缺口时会自动调用联网查题；本页只展示接口说明，不在浏览器里直接搜。
    </p>

    <p v-if="loading">正在读取接口…</p>
    <p v-else-if="errorText" class="error">{{ errorText }}</p>
    <template v-else-if="server">
      <section class="card">
        <h2>{{ server.name }}</h2>
        <p>{{ server.summary }}</p>
        <dl>
          <div>
            <dt>传输</dt>
            <dd>{{ server.transport }}</dd>
          </div>
          <div>
            <dt>配置</dt>
            <dd>{{ server.config }}</dd>
          </div>
          <div>
            <dt>启动</dt>
            <dd>
              <code>{{ server.command }}</code>
            </dd>
          </div>
        </dl>
      </section>

      <article v-for="tool in tools" :key="tool.name" class="card">
        <h2>{{ tool.title }}</h2>
        <p class="name">{{ tool.name }}</p>
        <p>{{ tool.description }}</p>
        <table>
          <thead>
            <tr>
              <th>参数</th>
              <th>类型</th>
              <th>必填</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="param in tool.parameters" :key="param.name">
              <td>{{ param.name }}</td>
              <td>{{ param.type }}</td>
              <td>{{ param.required ? '是' : '否' }}</td>
              <td>
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

<style scoped>
.page {
  height: 100vh;
  overflow: auto;
  padding: 28px 32px 48px;
}

.page[data-embedded='true'] {
  height: auto;
  min-height: 100%;
  padding: 16px 18px 32px;
}

.embedded-lead {
  margin: 0;
  color: var(--muted);
}

.eyebrow {
  margin: 0;
  color: var(--accent);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-size: 12px;
  font-weight: 700;
}

h1 {
  margin: 6px 0 0;
  font-family: var(--font-display);
  font-size: clamp(32px, 4vw, 44px);
  letter-spacing: -0.03em;
}

header p,
.card p {
  color: var(--muted);
}

.card {
  max-width: 760px;
  margin-top: 18px;
  padding: 18px 20px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: var(--panel);
  backdrop-filter: blur(8px);
  box-shadow: var(--shadow);
}

h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 24px;
}

.name {
  margin: 4px 0 8px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
}

dl {
  display: grid;
  gap: 8px;
  margin: 12px 0 0;
}

dl div {
  display: grid;
  grid-template-columns: 52px 1fr;
  gap: 8px;
}

dt {
  color: var(--muted);
}

dd {
  margin: 0;
}

code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
}

table {
  width: 100%;
  margin-top: 12px;
  border-collapse: collapse;
  font-size: 14px;
}

th,
td {
  padding: 8px 6px;
  border-top: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
}

.error {
  color: var(--warn);
}

@media (max-width: 860px) {
  .page {
    height: auto;
    padding: 16px;
  }
}
</style>
