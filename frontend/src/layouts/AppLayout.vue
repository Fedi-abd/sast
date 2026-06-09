<script setup lang="ts">
/**
 * App shell — sidebar + content layout used by every authenticated
 * route.
 *
 * Surface hierarchy:
 *   - body          → surface.base (lighter / darker)
 *   - sidebar       → surface.sunken (one step below body in light,
 *                     one step deeper in dark — both register as
 *                     "this is a different zone than content")
 *   - main content  → inherits body; cards (`.card`) layer on top
 *
 * The theme toggle and log-out live in a pinned footer at the
 * bottom of the sidebar so they're reachable without scrolling on
 * any page. Log-out is a real form POST to Django's LogoutView —
 * the session cookie lives outside the SPA so clearing it requires
 * a server round-trip.
 */
import { RouterLink, RouterView } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import { storeToRefs } from 'pinia'

const themeStore = useThemeStore()
const { theme } = storeToRefs(themeStore)

function readCsrf(): string {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}
</script>

<template>
  <div class="flex min-h-full">
    <aside
      class="hidden md:flex w-64 flex-col
             border-r border-line dark:border-line-dark
             bg-surface-sunken dark:bg-surface-dark-sunken
             px-3 py-5"
    >
      <div class="px-3 mb-8">
        <h1 class="font-display font-semibold text-base tracking-tight">
          SAST
          <span class="text-slate-400 dark:text-slate-500 font-normal">platform</span>
        </h1>
        <p class="text-[0.6875rem] uppercase tracking-wider text-slate-500 dark:text-slate-500 mt-1.5 font-mono">
          Semgrep · SonarQube
        </p>
      </div>

      <nav class="flex-1 flex flex-col gap-1">
        <RouterLink to="/projects" class="nav-link">Projects</RouterLink>
      </nav>

      <div class="flex flex-col gap-1 pt-4 mt-4 border-t border-line dark:border-line-dark">
        <button
          type="button"
          class="nav-link text-left"
          @click="themeStore.toggle"
        >
          <span class="inline-flex items-center gap-2">
            <span class="text-base leading-none">
              {{ theme === 'dark' ? '☀' : '☾' }}
            </span>
            <span>{{ theme === 'dark' ? 'Light mode' : 'Dark mode' }}</span>
          </span>
        </button>

        <form action="/accounts/logout/" method="post">
          <input type="hidden" name="csrfmiddlewaretoken" :value="readCsrf()" />
          <button type="submit" class="nav-link w-full text-left">
            <span class="inline-flex items-center gap-2">
              <span class="text-base leading-none">⏻</span>
              <span>Log out</span>
            </span>
          </button>
        </form>
      </div>
    </aside>

    <main class="flex-1 overflow-x-auto">
      <div class="max-w-6xl mx-auto px-6 py-10">
        <RouterView />
      </div>
    </main>
  </div>
</template>
