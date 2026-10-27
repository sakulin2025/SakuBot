<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api } from '../api'
import { useConsole } from '../stores/console'
import AgentSettingsRow from '../components/AgentSettingsRow.vue'
import UiIcon from '../components/UiIcon.vue'
const store = useConsole()
const query = ref('')
const plugin = ref('')
const busy = ref(false)
const error = ref('')
let timer: ReturnType<typeof setInterval> | undefined
const plugins = computed(() => [...new Set(store.agents.filter((a) => a.plugin_id).map((a) => a.plugin_id))])
const agents = computed(() =>
  store.agents.filter(
    (a) =>
      a.id === 'main' ||
      ((!plugin.value || a.plugin_id === plugin.value) &&
        (a.name + a.id).toLowerCase().includes(query.value.toLowerCase())),
  ),
)
const models = computed(
  () =>
    store.config?.models.filter(
      (m) =>
        m.enabled &&
        m.capabilities.text &&
        store.config?.providers.some((p) => p.id === m.provider_id && p.enabled),
    ) || [],
)
async function saveDefault(field: 'persona_id' | 'model_id', event: Event) {
  const input = event.target as HTMLSelectElement
  busy.value = true
  error.value = ''
  try {
    await api('agent-defaults', { method: 'PATCH', body: { [field]: input.value } })
    await store.refresh()
  } catch {
    input.value = store.agentDefaults[field]
    error.value = '更新失败'
  } finally {
    busy.value = false
  }
}
onMounted(() => {
  store.refreshAgents().catch(() => {
    error.value = '加载失败'
  })
  timer = setInterval(() => {
    if (!document.hidden) store.refreshAgents().catch(() => {})
  }, 3000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
defineProps<{ embedded?: boolean }>()
</script>
<template>
  <SPageHeader v-if="!embedded" title="Agent 管理" :count="store.agents.length">
    <RouterLink to="/personas" class="button">
      <UiIcon name="persona" :size="16" />
      管理人格
    </RouterLink>
  </SPageHeader>
  <SCard class="surface agents-table-surface">
    <div class="agent-defaults-bar">
      <div class="compact-field">
        <label for="default-persona">默认人格</label>
        <SSelect
          id="default-persona"
          :value="store.agentDefaults.persona_id"
          :disabled="busy"
          @change="saveDefault('persona_id', $event)"
        >
          <option v-for="persona in store.personas" :key="persona.id" :value="persona.id">
            {{ persona.name }}
          </option>
        </SSelect>
      </div>
      <div class="compact-field">
        <label for="default-model">默认模型</label>
        <SSelect
          id="default-model"
          :value="store.agentDefaults.model_id"
          :disabled="busy"
          @change="saveDefault('model_id', $event)"
        >
          <option value="">未选择</option>
          <option v-for="model in models" :key="model.id" :value="model.id">
            {{ model.name || model.model_id }}
          </option>
        </SSelect>
      </div>
      <span v-if="error" class="form-error">{{ error }}</span>
    </div>
    <div class="table-toolbar">
      <div class="search-field">
        <UiIcon name="search" :size="17" />
        <SInput v-model="query" placeholder="搜索 Agent" aria-label="搜索 Agent" />
      </div>
      <SSelect v-model="plugin" aria-label="来源插件">
        <option value="">全部插件</option>
        <option v-for="id in plugins" :key="id" :value="id">
          {{ store.plugins.find((p) => p.name === id)?.label || id }}
        </option>
      </SSelect>
    </div>
    <div class="table-scroll">
      <STable class="data-table agents-table">
        <thead>
          <tr>
            <th>Agent</th>
            <th>来源</th>
            <th>人格</th>
            <th>模型</th>
            <th>状态</th>
            <th>启用</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody><AgentSettingsRow v-for="agent in agents" :key="agent.id" :agent="agent" /></tbody>
      </STable>
    </div>
  </SCard>
</template>
