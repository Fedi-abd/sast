<script setup lang="ts">
/**
 * SPA-side 404. Triggered by the catch-all route in `router/index.ts`,
 * which means the URL exists on the Django side (the server already
 * routed /app/<anything> to the SPA) but matches no Vue route.
 * Distinct from Django's templated 404 in Track 9.
 */
import { RouterLink } from 'vue-router'
</script>

<template>
  <div class="max-w-md mx-auto text-center mt-24 animate-rise-in">
    <p class="font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">
      404 — route not found
    </p>
    <h1 class="mt-4 text-3xl font-display font-semibold text-slate-900 dark:text-slate-50">
      Off the map
    </h1>
    <p class="mt-3 text-slate-500 dark:text-slate-400 text-sm">
      That URL doesn't match any route in the app.
    </p>
    <RouterLink to="/projects" class="btn-primary mt-8">
      Back to projects
    </RouterLink>
  </div>
</template>
