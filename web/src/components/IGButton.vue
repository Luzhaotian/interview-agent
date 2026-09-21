<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    variant?: 'ghost' | 'accent' | 'tool' | 'danger'
    size?: 'md' | 'sm'
    active?: boolean
    disabled?: boolean
    type?: 'button' | 'submit' | 'reset'
  }>(),
  {
    variant: 'ghost',
    size: 'md',
    active: false,
    disabled: false,
    type: 'button',
  },
)

const rootClass = computed(() => {
  const classes: string[] = []
  if (props.variant === 'accent') classes.push('btn-accent')
  else if (props.variant === 'tool') {
    classes.push(
      'btn-tool',
      'data-[on=true]:border-accent data-[on=true]:bg-accent data-[on=true]:text-white',
    )
  } else if (props.variant === 'danger') {
    classes.push('rounded-xl border border-warn bg-warn px-3 py-2 text-white')
  } else {
    classes.push('btn-ghost')
  }
  if (props.size === 'sm' && props.variant !== 'tool' && props.variant !== 'danger') {
    classes.push('rounded-lg px-3 py-1.5 text-[13px]')
  }
  return classes
})
</script>

<template>
  <button
    :type="type"
    :disabled="disabled"
    :data-on="active || undefined"
    :class="rootClass"
  >
    <slot />
  </button>
</template>
