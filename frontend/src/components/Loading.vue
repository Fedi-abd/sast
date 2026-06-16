<script setup>
defineProps({
  // mono, CLI-flavored: shows as "label ▍" with a blinking cursor
  label: { type: String, default: 'loading' },
});
</script>

<template>
  <div class="mono dim" style="padding: 24px; display: flex; align-items: center; gap: 10px">
    <span class="spinner" />
    <span>{{ label }}<span class="loading-cursor">▍</span></span>
  </div>
</template>

<style scoped>
.loading-cursor {
  margin-left: 2px;
  color: var(--accent);
  animation: loading-blink 1s steps(1) infinite;
}
@keyframes loading-blink {
  50% { opacity: 0; }
}
</style>
