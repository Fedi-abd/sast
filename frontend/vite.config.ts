import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

/**
 * Vite configuration for the SAST platform's Vue 3 SPA.
 *
 * `base: '/app/'` aligns the SPA's URL prefix between dev and prod.
 * In dev the Vite dev server still listens on http://localhost:5173,
 * but the app lives at http://localhost:5173/app/ — matching the
 * Django route Django serves the built bundle from in production.
 *
 * `server.proxy` forwards Django-owned paths to runserver on :8000
 * so the browser sees `/api/...` and `/accounts/...` as same-origin.
 * That's what makes the session cookie (set by Django's login view)
 * reach the API without any CORS dance.
 */
export default defineConfig({
  base: '/app/',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: false,
      },
      '/accounts': {
        target: 'http://localhost:8000',
        changeOrigin: false,
      },
      '/admin': {
        target: 'http://localhost:8000',
        changeOrigin: false,
      },
    },
  },
})
