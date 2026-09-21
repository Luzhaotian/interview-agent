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
    class="filter-chip text-[13px] disabled:cursor-not-allowed disabled:opacity-35"
    :data-on="active"
    :disabled="disabled"
  >
    <slot />
    <span v-if="count !== null" class="ml-1 opacity-70">{{ count }}</span>
  </button>
</template>
