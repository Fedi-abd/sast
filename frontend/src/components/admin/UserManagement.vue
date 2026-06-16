<script setup>
import { ref, computed, onMounted } from 'vue';
import { fetchAdminUsers, setUserActive, resetUserPassword, fetchResetRequests, resolveResetRequest, redirectToLogin, UnauthorizedError } from '../../api.js';
import { relativeTime, fmtDateTime } from '../../lib/format.js';
import { auth } from '../../auth.js';
import Icon from '../Icon.vue';
import Pill from '../Pill.vue';
import Loading from '../Loading.vue';

const users = ref([]);
const loading = ref(true);
const error = ref(null);
const q = ref('');
const reset = ref({}); // id -> 'confirm'
const tempPw = ref({}); // id -> temp password, persists until dismissed
const copied = ref(null); // 'pw:'+id or 'mail:'+id of the value just copied
const busy = ref(null); // id of the row with a mutation in flight
const actionError = ref(null);

onMounted(async () => {
  try {
    users.value = await fetchAdminUsers();
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    error.value = 'Failed to load users. Is the API up?';
  } finally {
    loading.value = false;
  }
});

const toggleActive = async (u) => {
  if (u.id === auth.me?.id) return; // can't deactivate yourself
  if (busy.value !== null) return;
  busy.value = u.id;
  actionError.value = null;
  try {
    // no optimistic flip; the switch reflects the server's answer only
    const updated = await setUserActive(u.id, !u.is_active);
    const i = users.value.findIndex((x) => x.id === updated.id);
    if (i !== -1) users.value[i] = updated;
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    actionError.value = e?.body?.detail || `Could not update ${u.username}. Try again.`;
  } finally {
    busy.value = null;
  }
};

const askReset = (id) => { reset.value = { ...reset.value, [id]: 'confirm' }; };
const cancelReset = (id) => { const n = { ...reset.value }; delete n[id]; reset.value = n; };
const doReset = async (id) => {
  if (busy.value !== null) return;
  busy.value = id;
  actionError.value = null;
  try {
    const res = await resetUserPassword(id);
    tempPw.value = { ...tempPw.value, [id]: res.temp_password };
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    actionError.value = e?.body?.detail || 'Password reset failed. Try again.';
  } finally {
    cancelReset(id);
    busy.value = null;
  }
};

const copyTemp = (id) => {
  try { navigator.clipboard.writeText(tempPw.value[id]); } catch (e) {}
  copied.value = 'pw:' + id;
  setTimeout(() => { copied.value = null; }, 1200);
};

// the platform has no SMTP; hand the admin a paste-ready email
// (clipboard) or open their own mail app prefilled (mailto:)
const EMAIL_SUBJECT = 'Your SAST Platform password was reset';
const emailBody = (u) => [
  `Hi ${u.username},`,
  '',
  'An administrator reset your SAST Platform password.',
  '',
  `  Temporary password: ${tempPw.value[u.id]}`,
  '',
  `Sign in at ${window.location.origin}/accounts/login/ and change it right away:`,
  'profile menu (top right) -> Change password.',
  '',
  'SAST Platform',
].join('\n');

const copyEmail = (u) => {
  try { navigator.clipboard.writeText(`Subject: ${EMAIL_SUBJECT}\n\n${emailBody(u)}`); } catch (e) {}
  copied.value = 'mail:' + u.id;
  setTimeout(() => { copied.value = null; }, 1200);
};

const mailtoHref = (u) =>
  `mailto:${encodeURIComponent(u.email)}?subject=${encodeURIComponent(EMAIL_SUBJECT)}&body=${encodeURIComponent(emailBody(u))}`;
const dismissTemp = (id) => { const n = { ...tempPw.value }; delete n[id]; tempPw.value = n; };

const list = computed(() => {
  const s = q.value.toLowerCase();
  return users.value.filter((u) => u.username.toLowerCase().includes(s) || u.email.toLowerCase().includes(s));
});

// password reset requests
const resetRequests = ref([]);
const resetReqLoading = ref(true);
const resetReqError = ref(null);
const resolvingId = ref(null);

const loadResetRequests = async () => {
  resetReqError.value = null;
  try {
    resetRequests.value = await fetchResetRequests();
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    resetReqError.value = 'Failed to load reset requests. Is the API up?';
  } finally {
    resetReqLoading.value = false;
  }
};

onMounted(loadResetRequests);

const markHandled = async (id) => {
  if (resolvingId.value !== null) return;
  resolvingId.value = id;
  try {
    await resolveResetRequest(id);
    // remove from the list immediately; a re-fetch would also work
    resetRequests.value = resetRequests.value.filter((r) => r.id !== id);
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    resetReqError.value = 'Could not mark request handled. Try again.';
  } finally {
    resolvingId.value = null;
  }
};
</script>

<template>
  <!-- password reset requests -->
  <div class="panel rise-in" style="margin-bottom: 16px">
    <div class="panel-head">
      <span class="panel-title">// password_reset_requests</span>
    </div>
    <Loading v-if="resetReqLoading" label="loading_reset_requests" />
    <div v-else-if="resetReqError" class="panel-body" style="color: var(--sev-high)">{{ resetReqError }}</div>
    <template v-else>
      <div v-if="resetRequests.length === 0" class="mono dim" style="padding: 16px 14px; font-size: var(--fs-sm)">
        // no pending requests
      </div>
      <template v-else>
        <div class="mono dim" style="padding: 10px 14px 4px; font-size: var(--fs-xs)">
          Reset the user via the roster below, then mark handled.
        </div>
        <table class="tbl">
          <thead>
            <tr>
              <th>Identifier</th>
              <th>Requested</th>
              <th>Status</th>
              <th style="text-align: right">Action</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in resetRequests" :key="r.id">
              <td><span style="color: var(--accent)">{{ r.identifier }}</span></td>
              <td class="dim" :title="fmtDateTime(r.created_at)">{{ relativeTime(r.created_at) }}</td>
              <td>
                <span v-if="r.handled" class="mono" style="color: var(--fg-3); font-size: var(--fs-xs)">handled</span>
                <Pill v-else kind="warn">pending</Pill>
              </td>
              <td style="text-align: right">
                <button
                  v-if="!r.handled"
                  class="btn btn-sm"
                  :disabled="resolvingId === r.id"
                  @click="markHandled(r.id)"
                >
                  <Icon name="check" :size="12" /> Mark handled
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </template>
    </template>
  </div>

  <div class="panel rise-in">
    <div class="panel-head">
      <span class="panel-title">// user_management</span>
      <div class="field" style="width: 240px">
        <Icon name="search" :size="14" />
        <input placeholder="grep_user..." v-model="q" />
      </div>
    </div>
    <Loading v-if="loading" label="loading_users" />
    <div v-else-if="error" class="panel-body" style="color: var(--sev-high)">{{ error }}</div>
    <template v-else>
      <div v-if="actionError" class="notice notice-err" style="margin: 12px 14px 0">
        <Icon name="alert" :size="14" />
        <span>{{ actionError }}</span>
      </div>
      <table class="tbl">
        <thead>
          <tr>
            <th>User</th>
            <th>Email</th>
            <th>Role</th>
            <th>Active</th>
            <!-- Fixed width: the reset flow swaps button → confirm →
                 temp-password row; without it every swap reflows the
                 whole table. Sized for the widest (temp) state. -->
            <th style="text-align: right; width: 380px">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in list" :key="u.id" :class="[!u.is_active ? 'row-inactive' : '', u.id === auth.me?.id ? 'row-self' : '']">
            <td>
              <span style="color: var(--accent)">{{ u.username }}</span>
              <span v-if="u.id === auth.me?.id" class="mono" style="color: var(--fg-3); font-size: var(--fs-xs); margin-left: 8px">you</span>
            </td>
            <td class="dim">{{ u.email }}</td>
            <td>
              <Pill v-if="u.is_staff" kind="accent">STAFF</Pill>
              <span v-else class="mono" style="color: var(--fg-2)">member</span>
            </td>
            <td>
              <button
                role="switch"
                :aria-checked="u.is_active"
                :aria-disabled="u.id === auth.me?.id"
                :class="['switch', u.is_active ? 'on' : '']"
                @click="toggleActive(u)"
                :title="u.id === auth.me?.id ? `You can't deactivate your own account` : (u.is_active ? 'Deactivate' : 'Reactivate')"
              />
            </td>
            <td style="text-align: right">
              <span v-if="tempPw[u.id]" class="row-flex" style="gap: 6px; justify-content: flex-end">
                <span class="mono" style="font-size: var(--fs-xs); color: var(--fg-2)">temp:</span>
                <span class="mono" style="font-size: var(--fs-xs); color: var(--accent); user-select: all">{{ tempPw[u.id] }}</span>
                <button class="btn btn-sm" @click="copyTemp(u.id)" :title="copied === 'pw:' + u.id ? 'Copied' : 'Copy temp password'">
                  <Icon :name="copied === 'pw:' + u.id ? 'check' : 'code'" :size="12" />
                </button>
                <button class="btn btn-sm" @click="copyEmail(u)" :title="copied === 'mail:' + u.id ? 'Copied' : 'Copy a ready-to-send email'">
                  <Icon :name="copied === 'mail:' + u.id ? 'check' : 'book'" :size="12" />
                </button>
                <a v-if="u.email" class="btn btn-sm" :href="mailtoHref(u)" title="Open prefilled in your email app">
                  <Icon name="arrowRight" :size="12" />
                </a>
                <button class="btn btn-sm" @click="dismissTemp(u.id)" title="Dismiss">
                  <Icon name="x" :size="12" />
                </button>
              </span>
              <span v-else-if="reset[u.id] === 'confirm'" class="row-flex" style="gap: 6px; justify-content: flex-end">
                <span class="mono" style="font-size: var(--fs-xs); color: var(--fg-2)">reset this user's password?</span>
                <button class="btn btn-sm" @click="cancelReset(u.id)">No</button>
                <button class="btn btn-sm btn-primary" :disabled="busy === u.id" @click="doReset(u.id)">Yes</button>
              </span>
              <button
                v-else
                class="btn btn-sm"
                @click="askReset(u.id)"
                :disabled="!u.is_active || u.id === auth.me?.id"
                :title="u.id === auth.me?.id ? 'Resetting your own password would log you out. Use the Django admin instead.' : ''"
              >
                <Icon name="key" :size="12" /> Reset password
              </button>
            </td>
          </tr>
          <tr v-if="list.length === 0">
            <td colspan="5" class="mono dim" style="text-align: center; padding: 20px">No users match "{{ q }}".</td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>
