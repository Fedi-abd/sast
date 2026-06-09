<script setup lang="ts">
/**
 * Pill / chip label. Linear-style: subtle colored background, strong
 * colored text, optional leading dot indicator for status variants.
 *
 * Variants:
 *   info       — brand blue (default)
 *   neutral    — slate gray ("CORE" / generic tag)
 *   success    — green (scan SUCCESS, etc.)
 *   warning    — amber (scan RUNNING, MEDIUM severity)
 *   danger     — red (scan FAILED, HIGH severity)
 *   accent     — cyan (special / system tags)
 *
 * Sizing:
 *   sm (default) — dense rows
 *   md           — slightly chunkier, for emphasis
 *
 * `dot` prop adds a small filled circle before the label — use for
 * "live" status (RUNNING, online, etc.) to suggest motion.
 *
 * `uppercase` prop renders as a category tag (smaller, tracking).
 */
import { computed } from 'vue'

type Variant = 'info' | 'neutral' | 'success' | 'warning' | 'danger' | 'accent'
type Size = 'sm' | 'md'

const props = withDefaults(
  defineProps<{
    variant?: Variant
    size?: Size
    uppercase?: boolean
    dot?: boolean
  }>(),
  { variant: 'info', size: 'sm', uppercase: false, dot: false },
)

// Per-variant: background tint + text color, in both modes. Tints use
// /15 opacity on dark surfaces so the chip reads as "of the surface"
// rather than pasted on top. Text colors are picked to clear WCAG AA
// against the tinted background in both themes.
const variantClasses: Record<Variant, string> = {
  info:    'bg-brand-50  text-brand-700  dark:bg-brand-500/15  dark:text-brand-200',
  neutral: 'bg-slate-100 text-slate-700  dark:bg-slate-500/15  dark:text-slate-200',
  success: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200',
  warning: 'bg-amber-50  text-amber-800  dark:bg-amber-500/15  dark:text-amber-200',
  danger:  'bg-red-50    text-red-700    dark:bg-red-500/15    dark:text-red-200',
  accent:  'bg-cyan-50   text-cyan-700   dark:bg-cyan-500/15   dark:text-cyan-200',
}

const dotClasses: Record<Variant, string> = {
  info:    'bg-brand-500',
  neutral: 'bg-slate-400',
  success: 'bg-emerald-500',
  warning: 'bg-amber-500',
  danger:  'bg-red-500',
  accent:  'bg-cyan-500',
}

const sizeClasses: Record<Size, string> = {
  sm: 'px-2 py-0.5 text-[0.75rem]',
  md: 'px-2.5 py-1 text-sm',
}

const classes = computed(() => [
  'inline-flex items-center gap-1.5 rounded-md font-medium',
  'ring-1 ring-inset',
  // Each variant's ring tone derives from the bg — picked to be just
  // visible against the card surface, not a hard edge.
  props.variant === 'info' && 'ring-brand-200/60 dark:ring-brand-300/15',
  props.variant === 'neutral' && 'ring-slate-200 dark:ring-slate-300/15',
  props.variant === 'success' && 'ring-emerald-200/60 dark:ring-emerald-300/15',
  props.variant === 'warning' && 'ring-amber-200/60 dark:ring-amber-300/15',
  props.variant === 'danger' && 'ring-red-200/60 dark:ring-red-300/15',
  props.variant === 'accent' && 'ring-cyan-200/60 dark:ring-cyan-300/15',
  variantClasses[props.variant],
  sizeClasses[props.size],
  props.uppercase ? 'uppercase tracking-wider text-[0.6875rem] font-semibold' : '',
])
</script>

<template>
  <span :class="classes">
    <span
      v-if="dot"
      :class="['w-1.5 h-1.5 rounded-full', dotClasses[variant]]"
      aria-hidden="true"
    />
    <slot />
  </span>
</template>
