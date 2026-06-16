<script setup>
import { ref, watch, onBeforeUnmount } from 'vue';
import Icon from './Icon.vue';

/**
 * CLI-themed replacement for a native <select>. The native dropdown
 * panel is OS-drawn and ignores the dark theme, so we render our own.
 * v-model holds the selected string; '' means "not specified".
 */
const props = defineProps({
  modelValue: { type: String, default: '' },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: 'not specified' },
});
const emit = defineEmits(['update:modelValue']);

const open = ref(false);
const dropUp = ref(false);
const root = ref(null);

// An absolutely positioned panel past the viewport bottom still stretches
// the document scroll, so estimate the panel height before opening and
// flip upward when it wouldn't fit below. ~30px per row (7px padding x2
// + line) + 1 placeholder row + panel padding/border + 4px gap.
const estimatePanelHeight = () =>
  Math.min(240, (props.options.length + 1) * 30 + 10) + 4;

const toggle = () => {
  if (!open.value && root.value) {
    const rect = root.value.getBoundingClientRect();
    const below = window.innerHeight - rect.bottom;
    dropUp.value = below < estimatePanelHeight() && rect.top > below;
  }
  open.value = !open.value;
};

const choose = (value) => {
  emit('update:modelValue', value);
  open.value = false;
};

// Document-level listeners only live while the panel is open, same
// pattern as the profile menu in layouts/Topbar.vue.
let outsideHandlers = null;
const attachOutside = () => {
  const onDown = (e) => { if (root.value && !root.value.contains(e.target)) open.value = false; };
  const onKey = (e) => { if (e.key === 'Escape') open.value = false; };
  document.addEventListener('mousedown', onDown);
  document.addEventListener('keydown', onKey);
  outsideHandlers = { onDown, onKey };
};
const detachOutside = () => {
  if (!outsideHandlers) return;
  document.removeEventListener('mousedown', outsideHandlers.onDown);
  document.removeEventListener('keydown', outsideHandlers.onKey);
  outsideHandlers = null;
};
watch(open, (o) => { o ? attachOutside() : detachOutside(); });
onBeforeUnmount(detachOutside);
</script>

<template>
  <div ref="root" class="input cli-select">
    <button
      type="button"
      class="cli-trigger"
      aria-haspopup="listbox"
      :aria-expanded="open"
      @click="toggle"
    >
      <span class="cli-value" :class="{ ph: !modelValue }">❯ {{ modelValue || placeholder }}</span>
      <Icon name="chevronDown" :size="14" class="chev" :class="{ 'chev-open': open }" />
    </button>

    <div v-if="open" class="cli-panel" :class="{ up: dropUp }" role="listbox">
      <div
        class="cli-opt"
        :class="{ selected: !modelValue }"
        role="option"
        :aria-selected="!modelValue"
        @click="choose('')"
      >
        <span class="cli-label ph"><span class="opt-pfx">&gt; </span>{{ placeholder }}</span>
        <Icon v-if="!modelValue" name="check" :size="12" />
      </div>
      <div
        v-for="opt in options"
        :key="opt"
        class="cli-opt"
        :class="{ selected: opt === modelValue }"
        role="option"
        :aria-selected="opt === modelValue"
        @click="choose(opt)"
      >
        <span class="cli-label"><span class="opt-pfx">&gt; </span>{{ opt }}</span>
        <Icon v-if="opt === modelValue" name="check" :size="12" />
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Root reuses the global .input chrome; relative anchors the panel. */
.cli-select {
  position: relative;
  cursor: pointer;
}
.cli-trigger {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  min-width: 0;
  text-align: left;
  font-family: var(--font-mono);
  font-size: var(--fs-md);
  color: var(--fg);
}
.cli-value {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.cli-value.ph { color: var(--fg-3); }
.chev {
  flex-shrink: 0;
  color: var(--fg-3);
  transition: transform 0.15s ease;
}
.chev-open { transform: rotate(180deg); }

.cli-panel {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 30;
  background: var(--bg-2);
  border: 1px solid var(--line);
  border-radius: var(--r-2);
  box-shadow: 0 8px 24px oklch(0 0 0 / 0.35);
  max-height: 240px;
  overflow: auto;
  padding: 4px;
}
.cli-panel.up {
  top: auto;
  bottom: calc(100% + 4px);
  box-shadow: 0 -8px 24px oklch(0 0 0 / 0.35);
}
.cli-opt {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  padding: 7px 10px;
  border-radius: var(--r-1);
  color: var(--fg);
}
.cli-opt:hover { background: var(--bg-3); }
.cli-label {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.cli-label.ph { color: var(--fg-3); }
/* Local prefix class; NOT .pfx, which .input .pfx would restyle globally. */
.opt-pfx { color: var(--fg-3); }
.cli-opt.selected,
.cli-opt.selected .cli-label,
.cli-opt.selected .opt-pfx { color: var(--accent); }
</style>
