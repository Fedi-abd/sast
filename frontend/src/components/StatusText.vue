<script setup>
defineProps({
  kind: { type: String, required: true },
  label: { type: String, required: true },
});
</script>

<template>
  <span :class="['status', `status-${kind}`]">{{ label }}</span>
</template>
