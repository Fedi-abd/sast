/**
 * Auth state: a reactive singleton (no Pinia, matching the rest of
 * this app's plain-Vue style).
 *
 * `auth.me` holds the current user (username, is_staff, credits) once
 * `ensureAuth()` resolves. Components read it directly; the topbar
 * shows `auth.me.credits`, the sidebar gates admin nav on
 * `auth.me.is_staff`.
 *
 * `ensureAuth()` is called by the router guard on first navigation.
 * It checks `/api/me/` once and caches the result; a 401 means
 * "bounce to Django login." Session expiry mid-session is caught by
 * individual view fetches throwing UnauthorizedError, not re-polled
 * here.
 */
import { reactive } from 'vue';

import { fetchMe, UnauthorizedError } from './api.js';

export const auth = reactive({
  me: null,
  checked: false,
  authenticated: false,
});

export async function ensureAuth() {
  if (auth.checked) return auth.authenticated;
  try {
    auth.me = await fetchMe();
    auth.authenticated = true;
  } catch (err) {
    auth.authenticated = false;
    if (!(err instanceof UnauthorizedError)) throw err;
  } finally {
    auth.checked = true;
  }
  return auth.authenticated;
}

/** Refresh the cached `me` (e.g. after a scan spends credits). */
export async function refreshMe() {
  try {
    const fresh = await fetchMe();
    // Logging in as another account in a second tab swaps the shared
    // session cookie under this one; if /api/me/ now answers as a
    // different user, hard-reload so the SPA re-syncs to the real
    // session instead of silently acting as the new account.
    if (auth.me && fresh.id !== auth.me.id) {
      window.location.reload();
      return;
    }
    auth.me = fresh;
  } catch {
    // leave the stale value; a hard failure surfaces elsewhere
  }
}
