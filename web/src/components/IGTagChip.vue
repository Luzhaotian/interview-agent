<script setup lang="ts">
withDefaults(
  defineProps<{
    active?: boolean
    disabled?: boolean
    count?: number | null
  }>(),
  {
    active: false,
    disabled: false,
    count: null,
  },
)
</script>

<template>
  <button
    type="button"
    class="tag-chip disabled:cursor-not-allowed disabled:opacity-35"
    :data-on="active"
    :disabled="disabled"
  >
    <slot />
    <span v-if="count !== null" class="ml-0.5 opacity-70">{{ count }}</span>
  </button>
</template>
