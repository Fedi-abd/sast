<script setup lang="ts">
/**
 * Project list — the SPA's landing page after login.
 *
 * Card grid layout with the analyst-console treatment: subtle inset
 * highlight on dark mode cards, hover lift, mono-styled metadata
 * footer to ground the visual weight at the bottom of each card.
 *
 * Each card is wrapped in `.card-interactive` (the lift-on-hover
 * variant) so the user gets feedback that the card is clickable.
 * Click target is the whole card via `<RouterLink>` once the detail
 * route lands — today the cards are read-only.
 */
import { computed, onMounted, ref } from 'vue'
import { api, ApiError, UnauthorizedError } from '@/api/client'
import type { Project } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import Badge from '@/components/Badge.vue'

const projects = ref<Project[]>([])
const loading = ref(true)
const errorMessage = ref<string | null>(null)

async function load() {
  loading.value = true
  errorMessage.value = null
  try {
    projects.value = await api.get<Project[]>('/api/projects/')
  } catch (err) {
    if (err instanceof UnauthorizedError) {
      useAuthStore().redirectToLogin()
      return
    }
    if (err instanceof ApiError) {
      errorMessage.value = `API error ${err.status}`
    } else {
      errorMessage.value = 'Network error — is Django running?'
    }
  } finally {
    loading.value = false
  }
}

// Source-type → Badge variant. Keep this mapping centralized; if we
// change "git = purple" later, only edit here.
function sourceVariant(source: Project['source_type']) {
  switch (source) {
    case 'local':
      return 'neutral' as const
    case 'upload':
      return 'info' as const
    case 'git':
      return 'accent' as const
  }
}

const subtitle = computed(() => {
  if (loading.value) return 'Loading…'
  const n = projects.value.length
  return `${n} ${n === 1 ? 'project' : 'projects'} registered`
})

onMounted(load)
</script>

<template>
  <header class="flex items-end justify-between mb-10 animate-rise-in">
    <div>
      <h1 class="text-3xl font-display font-semibold tracking-tight">
        Projects
      </h1>
      <p class="text-sm text-slate-500 dark:text-slate-400 mt-2 font-mono">
        {{ subtitle }}
      </p>
    </div>
    <a href="/debug/projects/create/" class="btn-primary">
      <span class="text-base leading-none">+</span>
      <span>New project</span>
    </a>
  </header>

  <div v-if="loading" class="text-sm text-slate-500 dark:text-slate-400 font-mono">
    Loading projects…
  </div>

  <div
    v-else-if="errorMessage"
    class="card p-4 text-sm text-red-700 dark:text-red-300"
  >
    {{ errorMessage }}
  </div>

  <div v-else-if="projects.length === 0" class="card p-12 text-center">
    <p class="text-slate-700 dark:text-slate-100 font-medium">No projects yet</p>
    <p class="text-slate-500 dark:text-slate-400 text-sm mt-2">
      Register one from
      <a
        href="/debug/projects/create/"
        class="text-brand-700 dark:text-brand-300 underline underline-offset-4"
      >
        the create form
      </a>
      to start scanning.
    </p>
  </div>

  <ul v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
    <li
      v-for="(project, idx) in projects"
      :key="project.id"
      class="card-interactive p-5 cursor-pointer animate-rise-in"
      :style="{ animationDelay: `${idx * 40}ms` }"
    >
      <h2 class="font-display font-semibold text-base text-slate-900 dark:text-slate-50 leading-snug">
        {{ project.name }}
      </h2>

      <div class="flex flex-wrap gap-1.5 mt-3">
        <Badge :variant="sourceVariant(project.source_type)" uppercase>
          {{ project.source_type_display }}
        </Badge>
        <Badge v-if="project.language" variant="neutral">
          {{ project.language }}
        </Badge>
      </div>

      <p class="text-[0.6875rem] uppercase tracking-wider text-slate-400 dark:text-slate-500 mt-5 font-mono">
        Created · {{ new Date(project.created_at).toLocaleDateString() }}
      </p>
    </li>
  </ul>
</template>
