<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import {
  fetchProject, fetchScans, triggerScan, deleteProject,
  redirectToLogin, UnauthorizedError, ApiError,
} from '../api.js';
import { auth, refreshMe } from '../auth.js';
import { sourceTarget, fmtDateTime, formatDuration, scanStatusMeta } from '../lib/format.js';
import Icon from '../components/Icon.vue';
import Pill from '../components/Pill.vue';
import StatusText from '../components/StatusText.vue';
import SourceIcon from '../components/SourceIcon.vue';
import ScanActionCard from '../components/ScanActionCard.vue';
import Skeleton from '../components/Skeleton.vue';

const props = defineProps({ id: { type: String, default: '' } });
const router = useRouter();

const TOOL_COST = { semgrep: 1, sonarqube: 1, both: 2 };

const project = ref(null);
const scans = ref([]);
const loading = ref(true);
const error = ref(null);
const triggerError = ref(null);
const busy = ref(false);

// staff and unlimited (negative sentinel) users are unmetered
// server-side; never gate their scan cards
const credits = computed(() => {
  if (auth.me?.is_staff) return Infinity;
  const c = auth.me?.credits ?? 0;
  return c < 0 ? Infinity : c;
});
const runs = computed(() => scans.value
  .filter(r => r.project_id === props.id)
  .sort((a, b) => new Date(b.started_at) - new Date(a.started_at)));
const runningScans = computed(() => runs.value.filter(r => r.status === 'RUNNING'));
const running = computed(() => runningScans.value[0] || null);
const runningTools = computed(() => new Set(runningScans.value.map(r => r.tool)));

// Static analysers don't stream progress, so while a scan is RUNNING we
// just re-poll the scan list every 3s and stop once it settles.
let pollTimer = null;
const stopPolling = () => { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } };
const startPolling = () => {
  if (pollTimer) return;
  pollTimer = setInterval(async () => {
    try { scans.value = await fetchScans(); } catch { /* keep last good list */ }
    if (!running.value) { stopPolling(); refreshMe(); }
  }, 3000);
};

const load = async () => {
  loading.value = true;
  error.value = null;
  try {
    const [proj, allScans] = await Promise.all([fetchProject(props.id), fetchScans()]);
    project.value = proj;
    scans.value = allScans;
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    error.value = 'Failed to load the project. Is the API up?';
  } finally {
    loading.value = false;
  }
};

const trigger = async (tool) => {
  triggerError.value = null;
  if (busy.value) return;
  busy.value = true;
  try {
    await triggerScan(props.id, tool);
    scans.value = await fetchScans();   // the new RUNNING scan(s) show up
    await refreshMe();                  // credits were just spent
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    triggerError.value = (e instanceof ApiError && e.status === 402)
      ? 'Not enough credits for that scan.'
      : 'Could not start the scan. Try again.';
  } finally {
    busy.value = false;
  }
};

const purge = async () => {
  if (!project.value) return;
  if (!window.confirm(`Delete "${project.value.name}" and all its scan history? This cannot be undone.`)) return;
  try {
    await deleteProject(props.id);
    router.push('/projects');
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    triggerError.value = 'Could not delete the project.';
  }
};

watch(running, (r) => { r ? startPolling() : stopPolling(); });
onMounted(load);
onUnmounted(stopPolling);

const print = () => window.print();
</script>

<template>
  <div v-if="loading" class="page">
    <div class="page-head"><div><h1 class="page-title">Project</h1></div></div>
    <!-- label stays outside the grid so the two columns start level -->
    <Skeleton label="loading_project" variant="label" />
    <div class="two-col" style="margin-bottom: 24px">
      <Skeleton variant="panel" :rows="6" />
      <Skeleton variant="panel" :rows="6" />
    </div>
    <Skeleton variant="table" :rows="4" />
  </div>

  <div v-else-if="error || !project" class="page">
    <div class="page-head"><div><h1 class="page-title">Project</h1></div></div>
    <div class="panel"><div class="panel-body" style="color: var(--sev-high)">{{ error || 'Project not found.' }}</div></div>
  </div>

  <div v-else class="page">
    <div class="page-head">
      <div>
        <div class="page-sub" style="margin-bottom: 8px">
          <a class="mono" style="color: var(--fg-2); cursor: pointer" @click="router.push('/projects')">← projects</a>
        </div>
        <div style="display: flex; align-items: center; gap: 12px">
          <h1 class="page-title rise-in" style="word-break: break-all">{{ project.name }}</h1>
          <Pill v-if="running" kind="accent" :dot="true">SCANNING</Pill>
        </div>
        <div class="page-sub" style="margin-top: 4px">
          <span class="mono">id: {{ project.id }}</span>
          <span style="color: var(--fg-3)"> · </span>
          <span class="mono">lang: {{ project.language || 'auto' }}</span>
          <span style="color: var(--fg-3)"> · </span>
          <span class="mono">created: {{ (project.created_at || '').slice(0, 10) }}</span>
        </div>
      </div>
      <div style="display: flex; gap: 8px" class="no-print">
        <button class="btn" @click="print"><Icon name="download" :size="14" /> Export PDF</button>
        <button class="btn" @click="router.push(`/project/${props.id}/edit`)"><Icon name="edit" :size="14" /> Edit</button>
        <button class="btn btn-danger" @click="purge"><Icon name="trash" :size="14" /> Purge</button>
      </div>
    </div>

    <div class="two-col" style="margin-bottom: 24px">
      <div class="panel rise-in" :style="{ animationDelay: '40ms' }">
        <div class="panel-head"><span class="panel-title">// project_intel</span></div>
        <div class="panel-body">
          <dl class="dlist">
            <dt>Source</dt>
            <dd>
              <span style="display: inline-flex; align-items: center; gap: 6px">
                <SourceIcon :type="project.source_type" />{{ project.source_type_display }}
              </span>
            </dd>
            <dt>Location</dt>
            <dd class="accent">{{ sourceTarget(project) }}</dd>
            <template v-if="project.source_type === 'git' && project.git_branch">
              <dt>Branch</dt><dd>{{ project.git_branch }}</dd>
            </template>
            <dt>Language</dt><dd><span class="pill">{{ project.language || 'auto-detect' }}</span></dd>
            <dt>Created</dt><dd>{{ fmtDateTime(project.created_at) }}</dd>
            <dt>Scans</dt><dd>{{ runs.length }} run{{ runs.length === 1 ? '' : 's' }}</dd>
          </dl>
        </div>
      </div>

      <div class="panel rise-in" :style="{ animationDelay: '80ms' }">
        <div class="panel-head">
          <span class="panel-title">// scan_console</span>
          <span class="kbd-hint mono" :title="auth.me?.is_staff ? `staff accounts aren't metered` : 'Scan credits remaining'">
            <Icon name="scan" :size="11" style="vertical-align: -1px; margin-right: 4px; color: var(--accent)" />{{ credits === Infinity ? '∞' : credits }} credits
          </span>
        </div>
        <div class="panel-body">
          <div class="scan-actions">
            <ScanActionCard tool="Semgrep" desc="Fast pattern-based static analysis." :cost="TOOL_COST.semgrep" :credits="credits" :running="runningTools.has('semgrep')" @run="trigger('semgrep')" />
            <ScanActionCard tool="SonarQube" desc="Deep code-quality and security analysis." :cost="TOOL_COST.sonarqube" :credits="credits" :running="runningTools.has('sonarqube')" @run="trigger('sonarqube')" />
            <ScanActionCard tool="Run both" desc="Both scanners in parallel. For releases and audits." :cost="TOOL_COST.both" :credits="credits" :primary="true" @run="trigger('both')" />
          </div>

          <div v-if="triggerError" class="notice notice-err" style="margin-top: 16px">
            <Icon name="alert" :size="14" />
            <span>{{ triggerError }}</span>
          </div>

          <div v-else-if="credits < TOOL_COST.both" class="notice notice-warn" style="margin-top: 16px">
            <Icon name="alert" :size="14" />
            <span>
              <strong>Low on credits.</strong>
              <template v-if="credits < 1"> You have no credits left. Scans are disabled until an admin tops you up.</template>
              <template v-else> Run both needs {{ TOOL_COST.both }}, you have {{ credits }}. Single scans still available.</template>
            </span>
          </div>

          <div v-if="running" class="notice notice-ok" style="margin-top: 16px">
            <span class="spinner" />
            <span>
              <strong>{{ runningScans.map(r => r.tool_display).join(' + ') }} running.</strong>
              This view polls every 3s and refreshes when {{ runningScans.length > 1 ? 'they finish' : 'it finishes' }}.
            </span>
            <span style="margin-left: auto; display: flex; gap: 12px">
              <a v-for="r in runningScans" :key="r.id" class="mono" style="color: var(--accent); cursor: pointer; white-space: nowrap" @click="router.push(`/scan/${r.id}`)">watch{{ runningScans.length > 1 ? ' ' + r.tool : '' }} →</a>
            </span>
          </div>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <span class="panel-title">// scan_history</span>
      </div>
      <div v-if="runs.length === 0" class="panel-body" style="text-align: center; padding: 40px">
        <Icon name="scan" :size="20" />
        <div class="mono" style="margin-top: 12px; color: var(--fg-2); font-size: var(--fs-sm)">
          No scans yet. Run one from the console above.
        </div>
      </div>
      <div v-else class="tbl-scroll">
      <table class="tbl hist-tbl">
        <thead>
          <tr>
            <th>Scan ID</th>
            <th class="col-tool">Tool</th>
            <th class="col-started">Started</th>
            <th class="col-dur">Duration</th>
            <th class="num col-count">Findings</th>
            <th class="col-status">Status</th>
            <th class="col-chev"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in runs" :key="s.id" @click="router.push(`/scan/${s.id}`)" style="cursor: pointer">
            <td><span class="cell-clip" style="color: var(--accent)" :title="s.id">{{ s.id }}</span></td>
            <td>{{ s.tool_display }}</td>
            <td class="dim">{{ fmtDateTime(s.started_at) }}</td>
            <td>{{ formatDuration(s.duration_seconds) }}</td>
            <td class="num mono">
              <span v-if="s.status === 'FAILED'" style="color: var(--sev-high)">-</span>
              <span v-else>{{ s.status === 'RUNNING' ? '-' : (s.finding_count == null ? '-' : s.finding_count) }}</span>
            </td>
            <td><StatusText :kind="scanStatusMeta(s.status).kind" :label="scanStatusMeta(s.status).label" /></td>
            <td><Icon name="chevronRight" :size="14" /></td>
          </tr>
        </tbody>
      </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Scan ID absorbs the leftover width and clamps; below the floor the
   wrapper scrolls sideways instead of wrapping cells into tall rows. */
.hist-tbl {
  table-layout: fixed;
  min-width: 760px;
}
.col-tool { width: 110px; }
.col-started { width: 150px; }
.col-dur { width: 90px; }
.col-count { width: 80px; }
.col-status { width: 110px; }
.col-chev { width: 36px; }
</style>
