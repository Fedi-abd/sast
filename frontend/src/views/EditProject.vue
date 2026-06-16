<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import Icon from '../components/Icon.vue';
import Loading from '../components/Loading.vue';
import CliSelect from '../components/CliSelect.vue';
import { sourceLabel } from '../lib/format.js';
import { fetchProject, updateProject, redirectToLogin, UnauthorizedError, ApiError } from '../api.js';

const props = defineProps({ id: { type: String, default: '' } });
const router = useRouter();
const LANGS = ['Go', 'Python', 'Java', 'JavaScript', 'TypeScript', 'Ruby', 'C', 'C++', 'C#', 'Rust', 'PHP', 'Kotlin', 'Swift'];

const project = ref(null);
const loading = ref(true);
const loadError = ref(null);

const name = ref('');
const language = ref('');
const git = ref('');
const branch = ref('');
const localPath = ref('');

const errors = reactive({});
const banner = ref('');
const busy = ref(false);

onMounted(async () => {
  try {
    const proj = await fetchProject(props.id);
    project.value = proj;
    name.value = proj.name || '';
    language.value = proj.language || '';
    git.value = proj.git_url || '';
    branch.value = proj.git_branch || '';
    localPath.value = proj.repo_path || '';
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    loadError.value = 'Failed to load the project. Is the API up?';
  } finally {
    loading.value = false;
  }
});

const archiveName = computed(() =>
  project.value ? (project.value.source_filename || project.value.source_archive || '-') : '-');

const valid = computed(() => {
  if (!project.value) return false;
  if (!name.value.trim()) return false;
  if (project.value.source_type === 'git' && !git.value.trim()) return false;
  if (project.value.source_type === 'local' && !localPath.value.trim()) return false;
  return true;
});

// DRF returns {field: [messages]}; map the backend names onto the
// form's error slots so server-side validation reads like client-side.
const applyServerErrors = (body) => {
  if (!body || typeof body !== 'object') {
    banner.value = 'Save failed. Is the API up?';
    return;
  }
  const first = (v) => (Array.isArray(v) ? v[0] : String(v));
  if (body.name) errors.name = first(body.name);
  if (body.git_url) errors.git = first(body.git_url);
  if (body.repo_path) errors.local = first(body.repo_path);
  const general = body.non_field_errors || body.detail || body.source_type;
  if (general) banner.value = first(general);
  else if (Object.keys(errors).length === 0) banner.value = 'Save failed. Check the form.';
};

const save = async () => {
  if (busy.value || !project.value) return;
  Object.keys(errors).forEach(k => delete errors[k]);
  banner.value = '';
  if (!name.value.trim()) errors.name = 'Project name is required.';
  if (project.value.source_type === 'git' && !git.value.trim()) errors.git = 'Repository URL is required.';
  if (project.value.source_type === 'local' && !localPath.value.trim()) errors.local = 'Path is required.';
  if (Object.keys(errors).length > 0) return;

  busy.value = true;
  try {
    // Only the editable fields; source_type and source_archive are
    // locked server-side and never belong in the payload.
    const payload = { name: name.value.trim(), language: language.value };
    if (project.value.source_type === 'git') {
      // Accept scheme-less input ("github.com/org/repo"): the
      // backend requires http(s), so assume https when omitted.
      let url = git.value.trim();
      if (url && !/^https?:\/\//i.test(url)) url = 'https://' + url;
      payload.git_url = url;
      payload.git_branch = branch.value.trim();
    } else if (project.value.source_type === 'local') {
      payload.repo_path = localPath.value.trim();
    }
    await updateProject(props.id, payload);
    router.push('/project/' + props.id);
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    applyServerErrors(e instanceof ApiError ? e.body : null);
  } finally {
    busy.value = false;
  }
};
</script>

<template>
  <div v-if="loading" class="page">
    <div class="page-head"><div><h1 class="page-title">Edit project</h1></div></div>
    <Loading label="loading_project" />
  </div>

  <div v-else-if="loadError || !project" class="page">
    <div class="page-head"><div><h1 class="page-title">Edit project</h1></div></div>
    <div class="panel"><div class="panel-body" style="color: var(--sev-high)">{{ loadError || 'Project not found.' }}</div></div>
  </div>

  <div v-else class="page">
    <div class="page-head">
      <div>
        <div class="page-sub" style="margin-bottom: 8px">
          <a class="mono" style="color: var(--fg-2); cursor: pointer" @click="router.push(`/project/${props.id}`)">← {{ project.name }}</a>
        </div>
        <h1 class="page-title rise-in">Edit project</h1>
        <div class="page-sub" style="margin-top: 4px">
          <span class="mono">id: {{ project.id }}</span>
        </div>
      </div>
      <div style="display: flex; gap: 8px">
        <button class="btn" @click="router.push(`/project/${props.id}`)">Cancel</button>
        <button class="btn btn-primary" :disabled="!valid || busy" @click="save">
          <Icon name="check" :size="14" /> {{ busy ? 'Saving…' : 'Save changes' }}
        </button>
      </div>
    </div>

    <div v-if="banner" class="notice notice-err" style="margin-bottom: 24px">
      <Icon name="alert" :size="14" />
      <span>{{ banner }}</span>
    </div>

    <div class="panel ep-panel">
      <div class="panel-head"><span class="panel-title">// project_settings</span></div>
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

          <!-- Source type (locked after creation) -->
          <div class="form-label">Source</div>
          <div class="form-control">
            <div class="locked-row">
              <span class="pill">{{ sourceLabel(project.source_type) }}</span>
              <span class="mono dim">source type is locked after creation</span>
            </div>
          </div>

          <!-- Source-specific fields -->
          <template v-if="project.source_type === 'git'">
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

          <template v-else-if="project.source_type === 'local'">
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

          <template v-else-if="project.source_type === 'upload'">
            <div class="form-label">Archive</div>
            <div class="form-control">
              <div class="locked-row">
                <Icon name="archive" :size="14" />
                <span class="mono">{{ archiveName }}</span>
              </div>
              <div class="form-hint">The archive is immutable. Create a new project to replace it.</div>
            </div>
          </template>

          <!-- Language: display metadata only, scanners detect on their own -->
          <div class="form-label">Language</div>
          <div class="form-control">
            <CliSelect v-model="language" :options="LANGS" placeholder="Not specified" />
            <div class="form-hint">Optional display label. The scanners detect languages on their own.</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ep-panel {
  max-width: 760px;
}
.locked-row {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 7px 12px;
  border: 1px dashed var(--line);
  border-radius: var(--r-2);
  background: var(--bg-inset);
  color: var(--fg-1);
  font-size: var(--fs-sm);
}
.locked-row .dim {
  color: var(--fg-2);
  font-size: var(--fs-xs);
}
</style>
