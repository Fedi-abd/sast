<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import {
  fetchScan, fetchScanFindings, fetchScanReportBlob, triggerScan, solveFinding,
  redirectToLogin, UnauthorizedError, ApiError,
} from '../api.js';
import { auth } from '../auth.js';
import { fmtDateTime, formatDuration, scanStatusMeta, owaspParse } from '../lib/format.js';
import Icon from '../components/Icon.vue';
import StatusText from '../components/StatusText.vue';
import Bar from '../components/Bar.vue';
import SevRow from '../components/SevRow.vue';
import Finding from '../components/Finding.vue';
import Skeleton from '../components/Skeleton.vue';

const props = defineProps({ id: { type: String, default: '' } });
const router = useRouter();

// Real scans run into the thousands of findings; page the log instead
// of pulling the whole set into the DOM.
const PAGE = 25;

const scan = ref(null);
const results = ref([]);
const total = ref(0);
const visibleTotal = ref(0);
const solvedCount = ref(0);
const severityCounts = ref({});
const owaspCounts = ref([]);
const loading = ref(true);
const loadingMore = ref(false);
const exporting = ref(false);
const exportOpen = ref(false);
const exportScope = ref('all');
const exportError = ref(null);
const error = ref(null);
const actionError = ref(null);
const findingsError = ref(null);
const busy = ref(false);

const failed = computed(() => scan.value?.status === 'FAILED');
const running = computed(() => scan.value?.status === 'RUNNING');
const done = computed(() => scan.value?.status === 'SUCCESS');

const sevSet = ref([]);
const owaspSet = ref([]);
const openId = ref(null);

// Sonar splits findings across issue types. The burger is a hider:
// vulnerabilities always show, the other types start hidden, and the
// counts follow whatever is shown. null on Semgrep (no types).
const typeCounts = ref([]);
const selectedTypes = ref(null);
const typeMenuOpen = ref(false);
const typeMenuRef = ref(null);

const filterParams = () => ({
  severity: sevSet.value.length ? [...sevSet.value] : undefined,
  owasp: owaspSet.value.length ? [...owaspSet.value] : undefined,
  // Only Sonar findings have a type; sending it for Semgrep would match
  // nothing and blank the table.
  type: (scan.value?.tool === 'sonarqube' && selectedTypes.value && selectedTypes.value.length)
    ? [...selectedTypes.value] : undefined,
});

const applyEnvelope = (env) => {
  results.value = env.results || [];
  total.value = env.total || 0;
  visibleTotal.value = env.visible_total != null ? env.visible_total : (env.total || 0);
  solvedCount.value = env.solved_count || 0;
  severityCounts.value = env.severity_counts || {};
  owaspCounts.value = env.owasp_counts || [];
  typeCounts.value = env.type_counts || [];
  openId.value = null;
};

// Monotonic token: a chip toggled mid-flight invalidates older
// responses so they can't clobber (or append into) the newer view.
let findingsReq = 0;

const reloadFindings = async () => {
  const token = ++findingsReq;
  findingsError.value = null;
  try {
    const env = await fetchScanFindings(props.id, { ...filterParams(), limit: PAGE, offset: 0 });
    if (token === findingsReq) applyEnvelope(env);
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    if (token === findingsReq) findingsError.value = 'Failed to refresh findings. Try again.';
  }
};

const loadMore = async () => {
  if (loadingMore.value || results.value.length >= total.value) return;
  loadingMore.value = true;
  findingsError.value = null;
  const token = findingsReq;
  try {
    const env = await fetchScanFindings(props.id, {
      ...filterParams(), limit: PAGE, offset: results.value.length,
    });
    if (token === findingsReq) {
      results.value = [...results.value, ...(env.results || [])];
      total.value = env.total || total.value;
    }
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    if (token === findingsReq) findingsError.value = 'Could not load more findings. Try again.';
  } finally {
    loadingMore.value = false;
  }
};

// RUNNING scans report no incremental progress; poll the row every
// 3s and pull the first findings page once the status settles.
let pollTimer = null;
const stopPolling = () => { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } };
const startPolling = () => {
  if (pollTimer) return;
  pollTimer = setInterval(async () => {
    try {
      scan.value = await fetchScan(props.id);
    } catch { return; /* transient, keep last good row */ }
    if (!running.value) {
      stopPolling();
      reloadFindings();
    }
  }, 3000);
};

const load = async () => {
  loading.value = true;
  error.value = null;
  actionError.value = null;
  findingsError.value = null;
  sevSet.value = [];
  owaspSet.value = [];
  selectedTypes.value = null;
  typeMenuOpen.value = false;
  const token = ++findingsReq;
  try {
    // Default shows every type; the burger removes the ones you don't
    // want (include-all-then-remove). selectedTypes stays null = no filter.
    const [s, env] = await Promise.all([
      fetchScan(props.id),
      fetchScanFindings(props.id, { limit: PAGE, offset: 0 }),
    ]);
    if (token !== findingsReq) return;
    scan.value = s;
    applyEnvelope(env);
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    error.value = (e instanceof ApiError && e.status === 404)
      ? 'Scan not found.'
      : 'Failed to load the scan. Is the API up?';
  } finally {
    loading.value = false;
  }
};

const rerun = async () => {
  if (busy.value || !scan.value) return;
  busy.value = true;
  actionError.value = null;
  try {
    const resp = await triggerScan(scan.value.project_id, scan.value.tool);
    const fresh = resp.scans && resp.scans[0];
    if (fresh) {
      router.replace(`/scan/${fresh.id}`);
      await load();
    } else {
      // Tool already running on this project; watch it from the console.
      router.push(`/project/${scan.value.project_id}`);
    }
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    actionError.value = (e instanceof ApiError && e.status === 402)
      ? 'Not enough credits to re-run.'
      : 'Could not start the re-run. Try again.';
  } finally {
    busy.value = false;
  }
};

watch(running, (r) => { r ? startPolling() : stopPolling(); });
watch(() => props.id, load);
onMounted(load);
onUnmounted(stopPolling);

// Panels and chips read whole-scan counts from the envelope;
// stay stable no matter which filters or pages are loaded.
const tally = computed(() => ({
  HIGH: severityCounts.value.HIGH || 0,
  MEDIUM: severityCounts.value.MEDIUM || 0,
  LOW: severityCounts.value.LOW || 0,
}));

const owaspAgg = computed(() =>
  owaspCounts.value
    .map(({ category, count }) => ({ category, count, ...owaspParse(category) }))
    .sort((a, b) => b.count - a.count)
);
const owaspMax = computed(() => Math.max(...owaspAgg.value.map(o => o.count), 1));
// All buckets tied (common on small scans) => bars all render full-width and
// say nothing. Drop them and let the numbers speak.
const owaspAllEqual = computed(() => owaspAgg.value.length > 1 && owaspAgg.value.every(o => o.count === owaspAgg.value[0].count));

const inSev = (s) => sevSet.value.includes(s);
const inOwasp = (c) => owaspSet.value.includes(c);
const toggleSev = (s) => {
  sevSet.value = inSev(s) ? sevSet.value.filter(x => x !== s) : [...sevSet.value, s];
  reloadFindings();
};
const toggleOwasp = (c) => {
  owaspSet.value = inOwasp(c) ? owaspSet.value.filter(x => x !== c) : [...owaspSet.value, c];
  reloadFindings();
};
const clearFilters = () => { sevSet.value = []; owaspSet.value = []; reloadFindings(); };
const filtersActive = computed(() => sevSet.value.length + owaspSet.value.length > 0);

// Type burger (Sonar only): a hider over the visible types. Everything
// shows by default (null = no filter); unchecking a type removes it.
// Vulnerabilities can't be removed. Only worth showing when there's
// more than one type to act on.
const showTypeMenu = computed(() => scan.value?.tool === 'sonarqube' && typeCounts.value.length > 1);
const typeSelected = (t) => !selectedTypes.value || selectedTypes.value.includes(t);
const activeTypeCount = computed(() => selectedTypes.value ? selectedTypes.value.length : typeCounts.value.length);
const toggleType = (t) => {
  if (t === 'VULNERABILITY') return;   // always shown, not hideable
  const all = typeCounts.value.map((x) => x.type);
  const base = selectedTypes.value ? [...selectedTypes.value] : [...all];
  const next = base.includes(t) ? base.filter((x) => x !== t) : [...base, t];
  // Back to everything selected => clear the filter so counts cover all.
  selectedTypes.value = next.length >= all.length ? null : next;
  reloadFindings();
};
const onTypeMenuClick = (e) => {
  if (typeMenuRef.value && !typeMenuRef.value.contains(e.target)) typeMenuOpen.value = false;
};
watch(typeMenuOpen, (open) => {
  if (open) document.addEventListener('click', onTypeMenuClick);
  else document.removeEventListener('click', onTypeMenuClick);
});
onUnmounted(() => document.removeEventListener('click', onTypeMenuClick));

const onSolve = async (f) => {
  findingsError.value = null;
  try {
    await solveFinding(f.id, true);
    // Drop it in place so the loaded rows and scroll survive; the
    // counters move with it. The rollups don't change on solve.
    if (openId.value === f.id) openId.value = null;
    results.value = results.value.filter((r) => r.id !== f.id);
    total.value = Math.max(0, total.value - 1);
    solvedCount.value += 1;
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    findingsError.value = 'Could not mark that finding solved. Try again.';
  }
};

const remaining = computed(() => Math.max(0, total.value - results.value.length));
const nextChunk = computed(() => Math.min(PAGE, remaining.value));

const st = computed(() => scan.value ? scanStatusMeta(scan.value.status) : { kind: 'run', label: '-' });
const generatedAt = computed(() => new Date().toISOString().replace('T', ' ').slice(0, 16));

const triggerDownload = (blob, filename) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
};

// Severity scope -> which findings the PDF covers. null means all.
const SCOPES = { all: null, highmed: ['HIGH', 'MEDIUM'], high: ['HIGH'] };
const doExport = async () => {
  if (exporting.value) return;
  exporting.value = true;
  exportError.value = null;
  try {
    const blob = await fetchScanReportBlob(scan.value.id, SCOPES[exportScope.value]);
    triggerDownload(blob, `sast-scan-${scan.value.id}.pdf`);
    exportOpen.value = false;
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    exportError.value = 'Could not generate the PDF. Try again.';
  } finally {
    exporting.value = false;
  }
};

const closeExport = () => { exportOpen.value = false; };
const onExportKey = (e) => { if (e.key === 'Escape' && !exporting.value) closeExport(); };
watch(exportOpen, (open) => {
  if (open) { exportError.value = null; document.addEventListener('keydown', onExportKey); }
  else document.removeEventListener('keydown', onExportKey);
});
onUnmounted(() => document.removeEventListener('keydown', onExportKey));
</script>

<template>
  <div v-if="loading" class="page">
    <div class="page-head"><div><h1 class="page-title">Scan results</h1></div></div>
    <Skeleton label="loading_scan" variant="stat-cards" />
    <div class="two-col-equal" style="margin-bottom: 24px; grid-template-columns: 1fr 1fr">
      <Skeleton variant="panel" :rows="4" />
      <Skeleton variant="panel" :rows="4" />
    </div>
    <Skeleton variant="table" :rows="6" />
  </div>

  <div v-else-if="error || !scan" class="page">
    <div class="page-head"><div><h1 class="page-title">Scan results</h1></div></div>
    <div class="panel"><div class="panel-body" style="color: var(--sev-high)">{{ error || 'Scan not found.' }}</div></div>
  </div>

  <div v-else class="page">
    <div class="page-head">
      <div>
        <div class="page-sub" style="margin-bottom: 8px">
          <a class="mono" style="color: var(--fg-2); cursor: pointer" @click="router.push(`/project/${scan.project_id}`)">← {{ scan.project_name }}</a>
        </div>
        <h1 class="page-title rise-in">Scan results</h1>
        <div class="page-sub" style="margin-top: 4px">
          <span class="mono">id: {{ scan.id }}</span>
          <span style="color: var(--fg-3)"> · </span>
          <span class="mono">tool: {{ scan.tool_display }}</span>
          <span style="color: var(--fg-3)"> · </span>
          <span class="mono">started: {{ fmtDateTime(scan.started_at) }}</span>
          <span style="color: var(--fg-3)"> · </span>
          <StatusText :kind="st.kind" :label="st.label" />
        </div>
      </div>
      <div style="display: flex; gap: 8px" class="no-print">
        <button v-if="done" class="btn" @click="exportOpen = true"><Icon name="download" :size="14" /> Export</button>
        <button class="btn" :disabled="busy || running" @click="rerun"><Icon name="refresh" :size="14" /> Re-run</button>
      </div>
    </div>

    <div v-if="exportOpen" class="export-overlay no-print" @click.self="closeExport">
      <div class="panel export-modal">
        <div class="panel-head"><span class="panel-title">// export_pdf</span></div>
        <div class="panel-body">
          <p class="mono dim" style="margin: 0 0 12px; font-size: var(--fs-xs)">Scope the report by severity.</p>
          <div class="export-formats">
            <label class="export-opt" :class="{ active: exportScope === 'all' }">
              <input type="radio" value="all" v-model="exportScope" :disabled="exporting" />
              <span class="opt-title">Full report</span>
              <span class="opt-sub">Every finding. Cover, synthèse, OWASP, full table, appendix.</span>
            </label>
            <label class="export-opt" :class="{ active: exportScope === 'highmed' }">
              <input type="radio" value="highmed" v-model="exportScope" :disabled="exporting" />
              <span class="opt-title">High + Medium</span>
              <span class="opt-sub">Drops LOW findings for a tighter report.</span>
            </label>
            <label class="export-opt" :class="{ active: exportScope === 'high' }">
              <input type="radio" value="high" v-model="exportScope" :disabled="exporting" />
              <span class="opt-title">High only</span>
              <span class="opt-sub">A short executive summary of the critical findings.</span>
            </label>
          </div>

          <div v-if="exportError" class="notice notice-err" style="margin-top: 14px">
            <Icon name="alert" :size="14" />
            <span>{{ exportError }}</span>
          </div>

          <div class="export-actions">
            <button class="btn" :disabled="exporting" @click="closeExport">Cancel</button>
            <button class="btn btn-primary" :disabled="exporting" @click="doExport">
              <Icon name="download" :size="14" />
              {{ exporting ? 'Generating…' : 'Download PDF' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="actionError" class="notice notice-err" style="margin-bottom: 24px">
      <Icon name="alert" :size="14" />
      <span>{{ actionError }}</span>
    </div>

    <div class="print-header print-only">
      <div>
        <div class="h">SAST · Forensic brief</div>
        <div style="font-family: var(--font-mono); font-size: 11px; color: #444; margin-top: 4px">
          {{ scan.project_name }} · {{ scan.tool_display }} · {{ scan.id }}
        </div>
      </div>
      <div class="meta">generated: {{ generatedAt }}<br />status: {{ scan.status }}</div>
    </div>

    <!-- FAILED scans never persist findings -->
    <div v-if="failed" class="notice notice-err failed-notice" style="margin-bottom: 24px">
      <div class="failed-head">
        <Icon name="alert" :size="16" />
        <strong>Scan failed. No findings recorded.</strong>
        <button class="btn btn-sm failed-rerun" :disabled="busy" @click="rerun"><Icon name="refresh" :size="12" /> Re-run scan</button>
      </div>
      <!-- The raw dump is an operator's debugging lens; users get a
           clean line and the audit trail lives in the admin usage log. -->
      <pre v-if="auth.me?.is_staff && scan.error_message" class="failed-dump mono">{{ scan.error_message }}</pre>
      <div class="failed-hint mono">// {{ auth.me?.is_staff ? 'full error shown to staff only; users see this line' : 'contact your administrator for details' }}</div>
    </div>

    <!-- RUNNING is indeterminate: no progress %, no stats, no findings.
         Static analysers don't stream progress. -->
    <div v-else-if="running" class="panel" role="status" aria-live="polite">
      <div class="panel-body" style="padding: 64px 32px; display: flex; flex-direction: column; align-items: center; text-align: center; gap: 18px">
        <span class="spinner-lg" />
        <div>
          <div style="font-size: var(--fs-lg); font-weight: 600; margin-bottom: 6px">Scan in progress</div>
          <div class="mono" style="font-size: var(--fs-sm); color: var(--fg-2)">
            {{ scan.tool_display }} is analyzing <span class="row-link" style="color: var(--accent)" :title="'Open ' + scan.project_name" @click="router.push(`/project/${scan.project_id}`)">{{ scan.project_name }}</span> · scanning…
          </div>
        </div>
        <div class="mono" style="font-size: var(--fs-xs); color: var(--fg-3); max-width: 440px; line-height: 1.7">
          No incremental progress is reported. The full result set appears here the moment the run completes. This view polls every 3s.
        </div>
      </div>
    </div>

    <template v-else>
      <div class="stat-row">
        <div class="stat rise-in" :style="{ animationDelay: '0ms' }">
          <div class="label">Findings</div>
          <div class="val">{{ visibleTotal }}</div>
          <div class="delta">{{ results.length }} shown<template v-if="solvedCount"> · {{ solvedCount }} solved</template></div>
        </div>
        <div class="stat rise-in" :style="{ animationDelay: '40ms' }">
          <div class="label">High severity</div>
          <div class="val high">{{ tally.HIGH }}</div>
          <div class="delta">need triage first</div>
        </div>
        <div class="stat rise-in" :style="{ animationDelay: '80ms' }">
          <div class="label">Duration</div>
          <div class="val">{{ formatDuration(scan.duration_seconds) }}</div>
          <div class="delta">wall-clock</div>
        </div>
        <div class="stat rise-in" :style="{ animationDelay: '120ms' }">
          <div class="label">Tool</div>
          <div class="val" style="font-size: var(--fs-2xl)">{{ scan.tool_display }}</div>
          <div class="delta">engine</div>
        </div>
      </div>

      <div class="two-col-equal" style="margin-bottom: 24px; grid-template-columns: 1fr 1fr">
        <div class="panel">
          <div class="panel-head"><span class="panel-title">// severity_breakdown</span></div>
          <div class="panel-body" style="display: flex; flex-direction: column; gap: 16px">
            <SevRow label="HIGH"   :value="tally.HIGH"   :total="visibleTotal" kind="high" />
            <SevRow label="MEDIUM" :value="tally.MEDIUM" :total="visibleTotal" kind="med" />
            <SevRow label="LOW"    :value="tally.LOW"    :total="visibleTotal" kind="low" />
            <div class="divider-dashed" style="margin: 0" />
            <div class="mono" style="font-size: var(--fs-xs); color: var(--fg-2); line-height: 1.6">
              Severity split covers the open findings in the shown types, not just the rows loaded in the log below.
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-head">
            <span class="panel-title">// owasp_distribution</span>
            <span class="kbd-hint mono">click to filter</span>
          </div>
          <div class="panel-body" style="padding: 0">
            <table class="tbl">
              <tbody>
                <tr
                  v-for="o in owaspAgg"
                  :key="o.category"
                  :title="`Filter findings to ${o.code === '-' ? 'UNMAPPED' : o.code}`"
                  :style="{ cursor: 'pointer', background: inOwasp(o.category) ? 'var(--accent-soft)' : '' }"
                  @click="toggleOwasp(o.category)"
                >
                  <td :style="{ width: '52px', color: o.code === '-' ? 'var(--fg-3)' : 'var(--accent)' }">{{ o.code }}</td>
                  <td>{{ o.label }}</td>
                  <td style="width: 120px">
                    <span v-if="owaspAllEqual" class="mono" style="font-size: var(--fs-xs); color: var(--fg-3)">even</span>
                    <Bar v-else :pct="(o.count / owaspMax) * 100" :kind="o.count >= 2 ? 'med' : 'low'" />
                  </td>
                  <td class="num mono" style="width: 40px; color: var(--fg-1)">{{ o.count }}</td>
                </tr>
                <tr v-if="owaspAgg.length === 0">
                  <td class="mono dim" style="padding: 16px">No findings to distribute.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-head">
          <span class="panel-title">// findings_log</span>
          <span class="kbd-hint mono"><template v-if="solvedCount">{{ solvedCount }}/{{ visibleTotal }} solved · </template>showing {{ results.length }} of {{ total }}</span>
        </div>
        <div v-if="scan.finding_count > 0" class="filter-bar no-print">
          <div class="filter-bar-row">
            <span class="filter-label">severity</span>
            <button
              v-for="row in [
                { sev: 'HIGH',   cls: 'chip-sev-high', n: tally.HIGH },
                { sev: 'MEDIUM', cls: 'chip-sev-med',  n: tally.MEDIUM },
                { sev: 'LOW',    cls: 'chip-sev-low',  n: tally.LOW },
              ]"
              :key="row.sev"
              :class="['chip', row.cls, inSev(row.sev) ? 'active' : '']"
              :aria-pressed="inSev(row.sev)"
              :disabled="row.n === 0"
              @click="toggleSev(row.sev)"
            >
              {{ row.sev }}<span class="chip-count">{{ row.n }}</span>
            </button>
          </div>
          <div v-if="owaspAgg.length > 0" class="filter-bar-row">
            <span class="filter-label">owasp</span>
            <button
              v-for="o in owaspAgg"
              :key="o.category"
              :class="['chip', inOwasp(o.category) ? 'active' : '']"
              :aria-pressed="inOwasp(o.category)"
              :title="o.label || o.code"
              @click="toggleOwasp(o.category)"
            >
              {{ o.code === '-' ? 'UNMAPPED' : o.code }}<span class="chip-count">{{ o.count }}</span>
            </button>
            <a v-if="filtersActive" class="filter-clear" role="button" @click="clearFilters">✕ clear</a>
          </div>
          <div v-if="showTypeMenu" class="filter-bar-row">
            <span class="filter-label">type</span>
            <div class="type-menu" ref="typeMenuRef">
              <button
                class="chip type-burger"
                :class="{ active: typeMenuOpen }"
                :aria-expanded="typeMenuOpen"
                @click="typeMenuOpen = !typeMenuOpen"
              >☰ types<span class="chip-count">{{ activeTypeCount }}/{{ typeCounts.length }}</span></button>
              <div v-if="typeMenuOpen" class="type-menu-panel">
                <label v-for="t in typeCounts" :key="t.type" class="type-opt">
                  <input type="checkbox" :checked="typeSelected(t.type)" :disabled="t.type === 'VULNERABILITY'" @change="toggleType(t.type)" />
                  <span class="mono">{{ t.type }}</span>
                  <span class="type-opt-count mono">{{ t.count }}</span>
                </label>
                <div class="type-menu-note mono">// all shown by default; uncheck to hide (vulnerabilities stay)</div>
              </div>
            </div>
          </div>
        </div>
        <div class="panel-body">
          <div v-if="findingsError" class="mono" style="font-size: var(--fs-sm); color: var(--sev-high); padding-bottom: 10px">{{ findingsError }}</div>
          <Finding
            v-for="f in results"
            :key="f.id"
            :f="f"
            :open="openId === f.id"
            @toggle="openId = openId === f.id ? null : f.id"
            @solve="onSolve"
          />
          <div v-if="results.length === 0" class="mono dim" style="padding: 20px; text-align: center">
            {{ filtersActive ? 'No findings match these filters.' : 'No findings recorded.' }}
          </div>
          <div v-if="results.length < total" class="load-more-row no-print">
            <button class="btn mono load-more-btn" :disabled="loadingMore" @click="loadMore">
              {{ loadingMore ? 'loading…' : `load ${nextChunk} more · ${remaining} remaining` }}
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.export-overlay {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(2px);
}
.export-modal {
  width: min(460px, calc(100vw - 48px));
}
.export-formats {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.export-opt {
  display: grid;
  grid-template-columns: auto 1fr;
  column-gap: 10px;
  align-items: baseline;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: var(--r-2);
  cursor: pointer;
}
.export-opt.active {
  border-color: var(--accent);
  background: var(--bg-inset);
}
.export-opt input {
  grid-row: span 2;
  align-self: center;
}
.export-opt .opt-title { font-weight: 600; }
.export-opt .opt-sub {
  grid-column: 2;
  font-size: var(--fs-xs);
  color: var(--fg-2);
}
.export-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 18px;
}

/* Failed notice: column layout so a long error dump can't flex-crush
   the Re-run button sitting next to it. */
.failed-notice {
  flex-direction: column;
  align-items: stretch;
  gap: 10px;
}
.failed-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.failed-rerun {
  margin-left: auto;
  flex-shrink: 0;
}
.failed-dump {
  margin: 0;
  width: 100%;
  font-size: var(--fs-xs);
  background: var(--bg-inset);
  border: 1px solid var(--line);
  border-radius: var(--r-2);
  padding: 10px 12px;
  max-height: 180px;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.failed-hint {
  font-size: var(--fs-xs);
  color: var(--fg-3);
}

.load-more-row {
  display: flex;
  justify-content: center;
  padding: 14px 0 4px;
}
.load-more-btn {
  font-size: var(--fs-sm);
}

.type-menu { position: relative; display: inline-block; }
.type-burger { cursor: pointer; }
.type-menu-panel {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 40;
  min-width: 230px;
  padding: 8px;
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: var(--r-2);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.type-opt {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: var(--r-2);
  cursor: pointer;
  font-size: var(--fs-sm);
}
.type-opt:hover { background: var(--bg-inset); }
.type-opt-count { margin-left: auto; color: var(--fg-3); font-size: var(--fs-xs); }
.type-menu-note {
  margin-top: 4px;
  padding: 6px 8px 2px;
  font-size: var(--fs-xs);
  color: var(--fg-3);
  border-top: 1px solid var(--line);
}
</style>
