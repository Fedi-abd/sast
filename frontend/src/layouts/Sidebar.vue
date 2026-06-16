<script setup>
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import Icon from '../components/Icon.vue';
import ThemeToggle from './ThemeToggle.vue';
import { auth } from '../auth.js';
import { logout as apiLogout } from '../api.js';

const NAV = [
  { id: 'dashboard', label: 'Dashboard', icon: 'dashboard' },
  { id: 'projects',  label: 'Projects',  icon: 'projects' },
  { id: 'scans',     label: 'Scans',     icon: 'scan' },
  { id: 'vulns',     label: 'Findings',  icon: 'shield' },
];

const route = useRoute();
const router = useRouter();
const me = computed(() => auth.me || {});

// child routes (project/:id, scan/:id, projects/new) inherit their parent via meta.sidebarKey
const active = computed(() => route.meta.sidebarKey || route.name);
const go = (id) => router.push('/' + id);
const logout = () => apiLogout();
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-row">
        <span class="brand-logo">SAST</span>
        <span class="brand-sub">platform</span>
      </div>
      <div class="brand-meta">
        <span class="pulse" />core // v2.4.0
      </div>
    </div>

    <nav class="nav" aria-label="Primary">
      <div class="nav-section">Workspace</div>
      <a
        v-for="n in NAV"
        :key="n.id"
        :class="['nav-item', active === n.id ? 'active' : '']"
        @click="go(n.id)"
      >
        <Icon :name="n.icon" />
        <span>{{ n.label }}</span>
        <span v-if="n.count !== undefined" class="nav-count mono">{{ n.count }}</span>
      </a>

      <div class="nav-section">System</div>
      <a v-if="me.is_staff" :class="['nav-item', active === 'admin' ? 'active' : '']" @click="router.push('/admin')">
        <Icon name="settings" />
        <span>Admin</span>
      </a>
      <a :class="['nav-item', active === 'settings' ? 'active' : '']" @click="router.push('/settings')">
        <Icon name="sliders" />
        <span>Settings</span>
      </a>
      <a :class="['nav-item', active === 'docs' ? 'active' : '']" @click="router.push('/docs')">
        <Icon name="book" />
        <span>Documentation</span>
      </a>
    </nav>

    <div class="sidebar-foot">
      <div class="credits-chip" :title="me.is_staff ? `staff accounts aren't metered` : 'Scan credits remaining'">
        <Icon name="scan" :size="13" />
        <span class="mono">{{ (me.is_staff || me.credits < 0) ? '∞' : me.credits }}</span>
        <span class="mono credits-word">credits</span>
      </div>
      <ThemeToggle />
      <a class="nav-item" style="margin-top: 6px" @click="logout">
        <Icon name="logout" />
        <span>Log out</span>
      </a>
    </div>
  </aside>
</template>
