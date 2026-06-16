<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import Icon from '../components/Icon.vue';
import CliSelect from '../components/CliSelect.vue';
import { sourceLabel } from '../lib/format.js';
import { createProject, fetchConfig, redirectToLogin, UnauthorizedError, ApiError } from '../api.js';

const router = useRouter();
const LANGS = ['Go', 'Python', 'Java', 'JavaScript', 'TypeScript', 'Ruby', 'C', 'C++', 'C#', 'Rust', 'PHP', 'Kotlin', 'Swift'];
const MAX_MB = ref(250);          // fallback until /api/config/ supplies the effective cap
const hideLocal = ref(true);      // hidden until /api/config/ answers, so the card never flashes in

const name = ref('');
const source = ref('git');
const git = ref('');
const branch = ref('main');
const localPath = ref('');
const file = ref(null);
const over = ref(false);
const language = ref('');
const errors = reactive({});
const banner = ref('');
const busy = ref(false);
const fileRef = ref(null);

// Deployment knobs tune the form (upload cap, local-path visibility);
// the defaults above are sane, so a failed fetch is non-blocking.
onMounted(async () => {
  try {
    const cfg = await fetchConfig();
    if (cfg.max_upload_mb != null) MAX_MB.value = cfg.max_upload_mb;
    hideLocal.value = Boolean(cfg.hide_local_source);
    if (hideLocal.value && source.value === 'local') source.value = 'git';
  } catch (e) {
    if (e instanceof UnauthorizedError) redirectToLogin();
  }
});

// Create stays clickable while the form is incomplete; submit() then
// paints red per-field errors (same pattern as signup). A disabled
// button that couldn't explain itself went unnoticed in QC.

// DRF returns {field: [messages]}; map the backend names onto the
// form's error slots so server-side validation reads like client-side.
const applyServerErrors = (body) => {
  if (!body || typeof body !== 'object') {
    banner.value = 'Create failed. Is the API up?';
    return;
  }
  const first = (v) => (Array.isArray(v) ? v[0] : String(v));
  if (body.name) errors.name = first(body.name);
  if (body.git_url) errors.git = first(body.git_url);
  if (body.repo_path) errors.local = first(body.repo_path);
  if (body.source_archive) errors.file = first(body.source_archive);
  const general = body.non_field_errors || body.detail || body.source_type;
  if (general) banner.value = first(general);
  else if (Object.keys(errors).length === 0) banner.value = 'Create failed. Check the form.';
};

const submit = async () => {
  if (busy.value) return;
  Object.keys(errors).forEach(k => delete errors[k]);
  banner.value = '';
  if (!name.value.trim()) errors.name = 'Project name is required.';
  if (source.value === 'git' && !git.value.trim()) errors.git = 'Repository URL is required.';
  if (source.value === 'local' && !localPath.value.trim()) errors.local = 'Path is required.';
  if (source.value === 'upload' && !file.value) errors.file = 'A .zip archive is required.';
  if (Object.keys(errors).length > 0) return;

  busy.value = true;
  try {
    let payload;
    if (source.value === 'upload') {
      const fd = new FormData();
      fd.append('name', name.value.trim());
      fd.append('source_type', 'upload');
      fd.append('source_archive', file.value);
      if (language.value) fd.append('language', language.value);
      payload = fd;
    } else {
      payload = { name: name.value.trim(), source_type: source.value, language: language.value };
      if (source.value === 'git') {
        // Accept scheme-less input ("github.com/org/repo"): the
        // backend requires http(s), so assume https when omitted.
        let url = git.value.trim();
        if (url && !/^https?:\/\//i.test(url)) url = 'https://' + url;
        payload.git_url = url;
        payload.git_branch = branch.value.trim();
      } else {
        payload.repo_path = localPath.value.trim();
      }
    }
    const created = await createProject(payload);
    router.push(`/project/${created.id}`);
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    applyServerErrors(e instanceof ApiError ? e.body : null);
  } finally {
    busy.value = false;
  }
};

const acceptFile = (f) => {
  if (!f) return;
  delete errors.file;
  if (MAX_MB.value === 0) { errors.file = 'Uploads are disabled for your account. Ask an admin.'; return; }
  if (!f.name.toLowerCase().endsWith('.zip')) { errors.file = 'Only .zip archives are accepted.'; return; }
  if (f.size > MAX_MB.value * 1024 * 1024) { errors.file = `Archive exceeds ${MAX_MB.value} MB.`; return; }
  file.value = f;
};

const onDrop = (ev) => {
  ev.preventDefault();
  over.value = false;
  acceptFile(ev.dataTransfer?.files?.[0]);
};

const onFile = (ev) => {
  acceptFile(ev.target.files?.[0] || null);
};

const fileSize = computed(() => {
  if (!file.value) return '';
  const b = file.value.size;
  return b < 1024 * 1024 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1024 / 1024).toFixed(2)} MB`;
});
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <div class="page-sub" style="margin-bottom: 8px">
          <a class="mono" style="color: var(--fg-2); cursor: pointer" @click="router.push('/projects')">← projects</a>
        </div>
        <h1 class="page-title rise-in">New project</h1>
        <div class="page-sub" style="margin-top: 4px">
          <span class="mono">register a codebase for static analysis</span>
        </div>
      </div>
      <div class="head-actions">
        <button class="btn" @click="router.push('/projects')">Cancel</button>
        <button class="btn btn-primary" :disabled="busy" @click="submit">
          <Icon name="check" :size="14" /> {{ busy ? 'Creating…' : 'Create project' }}
        </button>
      </div>
    </div>

    <div v-if="banner" class="notice notice-err" style="margin-bottom: 24px">
      <Icon name="alert" :size="14" />
      <span>{{ banner }}</span>
    </div>

    <div class="np-layout">
      <div class="panel">
        <div class="panel-body" style="padding: 28px">
          <div class="form-grid">

            <!-- Name -->
            <div class="form-label">Project name<span class="req">*</span></div>
            <div class="form-control">
              <div :class="['input', errors.name ? 'error' : '']">
                <input v-model="name" placeholder="e.g. core-auth-service" />
              </div>
              <div class="form-hint">Shown across the dashboard and reports.</div>
              <div v-if="errors.name" class="form-error">{{ errors.name }}</div>
            </div>

            <!-- Source type -->
            <div class="form-label">Source<span class="req">*</span></div>
            <div class="form-control">
              <div class="radio-cards">
                <div :class="['radio-card', source === 'git' ? 'checked' : '']" @click="source = 'git'">
                  <div class="rc-head">
                    <span class="rc-radio" />
                    <Icon name="git" :size="14" />
                    <span class="rc-title">Git repository</span>
                  </div>
                  <div class="rc-desc">Clone over HTTPS from github.com or gitlab.com.</div>
                </div>
                <div v-if="!hideLocal" :class="['radio-card', source === 'local' ? 'checked' : '']" @click="source = 'local'">
                  <div class="rc-head">
                    <span class="rc-radio" />
                    <Icon name="folder" :size="14" />
                    <span class="rc-title">Local path</span>
                  </div>
                  <div class="rc-desc">Absolute path on the scan host. Useful for mounted volumes.</div>
                </div>
                <div :class="['radio-card', source === 'upload' ? 'checked' : '']" @click="source = 'upload'">
                  <div class="rc-head">
                    <span class="rc-radio" />
                    <Icon name="archive" :size="14" />
                    <span class="rc-title">Upload archive</span>
                  </div>
                  <div class="rc-desc">ZIP archive, up to {{ MAX_MB }} MB. Extracted server-side before scanning.</div>
                </div>
              </div>
            </div>

            <!-- Conditional source fields -->
            <template v-if="source === 'git'">
              <div class="form-label">Repository URL<span class="req">*</span></div>
              <div class="form-control">
                <div :class="['input', 'prefix', errors.git ? 'error' : '']">
                  <span class="pfx">git ⏵</span>
                  <input v-model="git" placeholder="https://github.com/org/repo" />
                </div>
                <div class="form-hint">Host must be <span class="mono">github.com</span> or <span class="mono">gitlab.com</span>. <span class="mono">https://</span> is assumed if you omit it.</div>
                <div v-if="errors.git" class="form-error">{{ errors.git }}</div>
              </div>

              <div class="form-label">Branch</div>
              <div class="form-control">
                <div class="input"><input v-model="branch" /></div>
                <div class="form-hint">Defaults to <span class="mono">main</span>. Branch or tag names accepted.</div>
              </div>
            </template>

            <template v-else-if="source === 'local'">
              <div class="form-label">Filesystem path<span class="req">*</span></div>
              <div class="form-control">
                <div :class="['input', 'prefix', errors.local ? 'error' : '']">
                  <span class="pfx">path ⏵</span>
                  <input v-model="localPath" placeholder="/home/user/projects/my-app" />
                </div>
                <div class="form-hint">Must be an absolute path readable by the scan worker.</div>
                <div v-if="errors.local" class="form-error">{{ errors.local }}</div>
              </div>
            </template>

            <template v-else-if="source === 'upload'">
              <div class="form-label">Archive<span class="req">*</span></div>
              <div class="form-control">
                <div
                  :class="['drop', over ? 'over' : '']"
                  @dragover.prevent="over = true"
                  @dragleave="over = false"
                  @drop="onDrop"
                  @click="fileRef && fileRef.click()"
                >
                  <input ref="fileRef" type="file" accept=".zip" style="display: none" @change="onFile" />
                  <div v-if="file">
                    <div class="drop-file">
                      <Icon name="archive" :size="14" /> {{ file.name }}
                      <button style="margin-left: 8px" @click.stop="file = null">
                        <Icon name="x" :size="12" />
                      </button>
                    </div>
                    <div class="drop-sub" style="margin-top: 8px">
                      {{ fileSize }} · click to replace
                    </div>
                  </div>
                  <template v-else>
                    <div class="drop-title">Drop a .zip here</div>
                    <div class="drop-sub">or click to browse · max {{ MAX_MB }} MB</div>
                  </template>
                </div>
                <div v-if="errors.file" class="form-error">{{ errors.file }}</div>
              </div>
            </template>

            <!-- Language: display metadata only, scanners detect on their own -->
            <div class="form-label">Language</div>
            <div class="form-control">
              <CliSelect v-model="language" :options="LANGS" placeholder="not specified" />
              <div class="form-hint">Optional display label. The scanners detect languages on their own.</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Summary aside -->
      <div>
        <div class="summary-card">
          <h4>// commit_preview</h4>
          <dl style="margin: 0">
            <div class="summary-row">
              <dt>Name</dt>
              <dd>{{ name || '-' }}</dd>
            </div>
            <div class="summary-row">
              <dt>Source</dt>
              <dd>{{ sourceLabel(source) }}</dd>
            </div>
            <div class="summary-row">
              <dt>Target</dt>
              <dd>
                <template v-if="source === 'git'">{{ git || '-' }}</template>
                <template v-else-if="source === 'local'">{{ localPath || '-' }}</template>
                <template v-else>{{ file ? file.name : '-' }}</template>
              </dd>
            </div>
            <div v-if="source === 'git'" class="summary-row">
              <dt>Branch</dt>
              <dd>{{ branch || '-' }}</dd>
            </div>
            <div class="summary-row">
              <dt>Language</dt>
              <dd>{{ language || 'not specified' }}</dd>
            </div>
          </dl>
          <div class="divider-dashed" style="margin: 16px 0" />
          <div class="form-hint" style="line-height: 1.6">
            On create, the platform registers the source and the project becomes available for scanning. No scan runs automatically. Source type is locked after creation; delete and recreate to change it.
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.head-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}
/* The global np-layout/form-grid breakpoints (960/720px) fire too late:
   the 240px sidebar eats viewport, so two columns stop fitting near
   1200px and the 160px-min radio cards overflow under the aside. */
@media (max-width: 1200px) {
  .np-layout { grid-template-columns: 1fr; }
  .np-layout .summary-card { position: static; }
}
@media (max-width: 900px) {
  .form-grid {
    grid-template-columns: 1fr;
    row-gap: var(--sp-3);
  }
  .form-grid .form-label { padding-top: 0; }
}
</style>
