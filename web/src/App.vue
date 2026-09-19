<script setup lang="ts">
import { onMounted, ref } from 'vue'

type KbStats = {
  total: number
  counts: Record<string, number>
}

type Profile = {
  years: string
  focus: string
  skills: string[]
  projects: string[]
  summary: string
}

type Question = {
  id: string
  category: string
  topic: string
  difficulty: string
  question: string
  reason: string
  answer_outline: string
}

const labels: Record<string, string> = {
  frontend: '前端',
  agent: 'Agent',
  backend: '后端',
  easy: '简单',
  medium: '中等',
  hard: '困难',
}

const connected = ref(false)
const statusText = ref('正在连接后端…')
const kb = ref<KbStats | null>(null)
const file = ref<File | null>(null)
const count = ref(15)
const loading = ref(false)
const errorText = ref('')
const profile = ref<Profile | null>(null)
const questions = ref<Question[]>([])

function label(value: string) {
  return labels[value] || value
}

async function errorMessage(response: Response) {
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') return body.detail
  } catch {
    // 非 JSON 错误页，走下面的通用文案
  }
  return `请求失败（${response.status}）`
}

async function loadStatus() {
  try {
    const health = await fetch('/api/health')
    if (!health.ok) throw new Error(await errorMessage(health))
    const kbResponse = await fetch('/api/kb')
    if (!kbResponse.ok) throw new Error(await errorMessage(kbResponse))
    kb.value = (await kbResponse.json()) as KbStats
    connected.value = true
    statusText.value = '后端已连接'
  } catch {
    connected.value = false
    statusText.value = '后端未连接'
  }
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  file.value = input.files?.[0] ?? null
}

async function recommend() {
  if (!file.value || loading.value) return
  loading.value = true
  errorText.value = ''
  profile.value = null
  questions.value = []
  const body = new FormData()
  body.append('file', file.value)
  body.append('count', String(count.value))
  try {
    const response = await fetch('/api/recommend', { method: 'POST', body })
    if (!response.ok) throw new Error(await errorMessage(response))
    const result = (await response.json()) as { profile: Profile; questions: Question[] }
    profile.value = result.profile
    questions.value = result.questions
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : '生成失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadStatus)
</script>

<template>
  <main class="page">
    <header>
      <p class="eyebrow">面试题推荐</p>
      <h1>根据简历出题</h1>
      <p class="status" :data-ok="connected">{{ statusText }}</p>
      <p v-if="kb" class="meta">
        知识库 {{ kb.total }} 道：前端 {{ kb.counts.frontend || 0 }}，Agent
        {{ kb.counts.agent || 0 }}，后端 {{ kb.counts.backend || 0 }}
      </p>
    </header>

    <form class="panel" @submit.prevent="recommend">
      <label>
        简历
        <input
          type="file"
          accept=".pdf,.docx,.md,.markdown,.txt"
          :disabled="!connected || loading"
          @change="onFileChange"
        />
      </label>
      <label>
        题目数量
        <input v-model.number="count" type="number" min="10" max="20" :disabled="loading" />
      </label>
      <button type="submit" :disabled="!connected || !file || loading">
        {{ loading ? '正在生成…' : '生成面试题' }}
      </button>
      <p v-if="loading" class="hint">读简历和选题大概需要一两分钟。</p>
      <p v-if="errorText" class="error">{{ errorText }}</p>
    </form>

    <section v-if="profile" class="panel">
      <h2>简历画像</h2>
      <ul>
        <li>方向：{{ label(profile.focus) }}</li>
        <li>年限：{{ profile.years }}</li>
        <li>技能：{{ profile.skills.join('、') || '未识别' }}</li>
        <li>项目：{{ profile.projects.join('、') || '未识别' }}</li>
        <li>摘要：{{ profile.summary || '无' }}</li>
      </ul>
    </section>

    <section v-if="questions.length" class="questions">
      <h2>题目</h2>
      <article v-for="(item, index) in questions" :key="item.id">
        <h3>
          {{ index + 1 }}.
          <span>{{ label(item.category) }} / {{ item.topic }} / {{ label(item.difficulty) }}</span>
          {{ item.question }}
        </h3>
        <p><strong>为什么问：</strong>{{ item.reason }}</p>
        <p><strong>答题要点：</strong>{{ item.answer_outline }}</p>
      </article>
    </section>
  </main>
</template>

<style>
body {
  margin: 0;
  background: #f4f1ea;
  color: #1c1917;
  font-family: 'Avenir Next', 'PingFang SC', 'Noto Sans SC', sans-serif;
}
</style>

<style scoped>
.page {
  max-width: 760px;
  margin: 0 auto;
  padding: 48px 20px 80px;
}

.eyebrow {
  margin: 0;
  color: #78716c;
  letter-spacing: 0.08em;
}

h1 {
  margin: 8px 0 12px;
  font-size: 36px;
  line-height: 1.2;
}

.status {
  display: inline-block;
  margin: 0;
  padding: 4px 10px;
  border-radius: 999px;
  background: #fee2e2;
  color: #991b1b;
}

.status[data-ok='true'] {
  background: #dcfce7;
  color: #166534;
}

.meta,
.hint {
  color: #57534e;
}

.panel,
article {
  margin-top: 20px;
  padding: 20px;
  background: #fff;
  border: 1px solid #e7e5e4;
  border-radius: 12px;
}

form {
  display: grid;
  gap: 14px;
}

label {
  display: grid;
  gap: 6px;
  font-weight: 600;
}

input[type='number'] {
  width: 96px;
  padding: 8px 10px;
  border: 1px solid #d6d3d1;
  border-radius: 8px;
  font: inherit;
}

button {
  width: fit-content;
  padding: 10px 16px;
  border: 0;
  border-radius: 8px;
  background: #1c1917;
  color: #fff;
  font: inherit;
  cursor: pointer;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.error {
  margin: 0;
  color: #b91c1c;
}

h2 {
  margin: 0 0 12px;
  font-size: 20px;
}

ul {
  margin: 0;
  padding-left: 18px;
}

li + li {
  margin-top: 6px;
}

article h3 {
  margin: 0 0 10px;
  font-size: 18px;
  line-height: 1.45;
}

article h3 span {
  display: inline-block;
  margin-right: 8px;
  color: #78716c;
  font-size: 13px;
  font-weight: 600;
}

article p {
  margin: 8px 0 0;
  line-height: 1.6;
}
</style>
