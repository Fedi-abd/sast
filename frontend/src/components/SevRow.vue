<script setup>
import { computed } from 'vue';
import Bar from './Bar.vue';

const props = defineProps({
  label: { type: String, required: true },
  value: { type: Number, required: true },
  total: { type: Number, required: true },
  kind: { type: String, required: true },
});

const pct = computed(() => (props.value / Math.max(1, props.total)) * 100);
</script>

<template>
  <div class="col-stack" style="gap: 6px">
    <div class="row-between">
      <span class="mono" :style="{ fontSize: 'var(--fs-sm)', color: `var(--sev-${kind})`, letterSpacing: '0.06em' }">
        {{ label }}
      </span>
      <span class="mono" style="font-size: var(--fs-sm); color: var(--fg)">
        {{ value }} <span style="color: var(--fg-3)">/ {{ total }}</span>
      </span>
    </div>
    <Bar :pct="pct" :kind="kind" />
  </div>
</template>
