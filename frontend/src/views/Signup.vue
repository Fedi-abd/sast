<script setup>
import { ref, reactive, computed } from 'vue';
import { useRouter } from 'vue-router';
import Icon from '../components/Icon.vue';
import Pill from '../components/Pill.vue';
import Field from '../components/Field.vue';

const router = useRouter();

const form = reactive({
  name: '',
  email: '',
  org: '',
  role: 'engineer',
  password: '',
  confirm: '',
  terms: false,
});

const errors = reactive({});
const step = ref('form'); // 'form' | 'done'

const firstName = computed(() => form.name.split(' ')[0]);

const submit = () => {
  Object.keys(errors).forEach(k => delete errors[k]);
  if (!form.name.trim()) errors.name = 'required';
  if (!form.email.includes('@')) errors.email = 'valid email required';
  if (form.password.length < 12) errors.password = 'min 12 characters';
  if (form.password !== form.confirm) errors.confirm = 'passwords do not match';
  if (!form.terms) errors.terms = 'must accept';
  if (Object.keys(errors).length === 0) step.value = 'done';
};
</script>

<template>
  <div class="auth-shell">
    <div class="auth-pane aside">
      <div class="auth-aside-art">
        <div class="auth-aside-card">
          <div class="term-line"><span class="prompt">$</span> sast init --workspace acme</div>
          <div class="term-line">→ allocating namespace</div>
          <div class="term-line">→ provisioning scan workers <span class="ok">[OK]</span></div>
          <div class="term-line">→ loading default rulesets <span class="ok">[OK]</span></div>
          <div class="term-line">→ wiring integrations · semgrep, sonarqube</div>
          <div class="term-line"><span class="prompt">$</span> sast project add core-auth-service</div>
          <div class="term-line">→ cloning repo</div>
          <div class="term-line">→ language detection · Go, gRPC</div>
          <div class="term-line"><span class="prompt">$</span> sast scan run --tool=semgrep</div>
          <div class="term-line"><span style="color: var(--accent)">▸</span> 14,204 files · 1.2M LOC · 00:00:45</div>
          <div class="term-line">
            <span class="high">2 high</span> · <span class="warn">5 medium</span> · 3 low
          </div>
          <div class="term-line" style="color: var(--fg-3); margin-top: 8px">// register to begin →</div>
        </div>
      </div>
    </div>

    <div class="auth-pane">
      <form class="auth-form" @submit.prevent="submit">
        <div class="auth-brand">
          <span class="brand-logo">SAST</span>
          <span class="brand-sub">platform</span>
        </div>

        <template v-if="step === 'form'">
          <div>
            <h1 class="auth-h rise-in">Create your account</h1>
            <p class="auth-sub">
              Already have one?
              <a style="color: var(--accent); cursor: pointer" @click.prevent="router.push('/dashboard')">Sign in</a>
            </p>
          </div>

          <div class="auth-stack">
            <Field label="Full name" :error="errors.name || ''">
              <input v-model="form.name" placeholder="Alex Chen" />
            </Field>

            <Field label="Work email" :error="errors.email || ''">
              <input v-model="form.email" type="email" placeholder="alex@acme.dev" />
            </Field>

            <div style="display: grid; grid-template-columns: 1fr 140px; gap: 12px">
              <Field label="Organization">
                <input v-model="form.org" placeholder="acme" />
              </Field>
              <Field label="Role">
                <select v-model="form.role" style="appearance: none">
                  <option value="engineer">Engineer</option>
                  <option value="security">Security</option>
                  <option value="lead">Lead</option>
                  <option value="auditor">Auditor</option>
                </select>
              </Field>
            </div>

            <Field label="Password" hint="12+ chars · mix of letters, digits, symbols" :error="errors.password || ''">
              <input v-model="form.password" type="password" />
            </Field>

            <Field label="Confirm password" :error="errors.confirm || ''">
              <input v-model="form.confirm" type="password" />
            </Field>

            <label style="display: flex; align-items: flex-start; gap: 10px; margin-top: 4px; cursor: pointer">
              <input
                type="checkbox"
                v-model="form.terms"
                style="margin-top: 3px; accent-color: var(--accent)"
              />
              <span class="mono" style="font-size: var(--fs-sm); color: var(--fg-1); line-height: 1.5">
                I accept the
                <a style="color: var(--accent)">terms</a> and
                <a style="color: var(--accent)">privacy policy</a>.
              </span>
            </label>
            <div v-if="errors.terms" class="form-error">You must accept to continue.</div>
          </div>

          <button class="btn btn-primary" type="submit" style="justify-content: center; padding: 12px 14px">
            <Icon name="arrowRight" :size="14" /> Create account
          </button>

          <div class="auth-row">
            <span>// secured by sast_core</span>
            <span style="color: var(--fg-3)">v2.4.0</span>
          </div>
        </template>

        <div v-else class="auth-stack" style="text-align: center; align-items: center; padding-top: 40px">
          <Pill kind="ok">ACCOUNT CREATED</Pill>
          <h1 class="auth-h" style="margin-top: 16px">Welcome, {{ firstName }}.</h1>
          <p class="auth-sub" style="max-width: 320px">
            We sent a verification link to
            <span class="mono" style="color: var(--fg)">{{ form.email }}</span>.
            Click it to activate scanning.
          </p>
          <button class="btn btn-primary" @click="router.push('/dashboard')" style="margin-top: 12px; padding: 12px 14px">
            <Icon name="arrowRight" :size="14" /> Continue to dashboard
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
