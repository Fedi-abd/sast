<script setup>
import { computed } from 'vue';
import { auth } from '../auth.js';
import Icon from '../components/Icon.vue';

const me = computed(() => auth.me || {});
// The password form is a styled Django page, so full page nav is correct.
const changePassword = () => window.location.assign('/accounts/password_change/');
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title rise-in">Settings</h1>
        <div class="page-sub"><span class="mono">account · security</span></div>
      </div>
    </div>

    <div class="panel rise-in" style="max-width: 560px">
      <div class="panel-head"><span class="panel-title">// account</span></div>
      <div class="panel-body">
        <dl class="dlist">
          <dt>Username</dt><dd>{{ me.username }}</dd>
          <dt>Email</dt><dd>{{ me.email || '-' }}</dd>
          <dt>Role</dt><dd><span class="mono">{{ me.is_staff ? 'staff' : 'member' }}</span></dd>
          <dt>Credits</dt>
          <dd><span class="mono">{{ (me.is_staff || me.credits < 0) ? '∞' : me.credits }}</span></dd>
        </dl>

        <div class="divider" />

        <button class="btn" @click="changePassword">
          <Icon name="key" :size="14" /> Change password
        </button>
        <div class="form-hint" style="margin-top: 12px; line-height: 1.6">
          Theme lives in the sidebar toggle. Credits and quotas are
          managed by your administrator.
        </div>
      </div>
    </div>
  </div>
</template>
