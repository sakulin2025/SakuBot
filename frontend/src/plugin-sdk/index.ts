import { createApp } from 'vue'
import type { Component } from 'vue'
import { formatDate, parseJson, ApiError } from '../api'
import '../style.css'
import './plugin.css'
import SakuUI from '../components/ui'
export * from '../components/ui'

export { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
export { formatDate, parseJson, ApiError }
export { default as UiIcon } from '../components/UiIcon.vue'
export { default as UiBadge } from '../components/UiBadge.vue'
export { default as UiModal } from '../components/UiModal.vue'
export { default as UiEmpty } from '../components/UiEmpty.vue'
export type { Memory, Person, Task, Schedule, AgentInfo, AgentCatalog } from '../types'

interface Host {
  token: string
  plugin: string
  page: string
  main_session: string
  api_version: number
}
let host: Host | null = null
const ready = new Promise<Host>((resolve) => {
  window.addEventListener('message', (event) => {
    if (event.source !== window.parent || event.origin !== window.location.origin) return
    if (event.data?.type === 'sakubot:host' && typeof event.data.token === 'string') {
      host = event.data
      resolve(event.data)
    }
  })
})
function message(type: string, payload: Record<string, unknown> = {}) {
  window.parent.postMessage({ type, ...payload }, window.location.origin)
}
async function request<T>(path: string, body?: unknown, method?: string): Promise<T> {
  const context = await ready
  const response = await fetch(path, {
    method: method || (body === undefined ? 'GET' : 'POST'),
    headers: { Authorization: 'Bearer ' + context.token, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (response.status === 401) message('sakubot:unauthorized')
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new ApiError(
      response.status,
      typeof data.detail === 'string' ? data.detail : data.error || undefined,
    )
  }
  return response.json()
}
export function usePluginHost() {
  return {
    upload: async <T>(path: string, file: File): Promise<T> => {
      const context = await ready
      const response = await fetch('/api/extensions/' + context.plugin + '/' + path.replace(/^\//, ''), {
        method: 'PUT',
        headers: { Authorization: 'Bearer ' + context.token, 'Content-Type': 'application/octet-stream' },
        body: file,
      })
      if (response.status === 401) message('sakubot:unauthorized')
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new ApiError(
          response.status,
          typeof data.detail === 'string' ? data.detail : data.error || undefined,
        )
      }
      return response.json()
    },
    download: async (path: string, name: string) => {
      const context = await ready
      const response = await fetch('/api/extensions/' + context.plugin + '/' + path.replace(/^\//, ''), {
        headers: { Authorization: 'Bearer ' + context.token },
      })
      if (response.status === 401) message('sakubot:unauthorized')
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new ApiError(
          response.status,
          typeof data.detail === 'string' ? data.detail : data.error || undefined,
        )
      }
      const url = URL.createObjectURL(await response.blob())
      const link = document.createElement('a')
      link.href = url
      link.download = name
      link.click()
      setTimeout(() => URL.revokeObjectURL(url), 30000)
    },
    api: async <T>(path: string, body?: unknown, method?: string) => {
      const context = await ready
      return request<T>('/api/extensions/' + context.plugin + '/' + path.replace(/^\//, ''), body, method)
    },
    coreApi: <T>(path: string, body?: unknown, method?: string) =>
      request<T>('/api/' + path.replace(/^\//, ''), body, method),
    toast: (text: string, error = false) => message('sakubot:toast', { text, error }),
    navigate: (path: string) => message('sakubot:navigate', { path }),
    refresh: () => message('sakubot:refresh'),
    context: () => host,
  }
}
export async function mountPlugin(component: Component) {
  document.body.classList.add('plugin-document')
  message('sakubot:ready')
  const interval = setInterval(() => {
    if (!host) message('sakubot:ready')
  }, 300)
  await ready
  clearInterval(interval)
  createApp(component).use(SakuUI).mount('#app')
}

export { default as PluginWorkbench } from './PluginWorkbench.vue'
