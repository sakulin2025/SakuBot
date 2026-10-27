<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { api } from '../api'
import { useConsole } from '../stores/console'
import WorkbenchField from '../plugin-sdk/WorkbenchField.vue'
import type { PluginInfo } from '../types'
const props = defineProps<{ plugin: PluginInfo | null }>()
const emit = defineEmits<{ close: [] }>()
const store = useConsole()
const fields = ref<any[]>([]),
  values = reactive<Record<string, any>>({}),
  configured = ref<Record<string, boolean>>({})
const loading = ref(false),
  saving = ref(false),
  error = ref(''),
  connection = ref(false)
const form = ref<HTMLFormElement>()
let revision = 0
watch(
  () => props.plugin,
  async (plugin) => {
    const current = ++revision
    fields.value = []
    error.value = ''
    Object.keys(values).forEach((k) => delete values[k])
    configured.value = {}
    if (!plugin) return
    loading.value = true
    try {
      const result = await api<any>('plugins/' + plugin.name + '/settings')
      if (current !== revision) return
      fields.value = result.fields
      connection.value = result.requires_connection
      for (const f of result.fields) {
        values[f.key] = result.values[f.key]
        configured.value[f.key] = !!result.values[f.key + '_configured']
      }
    } catch (e) {
      if (current === revision) error.value = e instanceof Error ? e.message : '设置加载失败'
    } finally {
      if (current === revision) loading.value = false
    }
  },
)
async function save() {
  if (!props.plugin || saving.value || !form.value?.reportValidity()) return
  saving.value = true
  error.value = ''
  try {
    const body = Object.fromEntries(
      fields.value.map((f) => [f.key, f.type === 'number' ? Number(values[f.key]) : values[f.key]]),
    )
    await api('plugins/' + props.plugin.name + '/settings', { method: 'PUT', body })
    await store.refresh()
    store.toast('设置已保存')
    emit('close')
  } catch (e) {
    error.value = e instanceof Error ? e.message : '设置保存失败'
  } finally {
    saving.value = false
  }
}
</script>
<template>
  <SDialog :open="!!plugin" :title="(plugin?.label || '') + '设置'" wide @close="!saving && emit('close')">
    <SCard v-if="loading" :loading="true" class="settings-loading" />
    <form v-else ref="form" id="plugin-settings-form" @submit.prevent="save">
      <fieldset class="settings-fields" :disabled="saving">
        <WorkbenchField
          v-for="field in fields"
          :key="field.key"
          v-model="values[field.key]"
          :field="field"
          :options="field.options"
          :configured="configured[field.key]"
        />
      </fieldset>
    </form>
    <div v-if="error" class="settings-error" role="alert">{{ error }}</div>
    <template #footer>
      <SButton :disabled="saving" @click="emit('close')">取消</SButton>
      <SButton
        variant="primary"
        form="plugin-settings-form"
        type="submit"
        :disabled="loading || !fields.length"
        :loading="saving"
      >
        {{ saving && connection ? '正在验证' : connection ? '验证并保存' : '保存设置' }}
      </SButton>
    </template>
  </SDialog>
</template>
<style scoped>
.settings-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 24px 28px;
  border: 0;
  padding: 4px 0;
  margin: 0;
  min-width: 0;
}
.settings-loading {
  height: 140px;
  border: 0;
  box-shadow: none;
}
.settings-error {
  margin-top: 20px;
  padding: 12px 15px;
  border: 1px solid #c67b8733;
  border-radius: 10px;
  background: #fff6f7;
  color: var(--negative);
  font-size: 13px;
  line-height: 1.7;
}
@media (max-width: 700px) {
  .settings-fields {
    grid-template-columns: 1fr;
  }
}
</style>
