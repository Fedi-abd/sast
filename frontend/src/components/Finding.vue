<script setup>
import { ref, computed } from 'vue';
import Icon from './Icon.vue';
import Pill from './Pill.vue';
import { owaspParse, confidencePct, severityLabel } from '../lib/format.js';

const props = defineProps({
  f: { type: Object, required: true },
  open: { type: Boolean, default: false },
});
defineEmits(['toggle', 'solve']);

const copied = ref('');
const owasp = computed(() => owaspParse(props.f.owasp_category));

const copy = (label, text) => {
  try { navigator.clipboard.writeText(text); } catch (e) {}
  copied.value = label;
  setTimeout(() => { copied.value = ''; }, 1200);
};
</script>

<template>
  <div :class="['disclose', open ? 'open' : '']">
    <div class="disclose-head" @click="$emit('toggle')">
      <Icon name="chevronRight" :size="12" class="caret" />
      <div style="display: flex; flex-direction: column; gap: 4px; min-width: 0">
        <div class="path">{{ f.message }}</div>
        <div class="mono" style="font-size: var(--fs-xs); color: var(--fg-2)">
          {{ f.file_path }}<span style="color: var(--fg-3)">:{{ f.line_number }}</span>
        </div>
      </div>
      <Pill :kind="severityLabel(f.severity)">{{ f.severity }}</Pill>
      <span class="cwe">{{ f.cwe_id }}</span>
    </div>
    <div v-if="open" class="disclose-body">
      <div class="meta-grid">
        <div><span class="mk">TOOL</span><span class="mv">{{ f.tool }}</span></div>
        <div><span class="mk">CWE</span><span class="mv">{{ f.cwe_id }}</span></div>
        <div><span class="mk">OWASP</span><span class="mv">{{ owasp.code === '-' ? 'Unmapped' : `${owasp.code} · ${owasp.label}` }}</span></div>
        <div><span class="mk">CONFIDENCE</span><span class="mv">{{ confidencePct(f.confidence_score) }}</span></div>
        <div style="grid-column: 1 / -1"><span class="mk">RULE_ID</span><span class="mv" style="word-break: break-all">{{ f.rule_id }}</span></div>
        <div style="grid-column: 1 / -1"><span class="mk">LOCATION</span><span class="mv accent">{{ f.file_path }}:{{ f.line_number }}</span></div>
      </div>

      <div style="display: flex; gap: 8px; margin-top: 16px" class="no-print">
        <button class="btn btn-sm" @click="copy('path', `${f.file_path}:${f.line_number}`)">
          <Icon :name="copied === 'path' ? 'check' : 'code'" :size="12" /> {{ copied === 'path' ? 'Copied' : 'Copy path' }}
        </button>
        <button class="btn btn-sm" @click="copy('rule', f.rule_id)">
          <Icon :name="copied === 'rule' ? 'check' : 'filter'" :size="12" /> {{ copied === 'rule' ? 'Copied' : 'Copy rule ID' }}
        </button>
        <button class="btn btn-sm solve-btn" @click="$emit('solve', f)">
          <Icon name="check" :size="12" /> Mark solved
        </button>
      </div>
    </div>
  </div>
</template>
