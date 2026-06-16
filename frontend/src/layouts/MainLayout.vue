<script setup>
import Sidebar from './Sidebar.vue';
import Topbar from './Topbar.vue';
</script>

<template>
  <div class="app">
    <Sidebar />
    <div class="main">
      <Topbar />
      <slot />
    </div>
  </div>
</template>
