<script setup>
defineProps({
  label: { type: String, required: true },
  error: { type: String, default: '' },
  hint:  { type: String, default: '' },
});
</script>

<template>
  <div class="form-control">
    <div class="form-label" style="padding-top: 0">{{ label }}</div>
    <div :class="['input', error ? 'error' : '']">
      <slot />
    </div>
    <div v-if="hint" class="form-hint">{{ hint }}</div>
    <div v-if="error" class="form-error">{{ error }}</div>
  </div>
</template>
