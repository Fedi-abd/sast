# SAST Platform — Vue 3 port

Vue 3 SFC translation of the prototype. Visual fidelity preserved — `styles.css` is the same one that's in the prototype, with the `rise-in` animation appended.

```
frontend/
├── package.json              vue@^3.4, vue-router@^4.3, vite@^5.2
├── vite.config.js
├── index.html                root, loads /src/main.js
├── src/
│   ├── main.js               app entry
│   ├── App.vue               picks layout based on route.meta.layout
│   ├── router.js             vue-router (hash mode), one route per screen
│   ├── styles.css            tokens + components + print + rise-in
│   ├── data.js               mock data — REPLACE with API calls
│   ├── lib/
│   │   └── labels.js         sourceLabel() helper
│   ├── components/           primitives
│   │   ├── Icon.vue
│   │   ├── Pill.vue
│   │   ├── StatusText.vue
│   │   ├── SeverityBar.vue
│   │   ├── Bar.vue
│   │   ├── SourceIcon.vue
│   │   ├── ProjectCard.vue
│   │   ├── ScanActionCard.vue
│   │   ├── Finding.vue
│   │   ├── SevRow.vue
│   │   ├── Field.vue
│   │   └── ScanVolumeChart.vue
│   ├── layouts/
│   │   ├── MainLayout.vue    sidebar + topbar + <slot>
│   │   ├── Sidebar.vue
│   │   ├── Topbar.vue
│   │   └── ThemeToggle.vue
│   └── views/                one .vue per screen
│       ├── Dashboard.vue
│       ├── Projects.vue
│       ├── ProjectDetail.vue
│       ├── ScanResults.vue
│       ├── Vulnerabilities.vue
│       ├── Scans.vue
│       ├── NewProject.vue
│       ├── Signup.vue
│       └── Stub.vue
```

## Running locally

```
cd frontend
npm install
npm run dev
```

## Notes for porting to your stack

- All components use `<script setup>` composition API.
- Router uses hash mode (`#/dashboard`) to match the prototype. Swap to `createWebHistory()` for clean URLs once Django routing is sorted.
- `data.js` is the only place mock data lives. Replace each `import { PROJECTS, SCAN_RUNS, … } from '../data.js'` with an API call.
- Theme persists in `localStorage.sast_theme` — pure client state.
- Print: `window.print()` triggered from `ScanResults.vue` and `ProjectDetail.vue`. Print stylesheet in `styles.css`.
- Signup uses `meta: { layout: 'auth' }` to skip the main layout. Login (Django-templated per your note) is a separate page outside Vue.
- Child routes inherit a sidebar key via `route.meta.sidebarKey` (e.g. `/projects/new` keeps Projects highlighted).

## rise-in animation

Applied to: page H1s, KPI tiles, project cards, recent_scans rows, intel + scan_console panels on Project Detail, list rows on Vulnerabilities / Scans. Stagger via `:style="{ animationDelay: idx * 40 + 'ms' }"`. Reduced-motion off via `@media (prefers-reduced-motion: no-preference)`.

Strictly initial-mount reveal. If you need to suppress it during in-place updates (e.g. after a refetch where the component stays mounted), the class is the trigger — adding/removing it once on mount is enough. For Vue specifically, the `rise-in` class is set in the template and never toggled at runtime, which gives you the "initial-mount only" semantics for free.

See `HANDOFF.md` in the project root for full design tokens, vocabulary, layout descriptions, state coverage, and backend boundaries.
