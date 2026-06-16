<script setup>
import { computed } from 'vue';

const props = defineProps({
  high: { type: Number, default: 0 },
  med:  { type: Number, default: 0 },
  low:  { type: Number, default: 0 },
});

const total = computed(() => Math.max(1, props.high + props.med + props.low));
</script>

<template>
  <div class="sev-bar" aria-hidden="true">
    <span class="h" :style="{ width: (high / total * 100) + '%' }" />
    <span class="m" :style="{ width: (med  / total * 100) + '%' }" />
    <span class="l" :style="{ width: (low  / total * 100) + '%' }" />
  </div>
</template>
