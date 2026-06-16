<script setup>
defineProps({
  // Mono CLI label line above the blocks, e.g. "loading_dashboard";
  // pass it on the page's first skeleton only. variant="label" renders
  // the line alone, for pages whose first shimmer block sits inside a
  // grid cell (a label there would skew the columns).
  label: { type: String, default: '' },
  // label | stat-cards | chips | cards | table | panel
  variant: { type: String, default: 'panel' },
  rows: { type: Number, default: 4 },
  count: { type: Number, default: 4 },
});

// deterministic jitter so bars read as text, not uniform stripes
const lineWidth = (i) => ['72%', '88%', '58%', '80%'][i % 4];
const chipWidth = (i) => [96, 122, 84, 108, 90][i % 5] + 'px';
</script>

<template>
  <div class="sk">
    <div v-if="label" class="sk-label mono">// {{ label }}<span class="sk-cursor">▍</span></div>

    <div v-if="variant === 'stat-cards'" class="stat-row" aria-hidden="true">
      <div v-for="i in count" :key="i" class="stat">
        <div class="sk-block" style="width: 45%; height: 10px; margin-bottom: 14px" />
        <div class="sk-block" style="width: 58px; height: 26px" />
        <div class="sk-block" style="width: 70%; height: 9px; margin-top: 10px" />
      </div>
    </div>

    <div v-else-if="variant === 'chips'" class="sk-chips" aria-hidden="true">
      <div v-for="i in count" :key="i" class="sk-block sk-chip" :style="{ width: chipWidth(i) }" />
    </div>

    <div v-else-if="variant === 'cards'" class="project-grid" aria-hidden="true">
      <div v-for="i in count" :key="i" class="panel sk-card">
        <div class="sk-block" style="width: 55%; height: 14px" />
        <div class="sk-block" style="width: 75%; height: 10px; margin-top: 8px" />
        <div style="display: flex; gap: 6px; margin-top: 18px">
          <div class="sk-block" style="width: 64px; height: 20px" />
          <div class="sk-block" style="width: 64px; height: 20px" />
        </div>
        <div class="sk-block" style="width: 100%; height: 10px; margin-top: 18px" />
      </div>
    </div>

    <div v-else-if="variant === 'table'" class="panel" aria-hidden="true">
      <div class="panel-head"><span class="sk-block" style="width: 130px; height: 10px" /></div>
      <div class="sk-rows">
        <div v-for="i in rows" :key="i" class="sk-block sk-row" />
      </div>
    </div>

    <div v-else-if="variant === 'panel'" class="panel" aria-hidden="true">
      <div class="panel-head"><span class="sk-block" style="width: 130px; height: 10px" /></div>
      <div class="panel-body sk-rows">
        <div v-for="i in rows" :key="i" class="sk-block sk-line" :style="{ width: lineWidth(i) }" />
      </div>
    </div>
  </div>
</template>

<style scoped>
/* echoes Loading.vue's "label ▍" so the CLI personality carries over */
.sk-label {
  font-size: var(--fs-sm);
  color: var(--fg-2);
  margin-bottom: 14px;
}
.sk-cursor {
  margin-left: 2px;
  color: var(--accent);
  animation: sk-blink 1s steps(1) infinite;
}
@keyframes sk-blink {
  50% { opacity: 0; }
}

.sk-block {
  background: var(--bg-inset);
  border-radius: var(--r-2);
  position: relative;
  overflow: hidden;
}
/* left-to-right sweep; --bg-2 sits lighter than the inset tone in dark
   mode and darker in light mode, so it reads as a sheen in both themes */
.sk-block::after {
  content: '';
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(90deg, transparent, var(--bg-2) 50%, transparent);
  animation: sk-shimmer 1.6s ease-in-out 0.2s infinite;
}
@keyframes sk-shimmer {
  to { transform: translateX(100%); }
}

.sk-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}
.sk-chip { height: 26px; }

.sk-card { padding: 16px; }

.sk-rows {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 14px 16px;
}
.panel-body.sk-rows { gap: 12px; }
.sk-row { height: 14px; }
.sk-line { height: 12px; }

@media (prefers-reduced-motion: reduce) {
  .sk-block::after { animation: none; opacity: 0; }
  .sk-cursor { animation: none; }
}
</style>
