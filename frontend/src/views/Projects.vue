<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import {
  fetchProjects, fetchScans, fetchConfig, latestScanFor as latestScanForApi,
  redirectToLogin, UnauthorizedError,
} from '../api.js';
import { sourceLabel, sourceTarget, relativeTime, scanStatusMeta } from '../lib/format.js';
import Icon from '../components/Icon.vue';
import Skeleton from '../components/Skeleton.vue';
import StatusText from '../components/StatusText.vue';
import SourceIcon from '../components/SourceIcon.vue';
import ProjectCard from '../components/ProjectCard.vue';

const router = useRouter();

const projects = ref([]);
const scans = ref([]);
const maxProjects = ref(null);
const loading = ref(true);
const error = ref(null);

onMounted(async () => {
  try {
    // Cards JOIN the latest scan client-side, so we need both lists.
    // Config failure shouldn't block the page; the quota line just hides.
    const [p, s, cfg] = await Promise.all([
      fetchProjects(),
      fetchScans(),
      fetchConfig().catch((e) => { if (e instanceof UnauthorizedError) throw e; return null; }),
    ]);
    projects.value = p;
    scans.value = s;
    maxProjects.value = cfg ? cfg.max_projects : null;
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    error.value = 'Failed to load projects. Is the API up?';
  } finally {
    loading.value = false;
  }
});

const atLimit = computed(() => maxProjects.value != null && maxProjects.value >= 0 && projects.value.length >= maxProjects.value);
// At the limit the button stays clickable and explains itself in a
// popup; a disabled button with a hover tooltip went unnoticed.
const limitPopup = ref(false);
const newProject = () => {
  if (atLimit.value) { limitPopup.value = true; return; }
  router.push('/projects/new');
};
// Admins can lower max_projects below the existing count; render that
// state deliberately (red counter) instead of looking like a glitch.
const overLimit = computed(() => maxProjects.value != null && maxProjects.value >= 0 && projects.value.length > maxProjects.value);

// Local selector closing over the fetched scans (api.latestScanFor
// takes the scans array explicitly since there's no module-global).
const latestScanFor = (projectId) => latestScanForApi(scans.value, projectId);

const FILTERS = [
  { id: 'all',    label: 'ALL_TYPES',  match: () => true },
  { id: 'local',  label: 'LOCAL_PATH', match: (p) => p.source_type === 'local' },
  { id: 'git',    label: 'GIT_REPO',   match: (p) => p.source_type === 'git' },
  { id: 'upload', label: 'UPLOAD',     match: (p) => p.source_type === 'upload' },
];

const filter = ref('all');
const query = ref('');
const view = ref('grid');

const activeFilter = computed(() => FILTERS.find(x => x.id === filter.value));
const list = computed(() => {
  const q = query.value.toLowerCase();
  return projects.value
    .filter(activeFilter.value.match)
    .filter(p => p.name.toLowerCase().includes(q) || (sourceTarget(p) || '').toLowerCase().includes(q));
});
const countOf = (f) => projects.value.filter(f.match).length;
</script>

<template>
  <div v-if="loading" class="page">
    <div class="page-head"><div><h1 class="page-title">Projects</h1></div></div>
    <Skeleton label="loading_projects" variant="chips" :count="4" />
    <Skeleton variant="cards" :count="6" />
  </div>

  <div v-else-if="error" class="page">
    <div class="page-head"><div><h1 class="page-title">Projects</h1></div></div>
    <div class="panel"><div class="panel-body" style="color: var(--sev-high)">{{ error }}</div></div>
  </div>

  <!-- First-run empty state -->
  <div v-else-if="projects.length === 0" class="page">
    <div class="page-head"><div><h1 class="page-title rise-in">Projects</h1></div></div>
    <div class="panel">
      <div class="panel-body" style="text-align: center; padding: 64px">
        <Icon name="projects" :size="28" />
        <div style="margin-top: 16px; font-size: var(--fs-lg); font-weight: 500">No projects yet</div>
        <div class="mono" style="margin-top: 6px; color: var(--fg-2); font-size: var(--fs-sm)">
          Register a codebase to start scanning for vulnerabilities.
        </div>
        <button class="btn btn-primary" style="margin-top: 20px" @click="router.push('/projects/new')">
          <Icon name="plus" :size="14" /> Create your first project
        </button>
      </div>
    </div>
  </div>

  <div v-else class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title rise-in">Projects</h1>
        <div class="page-sub">
          <span class="mono" :style="overLimit ? 'color: var(--sev-high)' : null">{{ projects.length }}<template v-if="maxProjects != null"> / {{ maxProjects < 0 ? '∞' : maxProjects }}</template> registered</span>
          <span class="mono" style="color: var(--fg-3)"> · </span>
          <span class="mono">view: {{ list.length }} match</span>
          <div v-if="atLimit" class="mono" style="color: var(--sev-med); margin-top: 4px">
            {{ overLimit ? 'over project limit' : 'project limit reached' }}. Ask an admin to raise it.
          </div>
        </div>
      </div>
      <button
        class="btn btn-primary"
        :title="atLimit ? 'Project limit reached. Ask an admin to raise it.' : null"
        @click="newProject"
      >
        <Icon name="plus" :size="14" /> New project
      </button>
    </div>

    <div v-if="limitPopup" class="limit-overlay" @click.self="limitPopup = false">
      <div class="panel limit-modal">
        <div class="panel-head"><span class="panel-title">// project_limit</span></div>
        <div class="panel-body">
          <p class="mono" style="margin: 0 0 8px">
            You're at your project limit
            <span style="color: var(--sev-high)">({{ projects.length }} / {{ maxProjects }})</span>.
          </p>
          <p class="mono" style="margin: 0 0 16px; color: var(--fg-2); font-size: var(--fs-sm)">
            Ask an administrator to raise it, or purge a project you no longer need.
          </p>
          <button class="btn" @click="limitPopup = false">OK</button>
        </div>
      </div>
    </div>

    <div class="row-between" style="margin-bottom: 20px; gap: 12px; flex-wrap: wrap">
      <div style="display: flex; gap: 6px; flex-wrap: wrap">
        <button
          v-for="x in FILTERS"
          :key="x.id"
          :class="['chip', filter === x.id ? 'active' : '']"
          @click="filter = x.id"
        >
          {{ x.label }}
          <span style="opacity: 0.7">{{ countOf(x) }}</span>
        </button>
      </div>

      <div style="display: flex; gap: 8px">
        <div class="field" style="width: 280px">
          <Icon name="search" :size="14" />
          <input v-model="query" placeholder="grep_project..." />
        </div>
        <div style="display: flex; border: 1px solid var(--line); border-radius: 4px; overflow: hidden">
          <button :class="['btn btn-sm', view === 'grid' ? 'btn-primary' : 'btn-ghost']" style="border-radius: 0; border: none" @click="view = 'grid'">Grid</button>
          <button :class="['btn btn-sm', view === 'list' ? 'btn-primary' : 'btn-ghost']" style="border-radius: 0; border: none" @click="view = 'list'">List</button>
        </div>
      </div>
    </div>

    <div v-if="view === 'grid'" class="project-grid">
      <ProjectCard
        v-for="(p, idx) in list"
        :key="p.id"
        :p="p"
        :latest="latestScanFor(p.id)"
        class="rise-in"
        :style="{ animationDelay: (idx * 40) + 'ms' }"
      />
    </div>

    <div v-else class="panel">
      <table class="tbl">
        <thead>
          <tr>
            <th>Name</th>
            <th>Source</th>
            <th>Language</th>
            <th>Last scan</th>
            <th class="num">Findings</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(p, idx) in list"
            :key="p.id"
            class="rise-in"
            :style="{ animationDelay: (idx * 40) + 'ms', cursor: 'pointer' }"
            @click="router.push(`/project/${p.id}`)"
          >
            <td>
              <div style="display: flex; flex-direction: column">
                <span style="color: var(--accent); font-size: var(--fs-md)">{{ p.name }}</span>
                <span style="color: var(--fg-3); font-size: var(--fs-xs)">{{ sourceTarget(p) }}</span>
              </div>
            </td>
            <td><span class="pill"><SourceIcon :type="p.source_type" />{{ sourceLabel(p.source_type) }}</span></td>
            <td><span class="pill">{{ p.language }}</span></td>
            <td class="dim">{{ latestScanFor(p.id) ? relativeTime(latestScanFor(p.id).started_at) : '-' }}</td>
            <td class="num mono">{{ latestScanFor(p.id) && latestScanFor(p.id).finding_count != null ? latestScanFor(p.id).finding_count : '-' }}</td>
            <td>
              <StatusText v-if="latestScanFor(p.id)" :kind="scanStatusMeta(latestScanFor(p.id).status).kind" :label="scanStatusMeta(latestScanFor(p.id).status).label" />
              <span v-else class="mono dim">NO_SCANS</span>
            </td>
            <td><Icon name="chevronRight" :size="14" /></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="list.length === 0" class="panel" style="margin-top: 16px">
      <div class="panel-body" style="text-align: center; padding: 48px">
        <Icon name="search" :size="20" />
        <div class="mono" style="margin-top: 12px; color: var(--fg-1)">
          No projects match <span style="color: var(--accent)">"{{ query }}"</span> in <span style="color: var(--accent)">{{ activeFilter.label }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.limit-overlay {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(2px);
}
.limit-modal {
  width: min(420px, calc(100vw - 48px));
}
</style>
