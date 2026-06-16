<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { fetchFindings, redirectToLogin, UnauthorizedError } from '../api.js';
import { relativeTime, severityLabel, owaspParse } from '../lib/format.js';
import Icon from '../components/Icon.vue';
import Pill from '../components/Pill.vue';
import Skeleton from '../components/Skeleton.vue';

const router = useRouter();

const PAGE = 25;

const rows = ref([]);
const total = ref(0);
const sevCounts = ref({ HIGH: 0, MEDIUM: 0, LOW: 0 });
const owaspCounts = ref([]);
const loading = ref(true);
const error = ref(null);
const fetchError = ref(null);
const fetching = ref(false);
const busy = ref(false);

const sevSet = ref([]);
const owaspSet = ref([]);
const ordering = ref('-detected_at');

const queryParams = (offset) => ({
  severity: sevSet.value.length ? sevSet.value : undefined,
  owasp: owaspSet.value.length ? owaspSet.value : undefined,
  ordering: ordering.value,
  limit: PAGE,
  offset,
});

// Rapid chip clicks overlap requests; latest-wins, stale responses dropped.
let reqSeq = 0;

const refetch = async () => {
  const seq = ++reqSeq;
  fetching.value = true;
  fetchError.value = null;
  try {
    const env = await fetchFindings(queryParams(0));
    if (seq !== reqSeq) return;
    rows.value = env.results;
    total.value = env.total;
    sevCounts.value = env.severity_counts;
    owaspCounts.value = env.owasp_counts;
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    if (seq === reqSeq) fetchError.value = 'Failed to load findings. Is the API up?';
  } finally {
    if (seq === reqSeq) fetching.value = false;
  }
};

onMounted(async () => {
  await refetch();
  // First load failing means there's nothing to show; promote to page error.
  if (fetchError.value) { error.value = fetchError.value; fetchError.value = null; }
  loading.value = false;
});

// Filters and ordering are server-side now; any change restarts from offset 0.
watch([sevSet, owaspSet, ordering], refetch);

const inSev = (s) => sevSet.value.includes(s);
const inOwasp = (c) => owaspSet.value.includes(c);
const toggleSev = (s) => { sevSet.value = inSev(s) ? sevSet.value.filter(x => x !== s) : [...sevSet.value, s]; };
const toggleOwasp = (c) => { owaspSet.value = inOwasp(c) ? owaspSet.value.filter(x => x !== c) : [...owaspSet.value, c]; };
const clearFilters = () => { sevSet.value = []; owaspSet.value = []; };
const filtersActive = computed(() => sevSet.value.length + owaspSet.value.length > 0);

// Chip counts come from the envelope and cover the whole unfiltered set.
const owaspChips = computed(() =>
  owaspCounts.value
    .map((o) => ({ cat: o.category, count: o.count, ...owaspParse(o.category) }))
    .sort((a, b) => b.count - a.count)
);

const remaining = computed(() => Math.max(total.value - rows.value.length, 0));

const loadMore = async () => {
  if (busy.value || fetching.value || remaining.value === 0) return;
  busy.value = true;
  const seq = ++reqSeq;
  fetchError.value = null;
  try {
    const env = await fetchFindings(queryParams(rows.value.length));
    if (seq === reqSeq) {
      rows.value = rows.value.concat(env.results);
      total.value = env.total;
    }
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    if (seq === reqSeq) fetchError.value = 'Could not load more findings. Try again.';
  } finally {
    busy.value = false;
  }
};

// CSV covers the loaded rows only; what you see is what you export.
const exportCsv = () => {
  const head = ['severity', 'message', 'file_path', 'line_number', 'cwe_id', 'owasp_category', 'project_name', 'detected_at', 'tool', 'rule_id'];
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const lines = [head.join(',')].concat(rows.value.map(f => head.map(k => esc(f[k])).join(',')));
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'findings.csv';
  a.click();
  URL.revokeObjectURL(a.href);
};
</script>

<template>
  <div v-if="loading" class="page">
    <div class="page-head"><div><h1 class="page-title">All findings</h1></div></div>
    <Skeleton label="loading_findings" variant="chips" :count="6" />
    <Skeleton variant="table" :rows="8" />
  </div>

  <div v-else-if="error" class="page">
    <div class="page-head"><div><h1 class="page-title">All findings</h1></div></div>
    <div class="panel"><div class="panel-body" style="color: var(--sev-high)">{{ error }}</div></div>
  </div>

  <div v-else class="page">
    <div class="page-head">
      <div>
        <div class="page-sub" style="margin-bottom: 8px">
          <a class="mono" style="color: var(--fg-2); cursor: pointer" @click="router.push('/dashboard')">← dashboard</a>
        </div>
        <h1 class="page-title rise-in">All findings</h1>
        <div class="page-sub">
          <span class="mono">cross-project · {{ total }} from success scans · showing {{ rows.length }}</span>
        </div>
      </div>
      <button class="btn" :disabled="rows.length === 0" title="exports the currently loaded rows" @click="exportCsv"><Icon name="download" :size="14" /> Export CSV</button>
    </div>

    <div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 20px">
      <div class="filter-bar-row">
        <span class="filter-label">severity</span>
        <button
          v-for="row in [
            { sev: 'HIGH',   cls: 'chip-sev-high', n: sevCounts.HIGH },
            { sev: 'MEDIUM', cls: 'chip-sev-med',  n: sevCounts.MEDIUM },
            { sev: 'LOW',    cls: 'chip-sev-low',  n: sevCounts.LOW },
          ]"
          :key="row.sev"
          :class="['chip', row.cls, inSev(row.sev) ? 'active' : '']"
          :aria-pressed="inSev(row.sev)"
          :disabled="row.n === 0"
          @click="toggleSev(row.sev)"
        >
          {{ row.sev }}<span class="chip-count">{{ row.n }}</span>
        </button>
        <span style="margin-left: auto; display: flex; align-items: center; gap: 6px; flex-wrap: wrap">
          <span class="filter-label" style="min-width: auto">order</span>
          <button
            v-for="o in [['-detected_at', 'NEWEST'], ['-severity', 'SEVERITY'], ['project', 'PROJECT']]"
            :key="o[0]"
            :class="['chip', ordering === o[0] ? 'active' : '']"
            @click="ordering = o[0]"
          >
            {{ o[1] }}
          </button>
        </span>
      </div>
      <div class="filter-bar-row">
        <span class="filter-label">owasp</span>
        <button
          v-for="o in owaspChips"
          :key="o.cat"
          :class="['chip', inOwasp(o.cat) ? 'active' : '']"
          :aria-pressed="inOwasp(o.cat)"
          :title="o.label || o.code"
          @click="toggleOwasp(o.cat)"
        >
          {{ o.code === '-' ? 'UNMAPPED' : o.code }}<span class="chip-count">{{ o.count }}</span>
        </button>
        <a v-if="filtersActive" class="filter-clear" role="button" @click="clearFilters">✕ clear</a>
      </div>
    </div>

    <div v-if="fetchError" class="notice notice-err" style="margin-bottom: 16px">
      <Icon name="alert" :size="14" />
      <span>{{ fetchError }}</span>
    </div>

    <div class="panel">
      <div class="tbl-scroll">
        <table class="tbl findings-tbl">
          <thead>
            <tr>
              <th class="col-sev">Severity</th>
              <th>Finding</th>
              <th class="col-file">File</th>
              <th class="col-cwe">CWE</th>
              <th class="col-project">Project</th>
              <th class="col-when">Detected</th>
              <th class="col-go"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in rows" :key="f.id" @click="router.push(`/scan/${f.scan_id}`)" style="cursor: pointer">
              <td><Pill :kind="severityLabel(f.severity)">{{ f.severity }}</Pill></td>
              <td>
                <span class="cell-clip" :title="f.message">{{ f.message }}</span>
              </td>
              <td>
                <span class="cell-clip dim" :title="`${f.file_path}:${f.line_number}`">{{ f.file_path }}<span style="color: var(--fg-3)">:{{ f.line_number }}</span></span>
              </td>
              <td><span class="cell-clip dim" :title="f.cwe_id || undefined">{{ f.cwe_id || '-' }}</span></td>
              <td><span class="cell-clip row-link" style="color: var(--accent)" :title="f.project_name" @click.stop="router.push(`/project/${f.project_id}`)">{{ f.project_name }}</span></td>
              <td class="dim" style="white-space: nowrap">{{ relativeTime(f.detected_at) }}</td>
              <td><Icon name="chevronRight" :size="14" /></td>
            </tr>
            <tr v-if="rows.length === 0">
              <td colspan="7" class="mono dim" style="text-align: center; padding: 24px">
                {{ filtersActive ? 'No findings match these filters.' : 'No findings yet. Run a scan first.' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="remaining > 0" class="load-more-row">
      <button class="btn mono" :disabled="busy || fetching" @click="loadMore">
        {{ busy ? 'loading…' : `load ${Math.min(PAGE, remaining)} more · ${remaining} remaining` }}
      </button>
    </div>
  </div>
</template>

<style scoped>
/* .tbl-scroll and .cell-clip are global helpers in styles.css.
   Fixed layout: sized columns hold their width, Finding absorbs the
   leftover; auto layout was handing the slack to whichever cell wrapped. */
.findings-tbl {
  table-layout: fixed;
  min-width: 920px;
}
.col-sev { width: 106px; }
.col-file { width: 22%; }
.col-cwe { width: 180px; }
.col-project { width: 140px; }
.col-when { width: 110px; }
.col-go { width: 36px; }

.load-more-row {
  display: flex;
  justify-content: center;
  padding: 14px 0 4px;
}
</style>
