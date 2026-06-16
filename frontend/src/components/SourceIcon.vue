<script setup>
import Icon from './Icon.vue';
defineProps({ type: { type: String, required: true } });
</script>

<template>
  <Icon v-if="type === 'git'"     name="git"     :size="14" />
  <Icon v-else-if="type === 'upload'" name="archive" :size="14" />
  <Icon v-else                    name="folder"  :size="14" />
</template>
