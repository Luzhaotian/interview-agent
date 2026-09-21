<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import IGFilterChip from '@/components/IGFilterChip.vue'
import IGTagChip from '@/components/IGTagChip.vue'
import { label } from '@/lib/labels'
import {
  emptyKbFilters,
  facetCounts,
  filterQuestions,
  hasActiveKbFilters,
  KB_CATEGORIES,
  KB_DIFFICULTIES,
  tagFrequency,
  toggleInList,
  type KbQuestion,
} from '@/lib/kbFilter'

defineProps<{ embedded?: boolean }>()

const TAG_PREVIEW = 24

const questions = ref<KbQuestion[]>([])
const loading = ref(true)
const errorText = ref('')
const category = ref('all')
const difficulties = ref<string[]>([])
const tags = ref<string[]>([])
const keyword = ref('')
const selectedId = ref('')
const tagsExpanded = ref(false)
const mobileShowDetail = ref(false)

const filters = computed(() => ({
  category: category.value,
  difficulties: difficulties.value,
  tags: tags.value,
  keyword: keyword.value,
}))

const filtered = computed(() => filterQuestions(questions.value, filters.value))
const facets = computed(() => facetCounts(questions.value, filters.value))
const filtersActive = computed(() => hasActiveKbFilters(filters.value))

const allTagsRanked = computed(() => tagFrequency(questions.value))
const visibleTags = computed(() =>
  tagsExpanded.value ? allTagsRanked.value : allTagsRanked.value.slice(0, TAG_PREVIEW),
)
const hiddenTagCount = computed(() => Math.max(0, allTagsRanked.value.length - TAG_PREVIEW))

const selected = computed(
  () => filtered.value.find((item) => item.id === selectedId.value) || null,
)

watch(
  filtered,
  (list) => {
    if (!list.length) {
      selectedId.value = ''
      return
    }
    if (!list.some((item) => item.id === selectedId.value)) {
      selectedId.value = list[0]?.id ?? ''
    }
  },
  { immediate: true },
)

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

function clearFilters() {
  const empty = emptyKbFilters()
  category.value = empty.category
  difficulties.value = empty.difficulties
  tags.value = empty.tags
  keyword.value = empty.keyword
}

function selectDifficulty(id: string) {
  difficulties.value = toggleInList(difficulties.value, id)
}

function selectTag(name: string) {
  tags.value = toggleInList(tags.value, name)
}

function openQuestion(id: string) {
  selectedId.value = id
  mobileShowDetail.value = true
}

function backToList() {
  mobileShowDetail.value = false
}

function difficultyTone(level: string) {
  if (level === 'easy') return 'bg-[rgba(11,122,106,0.12)] text-accent'
  if (level === 'hard') return 'bg-[rgba(180,35,24,0.1)] text-warn'
  return 'bg-[rgba(18,32,46,0.08)] text-muted'
}

onMounted(load)
</script>

<template>
  <section :class="embedded ? 'page-embedded scroll-thin' : 'page-shell scroll-thin'">
    <header v-if="!embedded" class="mb-4 flex-none">
      <p class="eyebrow">Knowledge</p>
      <h1 class="mt-1.5 mb-0 font-display text-[clamp(32px,4vw,44px)] tracking-[-0.03em]">知识库</h1>
    </header>

    <div
      v-if="!loading && !errorText"
      class="mb-3 flex flex-none flex-wrap items-center justify-between gap-2"
    >
      <p class="m-0 text-[13px] text-muted">
        匹配 {{ filtered.length }} / 共 {{ questions.length }}
      </p>
      <button
        v-if="filtersActive"
        type="button"
        class="border-0 bg-transparent p-0 text-[13px] text-accent underline-offset-2 hover:underline"
        @click="clearFilters"
      >
        清空筛选
      </button>
    </div>

    <div v-if="!loading && !errorText" class="mb-3 flex flex-none flex-col gap-2.5">
      <input
        v-model="keyword"
        class="w-full rounded-xl border border-line/10 bg-panel-strong px-3 py-2 text-sm"
        type="search"
        placeholder="搜题目、主题、标签或编号"
      />

      <div class="flex flex-wrap gap-1.5">
        <IGFilterChip
          v-for="item in KB_CATEGORIES"
          :key="item.id"
          :active="category === item.id"
          :disabled="(facets.categories[item.id] || 0) === 0 && item.id !== 'all'"
          :count="facets.categories[item.id] || 0"
          @click="category = item.id"
        >
          {{ item.name }}
        </IGFilterChip>
      </div>

      <div class="flex flex-wrap gap-1.5">
        <IGFilterChip
          v-for="item in KB_DIFFICULTIES"
          :key="item.id"
          :active="difficulties.includes(item.id)"
          :disabled="(facets.difficulties[item.id] || 0) === 0 && !difficulties.includes(item.id)"
          :count="facets.difficulties[item.id] || 0"
          @click="selectDifficulty(item.id)"
        >
          {{ item.name }}
        </IGFilterChip>
      </div>

      <div v-if="allTagsRanked.length" class="flex flex-wrap gap-1.5">
        <IGTagChip
          v-for="item in visibleTags"
          :key="item.name"
          :active="tags.includes(item.name)"
          :disabled="(facets.tags[item.name] || 0) === 0 && !tags.includes(item.name)"
          :count="facets.tags[item.name] || 0"
          @click="selectTag(item.name)"
        >
          {{ item.name }}
        </IGTagChip>
        <IGTagChip v-if="!tagsExpanded && hiddenTagCount > 0" @click="tagsExpanded = true">
          +{{ hiddenTagCount }} 更多
        </IGTagChip>
        <IGTagChip v-else-if="tagsExpanded && hiddenTagCount > 0" @click="tagsExpanded = false">
          收起
        </IGTagChip>
      </div>
    </div>

    <p v-if="loading" class="text-muted">正在读取题目…</p>
    <p v-else-if="errorText" class="text-warn">{{ errorText }}</p>
    <p v-else-if="!filtered.length" class="text-muted">没有匹配的题目。</p>

    <div
      v-else
      class="grid min-h-0 flex-1 grid-cols-1 gap-0 overflow-hidden rounded-panel border border-line/10 bg-white/70 max-md:min-h-[420px] md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.2fr)]"
      :class="embedded ? 'min-h-0' : 'min-h-[560px]'"
    >
      <!-- 左列表：窄屏有选中详情时隐藏 -->
      <div
        class="scroll-thin flex min-h-0 flex-col overflow-auto border-line/10 md:border-r"
        :class="mobileShowDetail ? 'max-md:hidden' : ''"
      >
        <button
          v-for="item in filtered"
          :key="item.id"
          type="button"
          class="kb-row"
          :data-active="selectedId === item.id"
          @click="openQuestion(item.id)"
        >
          <span class="flex items-center gap-2">
            <span class="diff-pill" :class="difficultyTone(item.difficulty)">{{
              label(item.difficulty)
            }}</span>
            <span class="min-w-0 flex-1 overflow-hidden text-ellipsis whitespace-nowrap text-[13px] text-muted">{{
              item.topic
            }}</span>
          </span>
          <span class="line-clamp-2 text-[14px] font-semibold leading-snug">{{ item.question }}</span>
        </button>
      </div>

      <!-- 右详情 -->
      <div
        class="scroll-thin min-h-0 overflow-auto px-4 py-4 max-md:px-3.5"
        :class="mobileShowDetail ? '' : 'max-md:hidden'"
      >
        <button
          type="button"
          class="mb-3 border-0 bg-transparent p-0 text-[13px] text-accent md:hidden"
          @click="backToList"
        >
          ← 返回列表
        </button>

        <template v-if="selected">
          <p class="m-0 text-[13px] text-muted">
            {{ label(selected.category) }} · {{ selected.topic }} ·
            {{ label(selected.difficulty) }}
          </p>
          <h2 class="mt-2 mb-0 font-display text-[clamp(20px,2.4vw,26px)] leading-snug tracking-tight">
            {{ selected.question }}
          </h2>

          <div v-if="selected.tags.length" class="mt-3 flex flex-wrap gap-1.5">
            <IGTagChip
              v-for="name in selected.tags"
              :key="name"
              :active="tags.includes(name)"
              @click="selectTag(name)"
            >
              {{ name }}
            </IGTagChip>
          </div>

          <div class="mt-5 border-t border-line/8 pt-4">
            <p class="m-0 mb-2 text-xs font-bold uppercase tracking-[0.12em] text-accent">参考答案</p>
            <p class="m-0 whitespace-pre-wrap text-[15px] leading-[1.7]">{{ selected.answer_outline }}</p>
          </div>
          <p class="mt-4 mb-0 font-mono text-[12px] text-muted">{{ selected.id }}</p>
        </template>
        <p v-else class="m-0 text-sm text-muted">从左侧选择一道题查看参考答案。</p>
      </div>
    </div>
  </section>
</template>
