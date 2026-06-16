<script setup>
import { computed } from 'vue';

// Client-derived from GET /api/scans/. Bucket started_at by day for
// the last 7 days (today rightmost), split SUCCESS / FAILED. RUNNING
// scans aren't counted: they're not an outcome yet. No time-series
// endpoint exists; this stays honest by deriving from real rows.
const props = defineProps({ scans: { type: Array, default: () => [] } });

const data = computed(() => {
  const days = [];
  const now = new Date();
  for (let i = 6; i >= 0; i--) {
    const day = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i);
    days.push({
      key: day.toDateString(),
      d: day.toLocaleDateString('en-US', { weekday: 'short' }),
      ok: 0,
      fail: 0,
    });
  }
  const byKey = Object.fromEntries(days.map((x) => [x.key, x]));
  for (const s of props.scans) {
    const bucket = byKey[new Date(s.started_at).toDateString()];
    if (!bucket) continue;
    if (s.status === 'SUCCESS') bucket.ok++;
    else if (s.status === 'FAILED') bucket.fail++;
  }
  return days;
});
const max = computed(() => Math.max(...data.value.map(d => d.ok + d.fail), 1));
const total = (d) => d.ok + d.fail;
</script>

<template>
  <div class="panel">
    <div class="panel-head">
      <span class="panel-title">// scan_volume · last 7d</span>
      <span class="kbd-hint mono">client-derived</span>
    </div>
    <div class="panel-body">
      <div style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 16px; align-items: end; height: 180px">
        <div v-for="d in data" :key="d.key" style="display: flex; flex-direction: column; align-items: center; gap: 8px">
          <div style="height: 140px; display: flex; flex-direction: column-reverse; width: 100%; max-width: 32px; margin-inline: auto">
            <div :style="{ height: (d.ok / max * 140) + 'px', background: 'var(--ok)', borderTopLeftRadius: '2px', borderTopRightRadius: '2px' }" />
            <div :style="{ height: (d.fail / max * 140) + 'px', background: 'var(--sev-high)', borderTopLeftRadius: d.ok ? '0' : '2px', borderTopRightRadius: d.ok ? '0' : '2px' }" />
          </div>
          <div class="mono" style="font-size: var(--fs-xs); color: var(--fg-2)">{{ d.d }}</div>
          <div class="mono" style="font-size: var(--fs-xs); color: var(--fg-1)">{{ total(d) }}</div>
        </div>
      </div>
      <div style="display: flex; gap: 16px; margin-top: 16px">
        <span class="mono" style="font-size: var(--fs-xs); display: flex; align-items: center; gap: 6px">
          <span style="width: 8px; height: 8px; background: var(--ok)" /> SUCCESS
        </span>
        <span class="mono" style="font-size: var(--fs-xs); display: flex; align-items: center; gap: 6px">
          <span style="width: 8px; height: 8px; background: var(--sev-high)" /> FAILED
        </span>
      </div>
    </div>
  </div>
</template>
