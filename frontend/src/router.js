import { createRouter, createWebHashHistory } from 'vue-router';

import { ensureAuth, auth } from './auth.js';
import { redirectToLogin } from './api.js';

const routes = [
  { path: '/',                redirect: '/dashboard' },
  { path: '/dashboard',       name: 'dashboard',    component: () => import('./views/Dashboard.vue') },
  { path: '/projects',        name: 'projects',     component: () => import('./views/Projects.vue') },
  { path: '/projects/new',    name: 'new-project',  component: () => import('./views/NewProject.vue'), meta: { sidebarKey: 'projects' } },
  { path: '/project/:id',     name: 'project',      component: () => import('./views/ProjectDetail.vue'), props: true, meta: { sidebarKey: 'projects' } },
  { path: '/project/:id/edit', name: 'edit-project', component: () => import('./views/EditProject.vue'), props: true, meta: { sidebarKey: 'projects' } },
  { path: '/scan/:id',        name: 'scan',         component: () => import('./views/ScanResults.vue'), props: true, meta: { sidebarKey: 'projects' } },
  { path: '/vulns',           name: 'vulns',        component: () => import('./views/Vulnerabilities.vue') },
  { path: '/scans',           name: 'scans',        component: () => import('./views/Scans.vue') },
  { path: '/settings',        name: 'settings',     component: () => import('./views/Settings.vue') },
  { path: '/admin',           name: 'admin',        component: () => import('./views/AdminDashboard.vue'), meta: { requiresStaff: true } },
  { path: '/docs',            name: 'docs',         component: () => import('./views/Documentation.vue') },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
});

/**
 * Auth gate. Every route requires a valid Django session; auth lives
 * in the templated /accounts/ pages, not the SPA, so unauthenticated
 * users bounce to the templated login with `?next=` pointing back to
 * the route they wanted. A network error falls through so the target
 * view can render its own error state rather than trapping the user.
 *
 * `requiresStaff` routes (the admin console) additionally check
 * `auth.me.is_staff`; the backend enforces this too, this just avoids
 * rendering a console a non-staff user can't use.
 */
router.beforeEach(async (to) => {
  let ok;
  try {
    ok = await ensureAuth();
  } catch {
    return true;
  }
  if (!ok) {
    // Hash routing: the address for a route is /app/#/<path>, so the
    // post-login ?next= must carry the hash; '/app/' + fullPath would
    // produce /app//dashboard and drop the user on the default route.
    // reason=null: a guard bounce is usually a fresh visit, not a
    // mid-session sign-out, so no "you were signed out" notice.
    redirectToLogin('/app/#' + to.fullPath, null);
    return false;
  }
  if (to.meta.requiresStaff && !auth.me?.is_staff) {
    return { name: 'dashboard' };
  }
  return true;
});

export default router;
