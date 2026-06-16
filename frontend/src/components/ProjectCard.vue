<script setup>
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import Pill from './Pill.vue';
import StatusText from './StatusText.vue';
import SourceIcon from './SourceIcon.vue';
import { sourceLabel, relativeTime, scanStatusMeta } from '../lib/format.js';

const props = defineProps({
  p: { type: Object, required: true },
  // Latest scan for this project, JOINed by the parent from /api/scans/.
  latest: { type: Object, default: null },
});
const router = useRouter();

const scan = computed(() => props.latest);
const st = computed(() => scan.value ? scanStatusMeta(scan.value.status) : null);
const open = () => router.push(`/project/${props.p.id}`);
</script>

<template>
  <div class="project-card" @click="open">
    <div class="project-head">
      <div class="project-name">{{ p.name }}</div>
      <div class="project-status">
        <StatusText v-if="scan" :kind="st.kind" :label="st.label" />
        <span v-else class="mono dim" style="font-size: var(--fs-xs)">NO_SCANS</span>
      </div>
    </div>

    <div class="project-meta">
      <span class="pill">
        <SourceIcon :type="p.source_type" />
        {{ sourceLabel(p.source_type) }}
      </span>
      <span class="pill">{{ p.language || 'n/a' }}</span>
    </div>

    <!-- finding_count from latest scan (no severity split at this level) -->
    <div v-if="scan && scan.status === 'RUNNING'" class="row-flex" style="gap: 8px">
      <span class="spinner" />
      <span class="mono" style="font-size: var(--fs-sm); color: var(--accent)">
        {{ scan.tool_display }} · scanning…
      </span>
    </div>
    <div v-else-if="scan && scan.status === 'SUCCESS'" class="row-flex" style="gap: 8px">
      <span class="mono" style="font-size: var(--fs-2xl); color: var(--fg); letter-spacing: -0.02em">{{ scan.finding_count }}</span>
      <span class="mono" style="font-size: var(--fs-sm); color: var(--fg-2)">finding{{ scan.finding_count === 1 ? '' : 's' }}</span>
    </div>
    <div v-else-if="scan && scan.status === 'FAILED'" class="mono" style="font-size: var(--fs-sm); color: var(--sev-high)">
      last scan failed
    </div>
    <div v-else class="mono" style="font-size: var(--fs-sm); color: var(--fg-2)">
      No scans run yet
    </div>

    <div class="project-foot">
      <span v-if="scan">last_scan · <span class="when">{{ relativeTime(scan.started_at) }}</span> · {{ scan.tool }}</span>
      <span v-else>ready to scan</span>
      <span style="color: var(--fg-3)">{{ (p.created_at || '').slice(0, 10) }}</span>
    </div>
  </div>
</template>
