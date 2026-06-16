<script setup>
import { ref, computed, onMounted } from 'vue';
import {
  fetchAdminLimits,
  updateAdminLimits,
  redirectToLogin,
  UnauthorizedError,
  ApiError,
} from '../../api.js';
import Icon from '../Icon.vue';
import Loading from '../Loading.vue';

const COLS = ['credits', 'max_projects', 'max_upload_mb'];
const clone = (arr) => arr.map((r) => ({ ...r }));

const rows = ref([]);
const baseline = ref([]);
const loading = ref(true);
const error = ref(null);

const load = async () => {
  const list = await fetchAdminLimits();
  rows.value = clone(list);
  baseline.value = clone(list);
};

onMounted(async () => {
  try {
    await load();
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    error.value = 'Failed to load user limits. Is the API up?';
  } finally {
    loading.value = false;
  }
});

const setField = (i, key, raw) => {
  // Blank OR a negative entry both mean unlimited (-1 sentinel) so the
  // admin can either clear the cell or just type -1; otherwise a
  // non-negative integer.
  const n = Number(raw);
  const v = (raw === '' || (Number.isFinite(n) && n < 0)) ? -1 : Math.max(0, Math.floor(n || 0));
  rows.value[i][key] = v;
};
const cellDirty = (i, k) => rows.value[i][k] !== baseline.value[i][k];
const rowDirty = (i) => COLS.some((k) => cellDirty(i, k));
const dirtyCount = computed(() => rows.value.filter((_, i) => rowDirty(i)).length);

const busy = ref(false);
const saved = ref(false);
const saveError = ref(null);

const save = async () => {
  if (busy.value) return;
  busy.value = true;
  saveError.value = null;
  const dirty = rows.value
    .filter((_, i) => rowDirty(i))
    .map((r) => ({
      user_id: r.user_id,
      credits: r.credits,
      max_projects: r.max_projects,
      max_upload_mb: r.max_upload_mb,
    }));
  try {
    await updateAdminLimits(dirty);
    // PATCH response may omit unchanged rows; refetch for the
    // canonical table instead of patching local state by hand.
    await load();
    saved.value = true;
    setTimeout(() => { saved.value = false; }, 1800);
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    // The batch is all-or-nothing server-side, so edits stay in place
    // for the admin to fix and retry.
    saveError.value =
      e instanceof ApiError && e.body && typeof e.body.detail === 'string'
        ? e.body.detail
        : 'Save failed. Nothing was written. Check the values and retry.';
  } finally {
    busy.value = false;
  }
};
const discard = () => {
  rows.value = clone(baseline.value);
  saveError.value = null;
};
</script>

<template>
  <div class="rise-in">
    <div class="panel">
      <div class="panel-head">
        <span class="panel-title">// per_user_limits</span>
        <span class="row-flex" style="gap: 10px">
          <span v-if="saved" class="mono" style="color: var(--ok); font-size: var(--fs-xs)"><Icon name="check" :size="12" /> saved</span>
          <span class="kbd-hint mono">click a value to edit &middot; blank = ∞</span>
        </span>
      </div>
      <Loading v-if="loading" label="loading_limits" />
      <div v-else-if="error" class="panel-body" style="color: var(--sev-high)">{{ error }}</div>
      <table v-else class="tbl">
        <thead>
          <tr>
            <th>User</th>
            <th class="num">Credits</th>
            <th class="num">Max projects</th>
            <th class="num">Max upload (MB)</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in rows" :key="r.user_id" :class="rowDirty(i) ? 'row-dirty' : ''">
            <td><span style="color: var(--accent)">{{ r.username }}</span></td>
            <td v-for="k in COLS" :key="k" class="num">
              <input
                type="number"
                placeholder="∞"
                :disabled="busy"
                :class="['cell-input', cellDirty(i, k) ? 'dirty' : '']"
                :value="r[k] < 0 ? '' : r[k]"
                @input="setField(i, k, $event.target.value)"
                :aria-label="`${r.username} ${k}`"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="dirtyCount > 0" class="save-bar">
      <span class="sb-label">
        <strong>{{ dirtyCount }}</strong> {{ dirtyCount === 1 ? 'user' : 'users' }} modified · not yet saved
      </span>
      <span v-if="saveError" class="form-error">{{ saveError }}</span>
      <div class="row-flex" style="gap: 8px">
        <button class="btn btn-sm" :disabled="busy" @click="discard">Discard</button>
        <button class="btn btn-sm btn-primary" :disabled="busy" @click="save">
          <Icon name="check" :size="12" /> {{ busy ? 'Saving…' : 'Save changes' }}
        </button>
      </div>
    </div>
  </div>
</template>
