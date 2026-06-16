<script setup>
defineProps({
  pct: { type: Number, default: 0 },
  kind: { type: String, default: 'accent' },  // 'accent' | 'high' | 'med' | 'low'
});
</script>

<template>
  <div :class="['bar', kind === 'accent' ? '' : kind]">
    <i :style="{ width: Math.min(100, pct) + '%' }" />
  </div>
</template>
