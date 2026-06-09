/**
 * Application bootstrap.
 *
 * Order matters slightly: Pinia must be installed before the router
 * because the router's `beforeEach` guard calls `useAuthStore()`,
 * and Pinia stores can only be instantiated after `app.use(pinia)`.
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
