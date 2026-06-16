<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import Icon from '../components/Icon.vue';
import { auth } from '../auth.js';
import { logout as apiLogout } from '../api.js';

const route = useRoute();
const router = useRouter();
const me = computed(() => auth.me || {});

const profileOpen = ref(false);
let outsideHandlers = null;
const attachOutside = () => {
  const onDown = (e) => { if (!e.target.closest('.profile-wrap')) profileOpen.value = false; };
  const onKey = (e) => { if (e.key === 'Escape') profileOpen.value = false; };
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
watch(profileOpen, (open) => { open ? attachOutside() : detachOutside(); });
onBeforeUnmount(detachOutside);
const logout = () => { profileOpen.value = false; apiLogout(); };
// password change is a styled Django page; full page nav is correct
const changePassword = () => { profileOpen.value = false; window.location.assign('/accounts/password_change/'); };

// Breadcrumbs. Project/scan names aren't resolved here anymore (no
// module-global list to look them up in); the active view shows the
// full name in its own header, so a generic segment reads fine.
const crumbs = computed(() => {
  const c = [{ label: 'sast', to: '/dashboard' }];
  const name = route.name;
  if (name === 'dashboard') c.push({ label: 'dashboard' });
  else if (name === 'projects') c.push({ label: 'projects' });
  else if (name === 'new-project') {
    c.push({ label: 'projects', to: '/projects' });
    c.push({ label: 'new' });
  } else if (name === 'project') {
    c.push({ label: 'projects', to: '/projects' });
    c.push({ label: 'project' });
  } else if (name === 'scan') {
    c.push({ label: 'projects', to: '/projects' });
    c.push({ label: 'scan' });
  } else if (name === 'vulns') {
    c.push({ label: 'dashboard', to: '/dashboard' });
    c.push({ label: 'findings' });
  } else if (name === 'admin') {
    c.push({ label: 'admin' });
  } else if (name) {
    c.push({ label: String(name) });
  }
  return c;
});
</script>

<template>
  <div class="topbar">
    <div class="crumb">
      <template v-for="(c, i) in crumbs" :key="i">
        <span v-if="i > 0" class="sep">/</span>
        <a v-if="c.to" @click="router.push(c.to)">{{ c.label }}</a>
        <span v-else :class="i === crumbs.length - 1 ? 'here' : ''">{{ c.label }}</span>
      </template>
    </div>
    <div class="topbar-search">
      <Icon name="search" :size="14" />
      <input placeholder="Search projects, scans, findings…" />
      <kbd>⌘K</kbd>
    </div>
    <div class="topbar-actions">
      <button class="icon-btn" title="Notifications">
        <Icon name="bell" /><span class="dot" />
      </button>
      <button class="icon-btn" title="Help" @click="router.push('/docs')">
        <Icon name="help" />
      </button>
    </div>
    <div class="profile-wrap">
      <button
        class="avatar avatar-btn mono"
        :aria-haspopup="'menu'"
        :aria-expanded="profileOpen"
        :title="me.email"
        @click="profileOpen = !profileOpen"
      >{{ (me.username || '?').slice(0, 2).toUpperCase() }}</button>
      <div v-if="profileOpen" class="profile-menu" role="menu">
        <div class="profile-head">
          <div class="profile-name">{{ me.username }}</div>
          <div class="profile-email mono">{{ me.email }}</div>
        </div>
        <div class="menu-row">
          <Icon name="scan" :size="13" />
          <span v-if="me.is_staff" class="mono" title="staff accounts aren't metered">∞</span>
          <span v-else class="mono">{{ me.credits < 0 ? '∞' : me.credits }}</span>
          <span class="credits-word">credits</span>
        </div>
        <div class="menu-sep" />
        <button class="menu-item" role="menuitem" @click="changePassword">
          <Icon name="key" :size="13" /> Change password
        </button>
        <div class="menu-sep" />
        <button class="menu-item" role="menuitem" @click="logout">
          <Icon name="logout" :size="13" /> Log out
        </button>
      </div>
    </div>
  </div>
</template>
