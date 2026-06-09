/**
 * Auth store.
 *
 * Authentication is owned by Django — the user signs in via the
 * templated `/accounts/login/` page, Django sets a `sessionid` cookie,
 * and the cookie travels on every API call. Vue's job is just to
 * detect whether that cookie is still valid by trying to fetch a
 * known-protected endpoint, and to bounce the user back to Django's
 * login page when it isn't.
 *
 * We don't store username/password here — those never live in JS.
 * `isAuthenticated` is the only piece of state.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api, UnauthorizedError } from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const isAuthenticated = ref<boolean | null>(null)
  const checking = ref(false)

  async function checkAuth(): Promise<boolean> {
    checking.value = true
    try {
      // /api/projects/ is the cheapest authenticated endpoint we
      // have; we throw away the response and only care about the
      // 200-vs-401/403 distinction.
      await api.get('/api/projects/')
      isAuthenticated.value = true
      return true
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        isAuthenticated.value = false
        return false
      }
      // Network errors etc. — leave isAuthenticated null so callers
      // can decide whether to retry or surface a real error.
      throw err
    } finally {
      checking.value = false
    }
  }

  function redirectToLogin(next: string = window.location.pathname): void {
    // Full-page navigation to Django's templated login — the Vue
    // router does not control /accounts/* routes. `?next=` makes
    // Django's LoginView bounce back to the SPA after success.
    const url = new URL('/accounts/login/', window.location.origin)
    url.searchParams.set('next', next)
    window.location.assign(url.toString())
  }

  return { isAuthenticated, checking, checkAuth, redirectToLogin }
})
