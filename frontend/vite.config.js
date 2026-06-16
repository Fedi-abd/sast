import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

/**
 * Vite config for the SAST Platform SPA.
 *
 * base '/app/' — the SPA is served from /app/ in both dev and prod, so
 * Django only owns one catch-all route there. Hash routing
 * (createWebHashHistory) means everything after /app/#/... is
 * client-side; Django never sees it.
 *
 * server.proxy — forwards Django-owned paths to runserver on :8000 so
 * the browser treats /api, /accounts, /admin, /static, /media as
 * same-origin, so the session cookie + CSRF token flow without CORS and
 * Django-rendered pages (the styled auth screens, the templated UI) get
 * their CSS.
 */
export default defineConfig({
  base: '/app/',
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: false },
      '/accounts': { target: 'http://localhost:8000', changeOrigin: false },
      '/admin': { target: 'http://localhost:8000', changeOrigin: false },
      '/static': { target: 'http://localhost:8000', changeOrigin: false },
      '/media': { target: 'http://localhost:8000', changeOrigin: false },
    },
  },
});
