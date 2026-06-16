<script setup>
import { ref, computed, onMounted } from 'vue';
import { fetchAdminUsage, redirectToLogin, UnauthorizedError } from '../../api.js';
import { scanStatusMeta, formatDuration, relativeTime, fmtDateTime } from '../../lib/format.js';
import Icon from '../Icon.vue';
import StatusText from '../StatusText.vue';
import Loading from '../Loading.vue';

const usage = ref([]);
const loading = ref(true);
const error = ref(null);

onMounted(async () => {
  try {
    // Server default limit (50); the console shows a page, not the full history.
    usage.value = await fetchAdminUsage();
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    error.value = 'Failed to load usage log. Is the API up?';
  } finally {
    loading.value = false;
  }
});

const desc = ref(true);
const statusFilter = ref('all');
const FILTERS = [['all', 'ALL'], ['SUCCESS', 'SUCCESS'], ['RUNNING', 'RUNNING'], ['FAILED', 'FAILED']];

// One expanded row at a time; this is a debugging lens, not a tree view.
const openId = ref(null);
function toggleRow(id) {
  openId.value = openId.value === id ? null : id;
}

const rows = computed(() => {
  let a = usage.value.filter((r) => (statusFilter.value === 'all' ? true : r.status === statusFilter.value));
  a = [...a].sort((x, y) => (new Date(y.started_at) - new Date(x.started_at)) * (desc.value ? 1 : -1));
  return a;
});
</script>

<template>
  <Loading v-if="loading" label="loading_usage_log" />

  <div v-else-if="error" class="panel rise-in">
    <div class="panel-body" style="color: var(--sev-high)">{{ error }}</div>
  </div>

  <div v-else class="panel rise-in">
    <div class="panel-head">
      <span class="panel-title">// usage_log · all users</span>
      <div style="display: flex; gap: 6px">
        <button v-for="[k, lbl] in FILTERS" :key="k" :class="['chip', statusFilter === k ? 'active' : '']" @click="statusFilter = k">{{ lbl }}</button>
      </div>
    </div>
    <table class="tbl">
      <thead>
        <tr>
          <th>User</th>
          <th>Project</th>
          <th>Tool</th>
          <th>Status</th>
          <th>Duration</th>
          <th class="num">Findings</th>
          <th>
            <span :class="['th-sort', desc ? '' : 'asc']" role="button" @click="desc = !desc">
              When <Icon name="chevronDown" :size="11" class="caret" />
            </span>
          </th>
        </tr>
      </thead>
      <tbody>
        <template v-for="r in rows" :key="r.id">
          <tr class="usage-row" :title="'click for details'" @click="toggleRow(r.id)">
            <td><span style="color: var(--fg)">{{ r.username }}</span></td>
            <td class="dim">{{ r.project_name }}</td>
            <td>{{ r.tool_display }}</td>
            <td>
              <span v-if="r.status === 'RUNNING'" class="row-flex" style="gap: 6px">
                <span class="spinner" /><StatusText :kind="scanStatusMeta(r.status).kind" :label="scanStatusMeta(r.status).label" />
              </span>
              <StatusText v-else :kind="scanStatusMeta(r.status).kind" :label="scanStatusMeta(r.status).label" />
            </td>
            <td>{{ formatDuration(r.duration_seconds) }}</td>
            <td class="num mono">
              <span v-if="r.status === 'FAILED'" style="color: var(--sev-high)">-</span>
              <!-- finding_count is a COUNT annotation (0 while RUNNING, never null) -->
              <template v-else>{{ r.status === 'RUNNING' ? '-' : r.finding_count }}</template>
            </td>
            <td class="dim" :title="fmtDateTime(r.started_at)">{{ relativeTime(r.started_at) }}</td>
          </tr>
          <!-- .stop so selecting/copying error text never re-toggles the row -->
          <tr v-if="openId === r.id" class="usage-detail" @click.stop>
            <td colspan="7">
              <div class="detail-meta mono">
                <span><span class="dim">scan_id</span> {{ r.id }}</span>
                <span><span class="dim">started</span> {{ fmtDateTime(r.started_at) }}</span>
                <span><span class="dim">duration</span> {{ formatDuration(r.duration_seconds) }}</span>
                <span><span class="dim">findings</span> {{ r.finding_count }}</span>
              </div>
              <pre v-if="r.error_message" class="error-block mono">{{ r.error_message }}</pre>
              <div v-else class="no-errors mono dim">// no errors recorded</div>
            </td>
          </tr>
        </template>
        <tr v-if="rows.length === 0">
          <td colspan="7" class="mono dim" style="text-align: center; padding: 20px">No scans match this filter.</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.usage-row {
  cursor: pointer;
}
.usage-detail td {
  padding-top: 4px;
  padding-bottom: 12px;
}
.detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 24px;
  font-size: var(--fs-xs);
}
.error-block {
  margin: 8px 0 0;
  font-size: var(--fs-xs);
  background: var(--bg-inset);
  border: 1px solid var(--line);
  border-radius: var(--r-2);
  padding: 10px 12px;
  max-height: 160px;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.no-errors {
  margin-top: 8px;
  font-size: var(--fs-xs);
}
</style>
