/**
 * Vue Router setup.
 *
 * History mode uses `/app/` as the base — matches the URL Django
 * serves the SPA from. The catch-all 404 route renders the same
 * NotFoundView regardless of depth, so e.g. /app/projects/garbage
 * lands on the SPA's own not-found page instead of triggering
 * Django's 404 handler.
 *
 * A `beforeEach` guard verifies authentication on every navigation
 * (except routes flagged `meta.public`). Unauthenticated users are
 * bounced to Django's templated login via `authStore.redirectToLogin`.
 */
import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory('/app/'),
  routes: [
    {
      path: '/',
      name: 'home',
      redirect: '/projects',
    },
    {
      path: '/projects',
      name: 'project-list',
      component: () => import('@/views/ProjectListView.vue'),
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
      meta: { public: true },
    },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true

  const auth = useAuthStore()
  if (auth.isAuthenticated === null) {
    try {
      await auth.checkAuth()
    } catch {
      // Network error — let the view render and show its own error
      // state rather than blocking navigation.
      return true
    }
  }

  if (auth.isAuthenticated === false) {
    auth.redirectToLogin(`/app${to.fullPath}`)
    // Returning false aborts the SPA navigation; the redirectToLogin
    // call has already triggered a full-page navigation, but `false`
    // keeps Vue from rendering the protected view in the meantime.
    return false
  }

  return true
})

export default router
