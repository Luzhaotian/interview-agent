<script setup lang="ts">
import { computed } from 'vue'

import { label } from '@/lib/labels'
import type { Question } from '@/lib/transcript'

const props = withDefaults(
  defineProps<{
    question: Question
    /** 组内序号，从 0 开始 */
    index: number
    /** 全局错峰序号：后端一次性 emit 所有题卡时，用它让卡片逐张浮现而非同帧弹出 */
    stagger?: number
  }>(),
  { stagger: 0 },
)

// 每张卡间隔 70ms 出现；封顶避免题多时最后一张等太久
const riseStyle = computed(() => ({
  animationDelay: `${Math.min(props.stagger, 12) * 70}ms`,
}))
</script>

<template>
  <article
    class="animate-rise mt-0 rounded-[14px] border border-line/10 bg-panel-strong p-3.5 [&+&]:mt-2.5"
    :style="riseStyle"
  >
    <p class="m-0 flex gap-2.5 font-bold leading-[1.45]">
      <span
        class="inline-grid size-6 flex-none place-items-center rounded-full bg-accent-soft text-xs text-accent"
        >{{ index + 1 }}</span
      >
      {{ question.question }}
    </p>
    <p class="mb-2.5 mt-1.5 text-[13px] text-muted">
      {{ label(question.category) }} · {{ question.topic }} · {{ label(question.difficulty) }}
      <span
        v-if="question.source === 'web'"
        class="ml-2 inline-block rounded-full bg-[#e8eef8] px-2 py-px text-xs font-bold text-[#2f5f9e]"
        >联网</span
      >
      <span
        v-else-if="question.source === 'probe'"
        class="ml-2 inline-block rounded-full bg-[#f3e8f8] px-2 py-px text-xs font-bold text-[#6b3d8f]"
        >追问</span
      >
      <span
        v-else-if="question.source === 'resume'"
        class="ml-2 inline-block rounded-full bg-accent-soft px-2 py-px text-xs font-bold text-accent"
        >简历</span
      >
    </p>
    <p
      v-if="question.source === 'web' && question.source_url"
      class="-mt-1 mb-2.5 text-[13px] text-muted"
    >
      来源
      <a
        class="text-accent no-underline hover:underline"
        :href="question.source_url"
        target="_blank"
        rel="noreferrer"
        >{{ question.source_title || question.source_url }}</a
      >
    </p>
    <p v-if="question.reason" class="m-0 leading-[1.65] [&+p]:mt-2">
      <em class="pill-em">为什么问</em>{{ question.reason }}
    </p>
    <p class="m-0 leading-[1.65] [&+p]:mt-2">
      <em class="pill-em">回答方向</em>{{ question.answer_direction }}
    </p>
    <p class="m-0 leading-[1.65] [&+p]:mt-2">
      <em class="pill-em">参考答案</em>{{ question.reference_answer }}
    </p>
  </article>
</template>
