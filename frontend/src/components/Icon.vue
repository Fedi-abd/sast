<script setup>
defineProps({
  name: { type: String, required: true },
  size: { type: Number, default: 16 },
});

// All 24x24, 1.5 stroke, currentColor; match the React Icon set 1:1.
const paths = {
  dashboard: `<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>`,
  projects:  `<path d="M3 7l0 12a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1V9a1 1 0 0 0-1-1h-8L10 5H4a1 1 0 0 0-1 1z"/>`,
  shield:    `<path d="M12 3l8 3v6c0 4.5-3.4 8.5-8 9-4.6-.5-8-4.5-8-9V6l8-3z"/>`,
  scan:      `<circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="8"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2"/>`,
  settings:  `<circle cx="12" cy="12" r="3"/><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41m11.32-11.32l1.41-1.41"/>`,
  search:    `<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>`,
  bell:      `<path d="M18 16v-5a6 6 0 0 0-12 0v5l-2 3h16l-2-3z"/><path d="M10 21a2 2 0 0 0 4 0"/>`,
  help:      `<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 0 1 4.9.7c0 1.7-2.4 2.3-2.4 4M12 17h.01"/>`,
  sun:       `<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>`,
  moon:      `<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>`,
  plus:      `<path d="M12 5v14M5 12h14"/>`,
  arrowRight:`<path d="M5 12h14M13 5l7 7-7 7"/>`,
  chevronRight:`<path d="M9 6l6 6-6 6"/>`,
  chevronDown:`<path d="M6 9l6 6 6-6"/>`,
  play:      `<path d="M6 4l14 8-14 8V4z"/>`,
  fastForward:`<path d="M4 6v12l8-6-8-6zm9 0v12l8-6-8-6z"/>`,
  git:       `<circle cx="6" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="12" r="2.5"/><path d="M6 9v6M8 6h2a4 4 0 0 1 4 4v0M14 14l-6 4"/>`,
  folder:    `<path d="M3 7l0 12a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1V9a1 1 0 0 0-1-1h-8L10 5H4a1 1 0 0 0-1 1z"/>`,
  archive:   `<rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8M10 12h4"/>`,
  code:      `<path d="M16 18l6-6-6-6M8 6l-6 6 6 6"/>`,
  clock:     `<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>`,
  alert:     `<path d="M12 3L2 20h20L12 3z"/><path d="M12 10v4M12 17h.01"/>`,
  check:     `<path d="M5 12l5 5L20 7"/>`,
  x:         `<path d="M6 6l12 12M18 6L6 18"/>`,
  edit:      `<path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>`,
  trash:     `<path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M19 6l-1 14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1L5 6"/>`,
  download:  `<path d="M21 15v4a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-4M7 10l5 5 5-5M12 15V3"/>`,
  filter:    `<path d="M3 5h18l-7 9v6l-4-2v-4L3 5z"/>`,
  logout:    `<path d="M9 21H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h4"/><path d="M16 17l5-5-5-5M21 12H9"/>`,
  book:      `<path d="M4 4h6a4 4 0 0 1 4 4v12a3 3 0 0 0-3-3H4V4z"/><path d="M20 4h-6a4 4 0 0 0-4 4v12a3 3 0 0 1 3-3h7V4z"/>`,
  refresh:   `<path d="M21 12a9 9 0 0 1-15 6.7L3 16M3 12a9 9 0 0 1 15-6.7L21 8M21 3v5h-5M3 21v-5h5"/>`,
  eye:       `<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>`,
  terminal:  `<rect x="3" y="4" width="18" height="16" rx="1"/><path d="M7 9l3 3-3 3M13 15h4"/>`,
  users:     `<circle cx="9" cy="8" r="3.2"/><path d="M3.5 20a5.5 5.5 0 0 1 11 0"/><path d="M16 5.3a3.2 3.2 0 0 1 0 6.1"/><path d="M17.5 14.4A5.5 5.5 0 0 1 20.5 20"/>`,
  sliders:   `<path d="M4 6h8M16 6h4"/><circle cx="14" cy="6" r="2"/><path d="M4 12h4M12 12h8"/><circle cx="10" cy="12" r="2"/><path d="M4 18h8M16 18h4"/><circle cx="14" cy="18" r="2"/>`,
  server:    `<rect x="3" y="4" width="18" height="7" rx="1"/><rect x="3" y="13" width="18" height="7" rx="1"/><path d="M7 7.5h.01M7 16.5h.01"/>`,
  key:       `<circle cx="7.5" cy="15.5" r="4.5"/><path d="M10.7 12.3L20 3M17 6l2.5 2.5M14 9l2.5 2.5"/>`,
};
</script>

<template>
  <svg
    class="ico"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    v-html="paths[name] || ''"
  />
</template>
