<script setup>
import { ref, watch, onMounted } from 'vue';
import Icon from '../components/Icon.vue';

const theme = ref(localStorage.getItem('sast_theme') || 'dark');

watch(theme, (v) => {
  document.documentElement.setAttribute('data-theme', v);
  localStorage.setItem('sast_theme', v);
});

onMounted(() => {
  document.documentElement.setAttribute('data-theme', theme.value);
});
</script>

<template>
  <div class="theme-toggle" role="group" aria-label="Theme">
    <span
      :class="['seg', theme === 'dark' ? 'on' : '']"
      style="display: flex; align-items: center; gap: 6px; justify-content: center"
      @click="theme = 'dark'"
    >
      <Icon name="moon" :size="12" /> Dark
    </span>
    <span
      :class="['seg', theme === 'light' ? 'on' : '']"
      style="display: flex; align-items: center; gap: 6px; justify-content: center"
      @click="theme = 'light'"
    >
      <Icon name="sun" :size="12" /> Light
    </span>
  </div>
</template>
