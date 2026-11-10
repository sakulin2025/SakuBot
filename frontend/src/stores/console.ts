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
import { clearToken, rememberToken, setSessionToken } from '../credentials'

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
  let epoch = 0
  const flights = new Map<string, Promise<void>>()
  function single(key: string, work: (generation: number) => Promise<void>) {
    const generation = epoch
    const name = generation + ':' + key
    const existing = flights.get(name)
    if (existing) return existing
    const promise = work(generation).finally(() => { if (flights.get(name) === promise) flights.delete(name) })
    flights.set(name, promise)
    return promise
  }
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
  function refreshStatus() {
    return single('status', async generation => {
      const data = await api<Status>('status')
      if (generation !== epoch) return
      status.value = data
      if (config.value) config.value.enabled = data.enabled
      agents.value = agents.value.map(agent => ({ ...agent, ...data.agent_states?.[agent.id] }))
      plugins.value = plugins.value.map(plugin => ({ ...plugin, ...data.plugin_states?.[plugin.name] }))
      const updates: Promise<unknown>[] = []
      if (data.registry_revision !== revision.value) {
        updates.push(refreshRegistry(), api<Setup>('setup').then(value => { if (generation === epoch) setup.value = value }))
      }
      if (data.agents_revision !== agentRevision.value) updates.push(refreshAgents())
      await Promise.all(updates)
    })
  }
  function refreshAgents() {
    return single('agents', async generation => {
      const data = await api<AgentCatalog>('agents')
      if (generation !== epoch) return
      agents.value = data.items
      const main = data.items.find(item => item.id === 'main')
      if (config.value && main) config.value.enabled = main.enabled
      agentDefaults.value = data.defaults
      agentRevision.value = data.revision
    })
  }
  function refreshRegistry() {
    return single('registry', async generation => {
      const registry = await api<PluginRegistry>('plugin-registry')
      if (generation !== epoch) return
      const changed = JSON.stringify(pages.value) !== JSON.stringify(registry.pages)
      pages.value = registry.pages
      plugins.value = registry.plugins
      revision.value = registry.revision
      if (changed) await synchronizePluginRoutes(registry.pages)
    })
  }
  function refresh() {
    return single('refresh', async generation => {
      const [, settings, onboarding, people] = await Promise.all([
        refreshStatus(), api<Configuration>('config'), api<Setup>('setup'), api<Persona[]>('personas'),
        refreshRegistry(), refreshAgents(),
      ])
      if (generation !== epoch) return
      config.value = settings
      setup.value = onboarding
      personas.value = people
    })
  }
  async function togglePlugin(id: string, enabled: boolean) {
    saving.value = true
    try {
      await api('plugins/' + encodeURIComponent(id), { method: 'PATCH', body: { enabled } })
      epoch++
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
    token = token.trim()
    const generation = ++epoch
    setSessionToken(token)
    try {
      await refresh()
      if (generation !== epoch) return
      rememberToken(token)
      authenticated.value = true
    } catch (error) {
      if (generation === epoch) logout(false)
      throw error
    }
  }
  function logout(forget = true) {
    epoch++
    clearToken(forget)
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
      epoch++
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
      epoch++
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
