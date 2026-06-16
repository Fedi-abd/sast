<script setup>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { auth } from '../auth.js';
import Icon from '../components/Icon.vue';
import Pill from '../components/Pill.vue';
import StatusText from '../components/StatusText.vue';
import SonarqubeConfig from '../components/admin/SonarqubeConfig.vue';
import UserLimits from '../components/admin/UserLimits.vue';
import UsageLog from '../components/admin/UsageLog.vue';
import UserManagement from '../components/admin/UserManagement.vue';
import DeploymentToggles from '../components/admin/DeploymentToggles.vue';

const router = useRouter();
const me = computed(() => auth.me || {});
const tab = ref('sonarqube');

// No count badges: each tab fetches its own data lazily, and the
// shell shouldn't fire three requests just to decorate the tab bar.
const TABS = [
  { id: 'sonarqube',  label: 'sonarqube',  icon: 'scan' },
  { id: 'limits',     label: 'limits',     icon: 'sliders' },
  { id: 'usage',      label: 'usage',      icon: 'terminal' },
  { id: 'users',      label: 'users',      icon: 'users' },
  { id: 'deployment', label: 'deployment', icon: 'server' },
];
</script>

<template>
  <!-- Defense in depth: the backend enforces is_staff, but a non-staff user
       who deep-links here should never see the console. -->
  <div v-if="!me.is_staff" class="page">
    <div class="panel" style="margin-top: 40px">
      <div class="panel-body" style="text-align: center; padding: 64px">
        <Icon name="shield" :size="28" />
        <div style="margin-top: 16px; font-size: var(--fs-lg); font-weight: 600">Staff access required</div>
        <div class="mono" style="margin-top: 6px; color: var(--fg-2); font-size: var(--fs-sm)">
          The admin console is restricted to staff accounts. <span style="color: var(--sev-high)">[403]</span>
        </div>
        <button class="btn btn-primary" style="margin-top: 20px" @click="router.push('/dashboard')">
          <Icon name="arrowRight" :size="14" /> Back to dashboard
        </button>
      </div>
    </div>
  </div>

  <div v-else class="page">
    <div class="page-head">
      <div>
        <div style="display: flex; align-items: center; gap: 12px">
          <h1 class="page-title rise-in">Admin</h1>
          <Pill kind="accent" dot>STAFF</Pill>
        </div>
        <div class="page-sub" style="margin-top: 4px">
          <span class="mono">operator console · {{ me.username }}</span>
          <span style="color: var(--fg-3)"> · </span>
          <span class="mono">access: </span>
          <StatusText kind="run" label="STAFF" />
        </div>
      </div>
    </div>

    <div class="tabs" role="tablist">
      <button
        v-for="t in TABS"
        :key="t.id"
        role="tab"
        :aria-selected="tab === t.id"
        :class="['tab', tab === t.id ? 'active' : '']"
        @click="tab = t.id"
      >
        <Icon :name="t.icon" :size="14" />
        {{ t.label }}
      </button>
    </div>

    <SonarqubeConfig   v-if="tab === 'sonarqube'" />
    <UserLimits        v-else-if="tab === 'limits'" />
    <UsageLog          v-else-if="tab === 'usage'" />
    <UserManagement    v-else-if="tab === 'users'" />
    <DeploymentToggles v-else-if="tab === 'deployment'" />
  </div>
</template>
