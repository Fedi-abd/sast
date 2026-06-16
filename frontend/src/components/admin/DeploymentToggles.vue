<script setup>
import { ref, onMounted } from 'vue';
import { fetchAdminSettings, updateAdminSettings, redirectToLogin, UnauthorizedError } from '../../api.js';
import Icon from '../Icon.vue';
import Loading from '../Loading.vue';

const FLAGS = [
  {
    key: 'hide_local_source',
    title: 'Hide local-path source type',
    tag: 'PROD SAFETY', tagClass: 'tag-warn',
    readonly: false,
    desc: 'Removes the “Local path” option from New project, and the API refuses new local-path projects while this is on. Existing local projects keep scanning.',
  },
  {
    key: 'show_debug_ui',
    title: 'Show debug UI',
    tag: 'ENV-MANAGED', tagClass: 'tag-dim',
    readonly: true,
    desc: 'Serves the legacy Django-templated UI under /debug/ as a debug fallback. Managed by the SAST_DEBUG_UI environment variable; changing it means editing .env and restarting the server.',
  },
];

const flags = ref({});
const loading = ref(true);
const error = ref(null);
const busy = ref(false);
const saveError = ref(null);
const savedKey = ref(null);

onMounted(async () => {
  try {
    flags.value = await fetchAdminSettings();
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    error.value = 'Failed to load deployment flags. Is the API up?';
  } finally {
    loading.value = false;
  }
});

const toggle = async (f) => {
  // show_debug_ui is env-managed; the server 400s any PATCH of it.
  if (f.readonly || busy.value) return;
  busy.value = true;
  saveError.value = null;
  try {
    // PATCH echoes the full flag payload; adopt server truth, no optimistic flip.
    flags.value = await updateAdminSettings({ [f.key]: !flags.value[f.key] });
    savedKey.value = f.key;
    setTimeout(() => { if (savedKey.value === f.key) savedKey.value = null; }, 1400);
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    saveError.value = (e.body && e.body.detail) || 'Save failed. The flag was left unchanged.';
  } finally {
    busy.value = false;
  }
};
</script>

<template>
  <div class="panel rise-in">
    <div class="panel-head">
      <span class="panel-title">// deployment_flags</span>
      <span class="kbd-hint mono">saved on toggle</span>
    </div>

    <div v-if="loading" class="panel-body">
      <Loading label="loading_flags" />
    </div>

    <div v-else-if="error" class="panel-body" style="color: var(--sev-high)">{{ error }}</div>

    <div v-else class="panel-body" style="padding-top: 4px; padding-bottom: 4px">
      <div v-if="saveError" class="notice notice-err" style="margin: 12px 0">
        <Icon name="alert" :size="14" />
        <span>{{ saveError }}</span>
      </div>
      <div v-for="f in FLAGS" :key="f.key" class="flag-row">
        <button
          role="switch"
          :aria-checked="flags[f.key]"
          :aria-disabled="f.readonly || busy"
          :class="['switch', flags[f.key] ? 'on' : '']"
          @click="toggle(f)"
          style="margin-top: 2px"
        />
        <div class="flag-body">
          <div class="flag-title">
            {{ f.title }}
            <span :class="['tag', f.tagClass]">{{ f.tag }}</span>
            <span v-if="savedKey === f.key" class="saved-flash"><Icon name="check" :size="12" /> saved</span>
          </div>
          <div class="flag-desc">{{ f.desc }}</div>
        </div>
        <span class="mono" :style="{ fontSize: 'var(--fs-xs)', color: flags[f.key] ? 'var(--accent)' : 'var(--fg-3)', flexShrink: 0, marginTop: '4px' }">
          {{ flags[f.key] ? 'ON' : 'OFF' }}
        </span>
      </div>
    </div>
  </div>
</template>
