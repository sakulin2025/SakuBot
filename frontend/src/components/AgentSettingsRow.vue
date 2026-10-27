<script setup lang="ts">
import { ref, computed } from 'vue'
import type { AgentInfo } from '../types'
import { api } from '../api'
import { useConsole } from '../stores/console'
import UiBadge from './UiBadge.vue'
const props = defineProps<{ agent: AgentInfo }>()
const store = useConsole()
const busy = ref(false)
const error = ref('')
const models = computed(
  () =>
    store.config?.models.filter(
      (m) =>
        m.enabled &&
        m.capabilities.text &&
        store.config?.providers.some((p) => p.id === m.provider_id && p.enabled),
    ) || [],
)
async function change(field: 'persona_id' | 'model_id', event: Event) {
  const input = event.target as HTMLSelectElement
  busy.value = true
  error.value = ''
  try {
    await api('agents/' + encodeURIComponent(props.agent.id), {
      method: 'PATCH',
      body: { [field]: input.value },
    })
    await store.refresh()
  } catch {
    input.value = props.agent[field]
    error.value = '更新失败'
  } finally {
    busy.value = false
  }
}
async function toggle(value: boolean) {
  busy.value = true
  error.value = ''
  try {
    await store.setMainEnabled(value)
  } catch {
    error.value = '更新失败'
  } finally {
    busy.value = false
  }
}
async function action(kind: 'reset' | 'clear-context') {
  busy.value = true
  error.value = ''
  try {
    await api('agents/' + encodeURIComponent(props.agent.id) + '/' + kind, { method: 'POST' })
    await store.refresh()
  } catch {
    error.value = kind === 'reset' ? '重置失败' : '清空失败'
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <tr :class="{ 'main-agent-row': agent.id === 'main' }">
    <td>
      <strong>{{ agent.name }}</strong>
      <span class="cell-sub mono">{{ agent.id }}</span>
      <span v-if="error" class="form-error">{{ error }}</span>
    </td>
    <td>
      {{
        agent.plugin_id
          ? store.plugins.find((p) => p.name === agent.plugin_id)?.label || agent.plugin_id
          : '核心'
      }}
    </td>
    <td>
      <span v-if="agent.persona_mode === 'managed'">自管理</span>
      <SSelect
        v-else
        :value="agent.persona_id"
        :aria-label="agent.name + ' 人格'"
        :disabled="busy"
        @change="change('persona_id', $event)"
      >
        <option value="">{{ agent.plugin_persona_id ? '插件人格' : '默认' }}</option>
        <option
          v-if="agent.persona_id && !store.personas.some((p) => p.id === agent.persona_id)"
          :value="agent.persona_id"
        >
          {{ agent.persona_id }} · 不可用
        </option>
        <option v-for="persona in store.personas" :key="persona.id" :value="persona.id">
          {{ persona.name }}
        </option>
      </SSelect>
      <span v-if="agent.persona_mode !== 'managed'" class="cell-sub">{{ agent.persona_name }}</span>
    </td>
    <td>
      <SSelect
        :value="agent.model_id"
        :aria-label="agent.name + ' 模型'"
        :disabled="busy"
        @change="change('model_id', $event)"
      >
        <option value="">默认</option>
        <option v-if="agent.model_id && !models.some((m) => m.id === agent.model_id)" :value="agent.model_id">
          {{ agent.model_id }} · 不可用
        </option>
        <option v-for="model in models" :key="model.id" :value="model.id">
          {{ model.name || model.model_id }}
        </option>
      </SSelect>
      <span class="cell-sub">{{ agent.model_name }}</span>
    </td>
    <td>
      <UiBadge
        :status="agent.resetting ? 'running' : agent.busy ? 'running' : agent.ready ? 'done' : 'pending'"
        :label="agent.resetting ? '重置中' : agent.busy ? '运行中' : agent.ready ? '就绪' : '待配置'"
      />
    </td>
    <td>
      <SSwitch
        v-if="agent.id === 'main'"
        :model-value="agent.enabled"
        :disabled="busy || store.saving || (!agent.ready && !store.config?.enabled)"
        aria-label="主 Agent"
        @change="toggle"
      />
      <span v-else class="subtle">—</span>
    </td>
    <td>
      <div v-if="agent.id !== 'main'" class="row-actions">
        <SButton
          class="text-button"
          :disabled="busy || agent.busy || agent.resetting"
          @click="action('clear-context')"
        >
          清空上下文
        </SButton>
        <SButton class="text-button" :disabled="busy || agent.resetting" @click="action('reset')">
          重置
        </SButton>
      </div>
      <span v-else class="subtle">—</span>
    </td>
  </tr>
</template>
