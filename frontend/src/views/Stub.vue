<script setup>
import Icon from '../components/Icon.vue';

defineProps({
  title: { type: String, required: true },
  sub: { type: String, required: true },
});
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title rise-in">{{ title }}</h1>
        <div class="page-sub"><span class="mono">{{ sub }}</span></div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-body" style="padding: 48px; text-align: center">
        <Icon name="terminal" :size="24" />
        <div class="mono" style="margin-top: 12px; color: var(--fg-1)">
          Section scaffolded — wire to backend in implementation pass.
        </div>
      </div>
    </div>
  </div>
</template>
