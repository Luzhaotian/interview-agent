<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { label } from '@/lib/labels'

defineProps<{ embedded?: boolean }>()

type KbQuestion = {
  id: string
  category: string
  topic: string
  tags: string[]
  difficulty: string
  question: string
  answer_outline: string
}

const questions = ref<KbQuestion[]>([])
const loading = ref(true)
const errorText = ref('')
const keyword = ref('')
const category = ref('all')
const difficulty = ref('')
const activeTag = ref('')
const openId = ref('')

const categories = [
  { id: 'all', name: '全部' },
  { id: 'frontend', name: '前端' },
  { id: 'agent', name: 'Agent' },
  { id: 'backend', name: '后端' },
]

const difficulties = [
  { id: 'easy', name: '简单' },
  { id: 'medium', name: '中等' },
  { id: 'hard', name: '困难' },
]

const filtered = computed(() => {
  const needle = keyword.value.trim().toLowerCase()
  return questions.value.filter((item) => {
    if (category.value !== 'all' && item.category !== category.value) return false
    if (difficulty.value && item.difficulty !== difficulty.value) return false
    if (activeTag.value && !item.tags.includes(activeTag.value)) return false
    if (!needle) return true
    const haystack = [item.question, item.topic, item.id, item.tags.join(' ')].join(' ').toLowerCase()
    return haystack.includes(needle)
  })
})

const counts = computed(() => {
  const result: Record<string, number> = {}
  for (const item of questions.value) {
    result[item.category] = (result[item.category] || 0) + 1
  }
  return result
})

async function load() {
  loading.value = true
  errorText.value = ''
  try {
    const response = await fetch('/api/kb/questions')
    if (!response.ok) {
      const body = await response.json().catch(() => null)
      throw new Error(body?.detail || `请求失败（${response.status}）`)
    }
    const payload = (await response.json()) as { questions: KbQuestion[] }
    questions.value = payload.questions
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function toggle(id: string) {
  openId.value = openId.value === id ? '' : id
}

function selectTag(name: string) {
  activeTag.value = activeTag.value === name ? '' : name
}

function selectDifficulty(id: string) {
  difficulty.value = difficulty.value === id ? '' : id
}

onMounted(load)
</script>

<template>
  <section class="page" :data-embedded="embedded || undefined">
    <header v-if="!embedded">
      <p class="eyebrow">Knowledge</p>
      <h1>知识库</h1>
      <p v-if="!loading && !errorText">
        共 {{ questions.length }} 道：前端 {{ counts.frontend || 0 }}，Agent
        {{ counts.agent || 0 }}，后端 {{ counts.backend || 0 }}
      </p>
    </header>
    <p v-else-if="!loading && !errorText" class="embedded-lead">
      共 {{ questions.length }} 道：前端 {{ counts.frontend || 0 }}，Agent
      {{ counts.agent || 0 }}，后端 {{ counts.backend || 0 }}
    </p>

    <div class="toolbar">
      <div class="filters">
        <button
          v-for="item in categories"
          :key="item.id"
          type="button"
          :data-on="category === item.id"
          @click="category = item.id"
        >
          {{ item.name }}
        </button>
      </div>
      <div class="filters">
        <button
          v-for="item in difficulties"
          :key="item.id"
          type="button"
          :data-on="difficulty === item.id"
          @click="selectDifficulty(item.id)"
        >
          {{ item.name }}
        </button>
      </div>
      <input v-model="keyword" type="search" placeholder="搜题目、主题或标签" />
      <div v-if="activeTag" class="active-tag">
        <button type="button" @click="activeTag = ''">{{ activeTag }} ×</button>
      </div>
    </div>

    <p v-if="loading">正在读取题目…</p>
    <p v-else-if="errorText" class="error">{{ errorText }}</p>
    <p v-else-if="!filtered.length">没有匹配的题目。</p>
    <ul v-else>
      <li v-for="item in filtered" :key="item.id">
        <button type="button" class="row" @click="toggle(item.id)">
          <span class="meta"
            >{{ label(item.category) }} / {{ item.topic }} / {{ label(item.difficulty) }}</span
          >
          <span class="title">{{ item.question }}</span>
        </button>
        <div v-if="item.tags.length" class="tag-row">
          <button
            v-for="name in item.tags"
            :key="name"
            type="button"
            class="tag"
            :data-on="activeTag === name"
            @click="selectTag(name)"
          >
            {{ name }}
          </button>
        </div>
        <div v-if="openId === item.id" class="detail">
          <p><em>参考答案</em>{{ item.answer_outline }}</p>
          <p class="qid">{{ item.id }}</p>
        </div>
      </li>
    </ul>
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
  margin: 0 0 12px;
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

header p {
  margin: 8px 0 0;
  color: var(--muted);
}

.toolbar {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 10px;
  margin: 20px 0;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.filters button,
input {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--panel-strong);
  padding: 8px 12px;
}

.filters button {
  flex: none;
  white-space: nowrap;
}

.filters button[data-on='true'] {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

input {
  width: 100%;
}

.error {
  color: var(--warn);
}

ul {
  margin: 0;
  padding: 0;
  list-style: none;
}

li {
  margin-bottom: 10px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--panel);
  backdrop-filter: blur(8px);
  box-shadow: var(--shadow);
}

.row {
  display: grid;
  gap: 4px;
  width: 100%;
  padding: 14px 16px 8px;
  border: 0;
  background: transparent;
  text-align: left;
}

.meta {
  color: var(--muted);
  font-size: 13px;
}

.title {
  font-weight: 650;
}

.detail {
  padding: 0 16px 14px;
}

.detail p {
  margin: 0;
  line-height: 1.65;
}

.detail em {
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

.tag-row,
.active-tag {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-row {
  padding: 0 16px 12px;
}

.tag,
.active-tag button {
  flex: none;
  white-space: nowrap;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--panel-strong);
  padding: 2px 8px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.4;
}

.tag[data-on='true'],
.active-tag button {
  background: var(--accent-soft);
  border-color: transparent;
  color: var(--accent);
  font-weight: 700;
}

.qid {
  margin-top: 8px !important;
  color: var(--muted);
  font-size: 13px;
}

@media (max-width: 860px) {
  .page {
    height: auto;
    padding: 16px;
  }
}
</style>
