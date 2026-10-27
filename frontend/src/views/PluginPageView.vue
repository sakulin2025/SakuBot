<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import type { PluginPage } from '../types'
import { useConsole } from '../stores/console'
const props = defineProps<{ page: PluginPage }>()
const frame = ref<HTMLIFrameElement>()
const store = useConsole()
const router = useRouter()
function host() {
  frame.value?.contentWindow?.postMessage(
    {
      type: 'sakubot:host',
      token: sessionStorage.getItem('sakubot-token') || '',
      plugin: props.page.plugin_id,
      page: props.page.id,
      main_session: store.status?.main_session || '',
      api_version: 1,
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
      store.logout()
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
onMounted(() => window.addEventListener('message', receive))
onUnmounted(() => window.removeEventListener('message', receive))
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
