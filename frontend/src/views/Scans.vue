<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { fetchScans, redirectToLogin, UnauthorizedError } from '../api.js';
import { fmtDateTime, formatDuration, scanStatusMeta } from '../lib/format.js';
import Icon from '../components/Icon.vue';
import StatusText from '../components/StatusText.vue';
import Skeleton from '../components/Skeleton.vue';

const router = useRouter();

const scans = ref([]);
const loading = ref(true);
const error = ref(null);

onMounted(async () => {
  try {
    const data = await fetchScans();
    scans.value = data.sort((a, b) => new Date(b.started_at) - new Date(a.started_at));
  } catch (e) {
    if (e instanceof UnauthorizedError) { redirectToLogin(); return; }
    error.value = 'Failed to load scans. Is the API up?';
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title rise-in">Scans</h1>
        <div class="page-sub"><span class="mono">all scan runs · newest first</span></div>
      </div>
    </div>

    <Skeleton v-if="loading" label="loading_scans" variant="table" :rows="8" />
    <div v-else-if="error" class="panel"><div class="panel-body" style="color: var(--sev-high)">{{ error }}</div></div>

    <div v-else class="panel">
      <div class="tbl-scroll">
      <table class="tbl scans-tbl">
        <thead>
          <tr>
            <th class="col-id">Scan ID</th>
            <th>Project</th>
            <th class="col-tool">Tool</th>
            <th class="col-started">Started</th>
            <th class="col-dur">Duration</th>
            <th class="num col-count">Findings</th>
            <th class="col-status">Status</th>
            <th class="col-chev"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in scans" :key="s.id" @click="router.push(`/scan/${s.id}`)" style="cursor: pointer">
            <td><span class="cell-clip" style="color: var(--accent)" :title="s.id">{{ s.id }}</span></td>
            <td><span class="cell-clip row-link" style="color: var(--accent)" :title="s.project_name" @click.stop="router.push(`/project/${s.project_id}`)">{{ s.project_name }}</span></td>
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
          <tr v-if="scans.length === 0">
            <td colspan="8" class="mono dim" style="text-align: center; padding: 20px">No scans yet.</td>
          </tr>
        </tbody>
      </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Same recipe as the findings table: fixed layout holds column widths,
   Project absorbs the leftover, and below the floor the .tbl-scroll
   wrapper scrolls sideways instead of wrapping cells into tall rows. */
.scans-tbl {
  table-layout: fixed;
  min-width: 880px;
}
.col-id { width: 140px; }
.col-tool { width: 110px; }
.col-started { width: 150px; }
.col-dur { width: 90px; }
.col-count { width: 80px; }
.col-status { width: 110px; }
.col-chev { width: 36px; }
</style>
