<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import type { PluginPage } from '../types'
import { useConsole } from '../stores/console'
import { sessionToken, unauthorized } from '../credentials'
const props = defineProps<{ page: PluginPage }>()
const frame = ref<HTMLIFrameElement>()
const store = useConsole()
const router = useRouter()
function host() {
  try {
    if (frame.value?.contentDocument) frame.value.contentDocument.documentElement.dataset.theme = document.documentElement.dataset.theme
  } catch { /* Plugin pages outside this origin manage their own appearance. */ }
  frame.value?.contentWindow?.postMessage(
    {
      type: 'sakubot:host',
      token: sessionToken(),
      plugin: props.page.plugin_id,
      page: props.page.id,
      main_session: store.status?.main_session || '',
      api_version: 1,
      theme: document.documentElement.dataset.theme,
    },
    location.origin,
  )
}
function receive(event: MessageEvent) {
  if (event.origin !== location.origin || event.source !== frame.value?.contentWindow) return
  const data = event.data
  if (!data || typeof data !== 'object') return
  switch (data.type) {
    case 'sakubot:ready':
      host()
      break
    case 'sakubot:toast':
      store.toast(String(data.text || ''), Boolean(data.error))
      break
    case 'sakubot:unauthorized':
      unauthorized(typeof data.token === 'string' ? data.token : sessionToken())
      break
    case 'sakubot:refresh':
      store.refresh().catch(() => store.toast('刷新失败', true))
      break
    case 'sakubot:navigate':
      if (typeof data.path === 'string' && data.path.startsWith('/') && !data.path.startsWith('//'))
        router.push(data.path)
      break
  }
}
onMounted(() => { window.addEventListener('message', receive); window.addEventListener('sakubot-token-changed', host); window.addEventListener('sakubot-theme-changed', host) })
onUnmounted(() => { window.removeEventListener('message', receive); window.removeEventListener('sakubot-token-changed', host); window.removeEventListener('sakubot-theme-changed', host) })
</script>
<template>
  <iframe
    ref="frame"
    :key="page.url"
    :src="page.url"
    :title="page.title"
    class="plugin-frame"
    @load="host"
  ></iframe>
</template>
