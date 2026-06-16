<script setup>
defineProps({
  kind: { type: String, default: '' },
  dot: { type: Boolean, default: false },
});
</script>

<template>
  <span :class="['pill', kind ? `pill-${kind}` : '']">
    <span v-if="dot" class="dot" />
    <slot />
  </span>
</template>
