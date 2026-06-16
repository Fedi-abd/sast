<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import {
  fetchAdminSonarConfig,
  updateAdminSonarConfig,
  testAdminSonarConnection,
  redirectToLogin,
  UnauthorizedError,
  ApiError,
} from '../../api.js';
import { fmtDateTime } from '../../lib/format.js';
import Icon from '../Icon.vue';
import Loading from '../Loading.vue';

// The server rejects SECURITY_HOTSPOT; hotspots always come via their
// own SonarQube API, so they're not a configurable filter here.
const ISSUE_TYPES = ['VULNERABILITY', 'BUG', 'CODE_SMELL'];

const loading = ref(true);
const error = ref(null);

const host = ref('');
const issueTypes = ref([]);
const includeHotspots = ref(true);
const last4 = ref('');
const replacing = ref(false);
const newToken = ref('');
const baseline = ref({ host: '', issueTypes: [], includeHotspots: true });
const saved = ref(false);
const saving = ref(false);
const saveError = ref(null);
const test = ref('idle'); // idle | testing | ok | fail
const testRes = ref(null); // {server: bool, token: bool|null} from the verdict
const testDetail = ref('');
const meta = ref({ at: null, by: '' });

/** Server response is authoritative; repopulate everything from it. */
function applyConfig(cfg) {
  host.value = cfg.host || '';
  issueTypes.value = [...(cfg.issue_types || [])];
  includeHotspots.value = cfg.include_hotspots !== false;
  last4.value = cfg.token_last4 || '';
  meta.value = { at: cfg.updated_at, by: cfg.updated_by };
  baseline.value = {
    host: host.value,
    issueTypes: [...issueTypes.value],
    includeHotspots: includeHotspots.value,
  };
}

onMounted(async () => {
  try {
    applyConfig(await fetchAdminSonarConfig());
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    error.value = 'Failed to load SonarQube config. Is the API up?';
  } finally {
    loading.value = false;
  }
});

const dirty = computed(() =>
  host.value !== baseline.value.host ||
  [...issueTypes.value].sort().join() !== [...baseline.value.issueTypes].sort().join() ||
  includeHotspots.value !== baseline.value.includeHotspots ||
  (replacing.value && newToken.value.trim().length > 0)
);

const toggleType = (t) => {
  issueTypes.value = issueTypes.value.includes(t)
    ? issueTypes.value.filter((x) => x !== t)
    : [...issueTypes.value, t];
};

// The test verdict only vouches for the values it ran against. Any
// edit resets it, and the seq counter discards a verdict that lands
// after an edit mid-flight.
let testSeq = 0;
watch([host, issueTypes, includeHotspots, newToken, replacing], () => {
  testSeq++;
  test.value = 'idle';
  testRes.value = null;
  testDetail.value = '';
});

function saveErrorText(e) {
  if (e instanceof ApiError && e.body) {
    if (typeof e.body.detail === 'string') return e.body.detail;
    // DRF validation shape: {field: ["msg", ...]}
    const parts = Object.entries(e.body).map(
      ([field, msgs]) => `${field}: ${Array.isArray(msgs) ? msgs.join(' ') : msgs}`
    );
    if (parts.length) return parts.join(' · ');
  }
  return 'Save failed. Is the API up?';
}

const onSave = async () => {
  if (saving.value) return;
  saving.value = true;
  saveError.value = null;
  const body = {
    host: host.value,
    issue_types: issueTypes.value,
    include_hotspots: includeHotspots.value,
  };
  // Omitted token means "keep the stored one" server-side.
  if (replacing.value && newToken.value.trim()) body.token = newToken.value.trim();
  try {
    applyConfig(await updateAdminSonarConfig(body));
    replacing.value = false;
    newToken.value = '';
    saved.value = true;
    setTimeout(() => { saved.value = false; }, 1800);
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    saveError.value = saveErrorText(e);
  } finally {
    saving.value = false;
  }
};

const onCancel = () => {
  host.value = baseline.value.host;
  issueTypes.value = [...baseline.value.issueTypes];
  includeHotspots.value = baseline.value.includeHotspots;
  replacing.value = false;
  newToken.value = '';
  saveError.value = null;
};

const runTest = async () => {
  if (test.value === 'testing') return;
  const seq = ++testSeq;
  test.value = 'testing';
  testRes.value = null;
  testDetail.value = '';
  try {
    // Test the values as typed (unsaved edits included). An omitted
    // token means "use the saved/env one" server-side.
    const body = { host: host.value };
    if (replacing.value && newToken.value.trim()) body.token = newToken.value.trim();
    const res = await testAdminSonarConnection(body);
    if (seq !== testSeq) return; // config edited mid-test; verdict is stale
    test.value = res.ok ? 'ok' : 'fail';
    testRes.value = { server: res.server, token: res.token };
    testDetail.value = res.detail || '';
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    if (seq !== testSeq) return;
    test.value = 'fail';
    testRes.value = { server: false, token: null };
    testDetail.value = 'request failed. Is the API up?';
  }
};
</script>

<template>
  <div class="panel rise-in">
    <div class="panel-head">
      <span class="panel-title">// sonarqube_integration</span>
      <span class="kbd-hint mono">shared · all scans</span>
    </div>

    <Loading v-if="loading" label="loading_config" />

    <div v-else-if="error" class="panel-body" style="color: var(--sev-high)">{{ error }}</div>

    <div v-else class="panel-body" style="padding: 28px">
      <div class="notice" style="margin-bottom: 24px; background: var(--bg-1)">
        <Icon name="server" :size="14" />
        <span>This is a <strong>single shared configuration</strong>; it applies to every SonarQube scan across all users, not per-user.</span>
      </div>

      <div class="form-grid">
        <!-- Host -->
        <div class="form-label">Host</div>
        <div class="form-control">
          <div class="input prefix">
            <span class="pfx">url ⏵</span>
            <input v-model="host" placeholder="https://sonarqube.internal" />
          </div>
          <div class="form-hint">Base URL of the SonarQube server the workers reach. http(s) only.</div>
        </div>

        <!-- Token -->
        <div class="form-label">Auth token</div>
        <div class="form-control">
          <div v-if="!replacing" class="row-flex" style="gap: 12px; flex-wrap: wrap">
            <span v-if="last4" class="mono" style="font-size: var(--fs-sm); color: var(--fg-1); letter-spacing: 0.08em">••••••••••••{{ last4 }}</span>
            <span v-else class="mono" style="font-size: var(--fs-sm); color: var(--sev-med)">no token configured</span>
            <button class="btn btn-sm" @click="replacing = true"><Icon name="key" :size="12" /> {{ last4 ? 'Replace token' : 'Set token' }}</button>
          </div>
          <div v-else class="col-stack" style="gap: 8px">
            <div class="input">
              <input type="password" autofocus placeholder="Paste new SonarQube token" v-model="newToken" />
            </div>
            <div>
              <button class="btn btn-sm" @click="replacing = false; newToken = ''">{{ last4 ? `Keep current (•••${last4})` : 'Cancel' }}</button>
            </div>
          </div>
          <div class="form-hint">Stored encrypted. The API only ever returns the last 4 characters; the full token is never echoed back.</div>
        </div>

        <!-- Issue types. The first three are import filters; the hotspot
             chip looks the same but toggles display only (separate API). -->
        <div class="form-label">Default issue types</div>
        <div class="form-control">
          <div style="display: flex; gap: 8px; flex-wrap: wrap">
            <button
              v-for="t in ISSUE_TYPES"
              :key="t"
              :class="['chip', issueTypes.includes(t) ? 'active' : '']"
              :aria-pressed="issueTypes.includes(t)"
              @click="toggleType(t)"
            >
              <Icon :name="issueTypes.includes(t) ? 'check' : 'plus'" :size="12" /> {{ t }}
            </button>
            <button
              class="chip"
              :class="includeHotspots ? 'active' : ''"
              :aria-pressed="includeHotspots"
              @click="includeHotspots = !includeHotspots"
            >
              <Icon :name="includeHotspots ? 'check' : 'plus'" :size="12" /> SECURITY_HOTSPOT
            </button>
          </div>
          <div class="form-hint">
            The first three set which categories are imported. SECURITY_HOTSPOT
            is always scanned; its chip just shows or hides it.
            <span v-if="issueTypes.length === 0" style="color: var(--sev-med)"> &middot; At least one type is recommended.</span>
            <span v-if="!includeHotspots" style="color: var(--sev-med)"> &middot; Hotspots are security findings, hidden from every scan view while off.</span>
          </div>
        </div>
      </div>

      <div class="divider" />

      <div class="row-between" style="flex-wrap: wrap; gap: 12px">
        <span class="mono" style="font-size: var(--fs-xs); color: var(--fg-2)">
          last updated {{ fmtDateTime(meta.at) }} by <span style="color: var(--fg-1)">{{ meta.by || '-' }}</span>
        </span>
        <div class="row-flex" style="gap: 8px; flex-wrap: wrap">
          <span v-if="testRes" class="row-flex mono" style="gap: 10px; font-size: var(--fs-xs)">
            <span>server
              <span :style="{ color: testRes.server ? 'var(--ok)' : 'var(--sev-high)' }">[{{ testRes.server ? 'OK' : 'FAIL' }}]</span>
            </span>
            <span>token
              <span :style="{ color: testRes.token === true ? 'var(--ok)' : (testRes.token === false ? 'var(--sev-high)' : 'var(--fg-3)') }">[{{ testRes.token === true ? 'OK' : (testRes.token === false ? 'FAIL' : '-') }}]</span>
            </span>
          </span>
          <span v-if="test === 'fail'" class="mono" style="font-size: var(--fs-xs); color: var(--sev-high); max-width: 300px; overflow-wrap: anywhere">{{ testDetail || 'connection failed' }}</span>
          <button
            class="btn btn-sm"
            @click="runTest"
            :disabled="test === 'testing'"
            title="Tests the values as typed (unsaved edits included)"
          >
            <span v-if="test === 'testing'" class="spinner" /><Icon v-else name="scan" :size="12" /> Test connection
          </button>
          <span v-if="saveError" class="mono" style="font-size: var(--fs-xs); color: var(--sev-high); max-width: 360px; overflow-wrap: anywhere">{{ saveError }}</span>
          <span v-if="saved" class="saved-flash"><Icon name="check" :size="12" /> saved</span>
          <button class="btn" @click="onCancel" :disabled="!dirty || saving">Cancel</button>
          <button class="btn btn-primary" @click="onSave" :disabled="!dirty || saving">
            <span v-if="saving" class="spinner" /><Icon v-else name="check" :size="14" /> Save changes
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
