<script setup>
import { computed } from 'vue';
import Icon from './Icon.vue';

const props = defineProps({
  tool: { type: String, required: true },
  desc: { type: String, required: true },
  cost: { type: Number, required: true },
  credits: { type: Number, required: true },
  running: { type: Boolean, default: false },
  primary: { type: Boolean, default: false },
});
defineEmits(['run']);

const affordable = computed(() => props.credits >= props.cost);
const disabled = computed(() => !affordable.value || props.running);
</script>

<template>
  <div
    :class="['scan-action', primary && affordable ? 'primary' : '', disabled ? 'disabled' : '']"
    @click="!disabled && $emit('run')"
  >
    <div class="row-between">
      <span class="tool-name">{{ tool }}</span>
      <span v-if="running" class="spinner" />
      <Icon v-else :name="primary ? 'fastForward' : 'play'" :size="14" />
    </div>
    <div class="tool-desc">{{ desc }}</div>
    <div class="mono" style="font-size: var(--fs-xs); color: var(--fg-2); display: flex; justify-content: space-between">
      <span>cost: {{ cost }} credit{{ cost > 1 ? 's' : '' }}</span>
      <span v-if="running">RUNNING…</span>
      <span v-else-if="!affordable" style="color: var(--sev-high)">NO CREDITS</span>
      <span v-else>{{ primary ? 'RUN_BOTH →' : 'RUN →' }}</span>
    </div>
  </div>
</template>
