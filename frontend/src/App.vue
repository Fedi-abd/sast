<script setup lang="ts">
/**
 * Root component — just hosts the AppLayout shell, which in turn
 * renders the active route inside its main content area.
 *
 * When we eventually need full-bleed routes (e.g. a kiosk-style
 * scan-detail mode), we'll re-introduce a `meta.bare` branch here.
 */
import AppLayout from '@/layouts/AppLayout.vue'
</script>

<template>
  <AppLayout />
</template>
