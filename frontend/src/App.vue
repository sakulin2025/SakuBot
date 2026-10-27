<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useConsole } from './stores/console'
import AppShell from './components/AppShell.vue'
import UiIcon from './components/UiIcon.vue'
import SecretInput from './components/SecretInput.vue'
const store = useConsole()
const token = ref('')
const loading = ref(true)
const submitting = ref(false)
const failed = ref(false)
let interval: ReturnType<typeof setInterval>
const unauthorized = () => store.logout()
async function login() {
  submitting.value = true
  failed.value = false
  try {
    await store.login(token.value)
    token.value = ''
  } catch {
    failed.value = true
  } finally {
    submitting.value = false
  }
}
onMounted(async () => {
  window.addEventListener('sakubot-unauthorized', unauthorized)
  const saved = sessionStorage.getItem('sakubot-token')
  if (saved) {
    try {
      await store.login(saved)
    } catch {
      /* Show login. */
    }
  }
  loading.value = false
  interval = setInterval(() => {
    if (store.authenticated && !document.hidden) store.refreshStatus().catch(() => {})
  }, 5000)
})
onUnmounted(() => {
  clearInterval(interval)
  window.removeEventListener('sakubot-unauthorized', unauthorized)
})
</script>
<template>
  <div v-if="loading" class="boot-screen">
    <span class="brand-logo">S</span>
    <UiIcon name="loading" class="spinning" />
  </div>
  <div v-else-if="!store.authenticated" class="login-page">
    <div class="login-decoration"></div>
    <form class="login-card" @submit.prevent="login">
      <div class="login-brand">
        <span class="brand-logo">S</span>
        <span>SakuBot</span>
      </div>
      <h1>登录控制台</h1>
      <div class="field">
        <label for="admin-token">管理令牌</label>
        <SecretInput id="admin-token" v-model="token" />
      </div>
      <span v-if="failed" class="form-error" role="alert">登录失败</span>
      <SButton class="button primary full-width" :disabled="submitting || !token.trim()">
        <UiIcon v-if="submitting" name="loading" class="spinning" :size="17" />
        登录
        <UiIcon v-if="!submitting" name="arrow" :size="17" />
      </SButton>
    </form>
  </div>
  <AppShell v-else>
    <RouterView v-slot="{ Component, route }">
      <Transition name="s-page" mode="out-in">
        <div :key="route.path" class="route-surface"><component :is="Component" /></div>
      </Transition>
    </RouterView>
  </AppShell>
  <Transition name="toast">
    <div v-if="store.notice" class="toast-message" :class="{ error: store.notice.error }" role="status">
      <UiIcon :name="store.notice.error ? 'close' : 'complete'" :size="18" />
      {{ store.notice.text }}
    </div>
  </Transition>
</template>
