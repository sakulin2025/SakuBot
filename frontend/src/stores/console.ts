import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '../api'
import type {
  Configuration,
  Setup,
  Status,
  PluginRegistry,
  PluginPage,
  PluginInfo,
  Persona,
  AgentCatalog,
  AgentInfo,
} from '../types'
import { synchronizePluginRoutes } from '../plugin-routes'

export const useConsole = defineStore('console', () => {
  const authenticated = ref(false)
  const status = ref<Status | null>(null)
  const config = ref<Configuration | null>(null)
  const setup = ref<Setup | null>(null)
  const pages = ref<PluginPage[]>([])
  const plugins = ref<PluginInfo[]>([])
  const personas = ref<Persona[]>([])
  const agents = ref<AgentInfo[]>([])
  const agentDefaults = ref({
    persona_id: '',
    model_id: '',
  })
  const agentRevision = ref('')
  const revision = ref('')
  const saving = ref(false)
  const notice = ref<{ text: string; error: boolean } | null>(null)
  let toastTimer: ReturnType<typeof setTimeout>
  const pending = computed(() => status.value?.queue.find((item) => item.status === 'pending')?.count || 0)
  const requiredSteps = computed(() =>
    Object.keys(setup.value?.completed || {}).filter((key) => !setup.value?.optional?.includes(key)),
  )
  const completed = computed(() => requiredSteps.value.filter((key) => setup.value?.completed[key]).length)
  const ready = computed(
    () => requiredSteps.value.length > 0 && completed.value === requiredSteps.value.length,
  )

  function toast(text: string, error = false) {
    notice.value = { text, error }
    clearTimeout(toastTimer)
    toastTimer = setTimeout(() => (notice.value = null), 3500)
  }
  async function refreshStatus() {
    status.value = await api<Status>('status')
    if (config.value) config.value.enabled = status.value.enabled
    if (status.value.registry_revision !== revision.value) {
      await refreshRegistry()
      setup.value = await api<Setup>('setup')
    }
    await refreshAgents()
  }
  async function refreshAgents() {
    const data = await api<AgentCatalog>('agents')
    agents.value = data.items
    const main = data.items.find((item) => item.id === 'main')
    if (config.value && main) config.value.enabled = main.enabled
    agentDefaults.value = data.defaults
    agentRevision.value = data.revision
  }
  async function refreshRegistry() {
    const registry = await api<PluginRegistry>('plugin-registry')
    pages.value = registry.pages
    plugins.value = registry.plugins
    revision.value = registry.revision
    await synchronizePluginRoutes(registry.pages)
  }
  async function refresh() {
    const values = await Promise.all([
      api<Status>('status'),
      api<Configuration>('config'),
      api<Setup>('setup'),
      api<Persona[]>('personas'),
    ])
    ;[status.value, config.value, setup.value, personas.value] = values
    await Promise.all([refreshRegistry(), refreshAgents()])
  }
  async function togglePlugin(id: string, enabled: boolean) {
    saving.value = true
    try {
      await api('plugins/' + encodeURIComponent(id), { method: 'PATCH', body: { enabled } })
      await refresh()
      toast(enabled ? '已启用' : '已停用')
    } catch (error) {
      toast('切换失败', true)
      throw error
    } finally {
      saving.value = false
    }
  }
  async function login(token: string) {
    sessionStorage.setItem('sakubot-token', token.trim())
    try {
      await refresh()
      authenticated.value = true
    } catch (error) {
      logout()
      throw error
    }
  }
  function logout() {
    sessionStorage.removeItem('sakubot-token')
    authenticated.value = false
    status.value = null
    config.value = null
    setup.value = null
    pages.value = []
    plugins.value = []
    personas.value = []
    agents.value = []
    agentRevision.value = ''
    agentDefaults.value = {
      persona_id: '',
      model_id: '',
    }
    revision.value = ''
    void synchronizePluginRoutes([])
  }
  async function save(section: string, values: Record<string, unknown>) {
    saving.value = true
    try {
      await api('config', { method: 'PATCH', body: { section, values } })
      await refresh()
      toast('已保存')
    } catch (error) {
      toast('保存失败', true)
      throw error
    } finally {
      saving.value = false
    }
  }
  async function setMainEnabled(enabled: boolean) {
    saving.value = true
    try {
      await api('agents/main/state', { method: 'PATCH', body: { enabled } })
      await refresh()
    } finally {
      saving.value = false
    }
  }
  async function activate() {
    if (!config.value) return
    await setMainEnabled(!config.value.enabled)
  }
  return {
    agents,
    agentDefaults,
    refreshAgents,
    pages,
    plugins,
    personas,
    refreshRegistry,
    togglePlugin,
    authenticated,
    status,
    config,
    setup,
    saving,
    notice,
    pending,
    completed,
    requiredSteps,
    ready,
    toast,
    refreshStatus,
    refresh,
    login,
    logout,
    save,
    activate,
    setMainEnabled,
  }
})
