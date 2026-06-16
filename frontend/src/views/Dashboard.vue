<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { fetchDashboard, fetchFindings, fetchScans, fetchHealth, redirectToLogin, UnauthorizedError } from '../api.js';
import { auth } from '../auth.js';
import { relativeTime, scanStatusMeta, owaspParse } from '../lib/format.js';
import Icon from '../components/Icon.vue';
import StatusText from '../components/StatusText.vue';
import Pill from '../components/Pill.vue';
import Bar from '../components/Bar.vue';
import ScanVolumeChart from '../components/ScanVolumeChart.vue';
import Skeleton from '../components/Skeleton.vue';

const router = useRouter();
const me = computed(() => auth.me || {});

const totals = ref({ projects: 0, scans: 0, scans_this_week: 0, open_findings: 0 });
const owasp_distribution = ref([]);
const recent_activity = ref([]);
const topFindings = ref([]);
const scans = ref([]);
const loading = ref(true);
const error = ref(null);
const health = ref(null);

// scan_engine header status. null = still probing ("..."); a failed
// probe also leaves it null rather than breaking the page.
const engineStatus = computed(() => {
  if (!health.value) return { kind: 'run', label: '...', title: null };
  const down = [];
  if (!health.value.semgrep) down.push('semgrep CLI not found');
  if (!health.value.sonarqube) down.push('sonarqube unreachable');
  if (down.length === 0) return { kind: 'ok', label: 'ONLINE', title: null };
  return { kind: 'err', label: 'DEGRADED', title: down.join(', ') };
});

// fresh=1: re-pings Sonar server-side (5s floor), so a recovered
// server shows ONLINE without waiting out the 60s cache.
const probeHealth = () => fetchHealth(true)
  .then((h) => { health.value = h; })
  .catch(() => { health.value = null; });

const load = async (silent = false) => {
  if (!silent) loading.value = true;
  error.value = null;
  try {
    // The dashboard endpoint returns KPIs but no finding rows; the
    // high-severity panel pulls its 4 from the cross-project endpoint
    // (server-side limit, not a full fetch), and the volume chart
    // derives its buckets from the scan list.
    const [dash, highs, allScans] = await Promise.all([
      fetchDashboard(),
      fetchFindings({ severity: 'HIGH', ordering: '-detected_at', limit: 4 }),
      fetchScans(),
    ]);
    totals.value = dash.totals;
    owasp_distribution.value = dash.owasp_distribution;
    recent_activity.value = dash.recent_activity;
    // limit param makes the findings endpoint return the paginated
    // envelope, not a plain array
    topFindings.value = highs.results;
    scans.value = allScans;
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    error.value = 'Failed to load the dashboard. Is the API up?';
  } finally {
    if (!silent) loading.value = false;
  }
  // Fire-and-forget AFTER the main load: the health probe pings the
  // tools server-side, so it must never block the dashboard render.
  // Skipped on silent polls to avoid hitting Sonar every 3s; failures
  // are swallowed so the header just keeps showing "...".
  if (!silent) probeHealth();
};

// Re-probe every 30s while mounted, its own interval separate from
// the 3s scan polling, so DEGRADED clears on its own when Sonar comes
// back without hammering the ping. Manual Refresh stays instant via
// load() → probeHealth().
let healthTimer = null;
onMounted(() => {
  load();
  healthTimer = setInterval(probeHealth, 30000);
});

// Keep the dashboard live while a scan runs; recent activity shows
// the RUNNING row and flips on completion. Silent refresh so the page
// doesn't flash its loading state every 3s.
const anyRunning = computed(() => scans.value.some(s => s.status === 'RUNNING'));
let pollTimer = null;
const stopPolling = () => { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } };
const startPolling = () => {
  if (pollTimer) return;
  pollTimer = setInterval(() => load(true), 3000);
};
watch(anyRunning, (r) => { r ? startPolling() : stopPolling(); });
onUnmounted(() => { stopPolling(); clearInterval(healthTimer); });

const owaspMax = computed(() => Math.max(...owasp_distribution.value.map(o => o.count), 1));
</script>

<template>
  <div v-if="loading" class="page">
    <div class="page-head"><div><h1 class="page-title">Dashboard</h1></div></div>
    <Skeleton label="loading_dashboard" variant="stat-cards" />
    <div class="two-col" style="grid-template-columns: 2fr 1fr; margin-bottom: 24px">
      <Skeleton variant="table" :rows="5" />
      <Skeleton variant="panel" :rows="5" />
    </div>
    <Skeleton variant="table" :rows="4" />
  </div>

  <div v-else-if="error" class="page">
    <div class="page-head"><div><h1 class="page-title">Dashboard</h1></div></div>
    <div class="panel"><div class="panel-body" style="color: var(--sev-high)">{{ error }}</div></div>
  </div>

  <div v-else class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title rise-in">Dashboard</h1>
        <div class="page-sub">
          <span class="mono">scan_engine:</span>
          <span :title="engineStatus.title">
            <StatusText :kind="engineStatus.kind" :label="engineStatus.label" />
          </span>
          <span class="mono" style="color: var(--fg-3)"> · </span>
          <span class="mono">workspace: {{ me.username }}</span>
        </div>
      </div>
      <div style="display: flex; gap: 8px">
        <button class="btn" @click="load()"><Icon name="refresh" :size="14" /> Refresh</button>
        <button class="btn btn-primary" @click="router.push('/projects/new')">
          <Icon name="plus" :size="14" /> New project
        </button>
      </div>
    </div>

    <div class="stat-row">
      <div class="stat rise-in" :style="{ animationDelay: '0ms' }">
        <div class="label">Projects</div>
        <div class="val">{{ totals.projects }}</div>
        <div class="delta">registered in workspace</div>
      </div>
      <div class="stat rise-in" :style="{ animationDelay: '40ms' }">
        <div class="label">Scans · total</div>
        <div class="val">{{ totals.scans }}</div>
        <div class="delta">{{ totals.scans_this_week }} this week</div>
      </div>
      <div class="stat rise-in" :style="{ animationDelay: '80ms' }">
        <div class="label">Open findings</div>
        <div class="val">{{ totals.open_findings }}</div>
        <div class="delta">directional · success scans</div>
      </div>
      <div class="stat rise-in" :style="{ animationDelay: '120ms' }">
        <div class="label">Scan credits</div>
        <div class="val">{{ (me.is_staff || me.credits < 0) ? '∞' : me.credits }}</div>
        <div class="delta">1 credit per scan</div>
      </div>
    </div>

    <div class="two-col" style="grid-template-columns: 2fr 1fr; margin-bottom: 24px">
      <div class="panel">
        <div class="panel-head">
          <span class="panel-title">// recent_activity</span>
          <a class="kbd-hint" style="cursor: pointer" @click="router.push('/scans')">View all →</a>
        </div>
        <table class="tbl">
          <thead>
            <tr>
              <th>Project</th>
              <th>Tool</th>
              <th>Started</th>
              <th class="num">Findings</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(s, idx) in recent_activity"
              :key="s.scan_id"
              class="rise-in"
              :style="{ animationDelay: (160 + idx * 40) + 'ms', cursor: 'pointer' }"
              @click="router.push(`/scan/${s.scan_id}`)"
            >
              <td><span class="cell-clip row-link" style="color: var(--accent)" :title="s.project_name" @click.stop="router.push(`/project/${s.project_id}`)">{{ s.project_name }}</span></td>
              <td>{{ s.tool_display }}</td>
              <td class="dim">{{ relativeTime(s.started_at) }}</td>
              <td class="num mono">{{ s.status === 'RUNNING' ? '-' : (s.finding_count == null ? '-' : s.finding_count) }}</td>
              <td><StatusText :kind="scanStatusMeta(s.status).kind" :label="scanStatusMeta(s.status).label" /></td>
            </tr>
            <tr v-if="recent_activity.length === 0">
              <td colspan="5" class="mono dim" style="text-align: center; padding: 20px">No scans yet.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="panel">
        <div class="panel-head">
          <span class="panel-title">// owasp_distribution</span>
          <span class="kbd-hint mono">top buckets</span>
        </div>
        <div class="panel-body" style="display: flex; flex-direction: column; gap: 12px">
          <div v-for="o in owasp_distribution" :key="o.category" class="col-stack" style="gap: 4px">
            <div class="row-between">
              <span class="mono" :style="{ fontSize: 'var(--fs-sm)', color: o.category === 'UNMAPPED' ? 'var(--fg-2)' : 'var(--fg)' }">
                <span v-if="o.category !== 'UNMAPPED'" style="color: var(--accent); margin-right: 8px">{{ owaspParse(o.category).code }}</span>
                {{ owaspParse(o.category).label }}
              </span>
              <span class="mono dim" style="font-size: var(--fs-xs)">{{ o.count }}</span>
            </div>
            <Bar :pct="(o.count / owaspMax) * 100" :kind="o.category === 'UNMAPPED' ? 'low' : 'accent'" />
          </div>
          <div v-if="owasp_distribution.length === 0" class="mono dim" style="padding: 8px 0">
            No findings mapped yet.
          </div>
        </div>
      </div>
    </div>

    <div class="panel" style="margin-bottom: 24px">
      <div class="panel-head">
        <span class="panel-title">// top_findings · high severity</span>
        <a class="kbd-hint" style="cursor: pointer" @click="router.push('/vulns')">View all findings →</a>
      </div>
      <div class="tbl-scroll">
      <table class="tbl top-findings-tbl">
        <thead>
          <tr>
            <th class="col-sev">Severity</th>
            <th>Finding</th>
            <th class="col-file">File</th>
            <th class="col-project">Project</th>
            <th class="col-when">Detected</th>
            <th class="col-chev"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in topFindings" :key="f.id" style="cursor: pointer" @click="router.push(`/scan/${f.scan_id}`)">
            <td><Pill kind="high">HIGH</Pill></td>
            <td>
              <span class="cell-clip" :title="f.message">{{ f.message }}</span>
            </td>
            <td>
              <span class="cell-clip dim" :title="`${f.file_path}:${f.line_number}`">{{ f.file_path }}<span style="color: var(--fg-3)">:{{ f.line_number }}</span></span>
            </td>
            <td><span class="cell-clip row-link" style="color: var(--accent)" :title="f.project_name" @click.stop="router.push(`/project/${f.project_id}`)">{{ f.project_name }}</span></td>
            <td class="dim" style="white-space: nowrap">{{ relativeTime(f.detected_at) }}</td>
            <td><Icon name="chevronRight" :size="14" /></td>
          </tr>
          <tr v-if="topFindings.length === 0">
            <td colspan="6" class="mono dim" style="text-align: center; padding: 20px">No high-severity findings open. Nice.</td>
          </tr>
        </tbody>
      </table>
      </div>
    </div>

    <ScanVolumeChart :scans="scans" />
  </div>
</template>

<style scoped>
/* Fixed layout so long messages/paths clamp instead of wrapping into
   tall rows; below the floor the wrapper scrolls sideways. */
.top-findings-tbl {
  table-layout: fixed;
  min-width: 860px;
}
.col-sev { width: 96px; }
.col-file { width: 30%; }
.col-project { width: 150px; }
.col-when { width: 100px; }
.col-chev { width: 36px; }
</style>
