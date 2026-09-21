<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch } from 'vue'

import IGButton from '@/components/IGButton.vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    /** sm: 480px；lg: 加宽分栏（知识库） */
    size?: 'sm' | 'lg'
    /** false 时内容区不滚动，由子组件自行滚动 */
    bodyScroll?: boolean
  }>(),
  {
    size: 'sm',
    bodyScroll: true,
  },
)

const emit = defineEmits<{ close: [] }>()

const widthClass = computed(() =>
  props.size === 'lg' ? 'w-[min(1500px,96vw)]' : 'w-[min(480px,100vw)]',
)

function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.open) emit('close')
}

watch(
  () => props.open,
  (open) => {
    document.body.style.overflow = open ? 'hidden' : ''
  },
)

onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  document.body.style.overflow = ''
})
</script>

<template>
  <Transition name="drawer-fade">
    <div
      v-if="open"
      class="drawer-backdrop fixed inset-0 z-20 bg-[rgba(18,32,46,0.28)] backdrop-blur-[2px]"
      @click="emit('close')"
    />
  </Transition>
  <Transition name="drawer-slide">
    <aside
      v-if="open"
      class="drawer fixed top-0 right-0 z-30 flex h-screen flex-col bg-soft shadow-drawer will-change-transform"
      :class="widthClass"
      :aria-label="title"
    >
      <div class="flex items-center justify-between border-b border-line/10 bg-white/90 px-4 py-3.5">
        <strong>{{ title }}</strong>
        <IGButton size="sm" @click="emit('close')">关闭</IGButton>
      </div>
      <div
        class="min-h-0 flex-1"
        :class="bodyScroll ? 'scroll-thin overflow-auto' : 'flex flex-col overflow-hidden'"
      >
        <slot />
      </div>
    </aside>
  </Transition>
</template>
