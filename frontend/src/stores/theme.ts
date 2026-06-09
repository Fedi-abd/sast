/**
 * Theme store — light/dark toggle persisted in localStorage.
 *
 * Mirrors the existing Bootstrap theme toggle in `templates/base.html`
 * so the SPA and the templated fallback feel like one product. Light
 * is the default (projector-friendly demo).
 *
 * Tailwind's dark mode is class-based (`darkMode: 'class'` in
 * tailwind.config.js), so we toggle a `dark` class on `<html>`.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'sast-theme'
type Theme = 'light' | 'dark'

function resolveInitial(): Theme {
  const stored = window.localStorage.getItem(STORAGE_KEY)
  if (stored === 'light' || stored === 'dark') return stored
  return 'light'
}

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<Theme>(resolveInitial())

  function apply() {
    document.documentElement.classList.toggle('dark', theme.value === 'dark')
  }

  function setTheme(next: Theme) {
    theme.value = next
    window.localStorage.setItem(STORAGE_KEY, next)
    apply()
  }

  function toggle() {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  apply()

  return { theme, setTheme, toggle }
})
