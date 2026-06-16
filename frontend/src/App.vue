<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { useRoute } from 'vue-router';
import MainLayout from './layouts/MainLayout.vue';

const route = useRoute();

// Mid-session cutoff (expired session / deactivated account): api.js
// emits this instead of hard-bouncing, so the user learns why before
// landing on the login page.
const sessionEndedUrl = ref(null);
const onSessionEnded = (e) => { sessionEndedUrl.value = e.detail.url; };
onMounted(() => window.addEventListener('sast:session-ended', onSessionEnded));
onUnmounted(() => window.removeEventListener('sast:session-ended', onSessionEnded));
const toLogin = () => window.location.assign(sessionEndedUrl.value);
</script>

<template>
  <router-view v-if="route.meta.layout === 'auth'" />
  <MainLayout v-else>
    <router-view />
  </MainLayout>

  <div v-if="sessionEndedUrl" class="session-overlay">
    <div class="session-modal panel">
      <div class="panel-head"><span class="panel-title">// session_ended</span></div>
      <div class="panel-body">
        <p style="margin: 0 0 6px; font-weight: 600">You've been signed out.</p>
        <p class="mono" style="font-size: var(--fs-sm); color: var(--fg-2); margin: 0 0 16px; line-height: 1.6">
          Your session expired or your account was changed. If this is
          unexpected, contact your administrator.
        </p>
        <button class="btn btn-primary" @click="toLogin">Go to login →</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.session-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: oklch(0.1 0.01 245 / 0.6);
  backdrop-filter: blur(2px);
}
.session-modal {
  width: min(420px, calc(100vw - 48px));
}
</style>
