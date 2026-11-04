<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api } from '../api'
const props = defineProps<{ modelValue: string; kind?: 'environment' | 'source_change'; title?: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const defaults = ref('')
const variables = ref<{ name: string; label: string }[]>([])
const preview = ref('')
const busy = ref(false)
const error = ref('')
const resetDialog = ref(false)
const showVariables = ref(false)
watch(() => props.modelValue, () => { preview.value = ''; error.value = '' })
onMounted(async () => {
  try {
    const data = await api<{ default: string; variables: typeof variables.value }>('wake-prompt?kind=' + (props.kind || 'environment'))
    defaults.value = data.default
    variables.value = data.variables
  } catch (exc) { error.value = exc instanceof Error ? exc.message : '加载失败' }
})
async function renderPreview() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    const result = await api<{ text: string }>('wake-prompt/preview', { body: { template: props.modelValue, kind: props.kind || 'environment' } })
    preview.value = result.text
  } catch (exc) { error.value = exc instanceof Error ? exc.message : '预览失败' }
  finally { busy.value = false }
}
function reset() {
  emit('update:modelValue', defaults.value)
  resetDialog.value = false
}
</script>
<template>
  <SCard :title="title || '主智能体本轮提示词'">
    <div class="form-body">
      <slot name="controls" />
      <SFormItem label="Jinja 模板" :for="`wake-prompt-${kind || 'environment'}`">
        <STextarea :id="`wake-prompt-${kind || 'environment'}`" :model-value="modelValue" :rows="14" :maxlength="20000" required
          placeholder="{{ time.now }}" @update:model-value="emit('update:modelValue', $event)" />
      </SFormItem>
      <div class="wake-prompt-actions">
        <SButton type="button" :loading="busy" @click="renderPreview">预览</SButton>
        <SButton type="button" @click="showVariables = !showVariables">{{ showVariables ? '收起变量' : '模板变量' }}</SButton>
        <SButton type="button" :disabled="!defaults" @click="resetDialog = true">重置为默认</SButton>
      </div>
      <span v-if="error" class="form-error" role="alert">{{ error }}</span>
      <STable v-if="showVariables">
        <thead><tr><th>变量</th><th>含义</th></tr></thead>
        <tbody><tr v-for="variable in variables" :key="variable.name"><td class="mono">{{ variable.name }}</td><td>{{ variable.label }}</td></tr></tbody>
      </STable>
      <div v-if="preview" class="wake-prompt-preview"><strong>渲染结果</strong><pre>{{ preview }}</pre></div>
    </div>
    <SDialog :open="resetDialog" :title="`确认重置${title || '本轮提示词'}`" @close="resetDialog = false">
      <template #footer>
        <SButton type="button" @click="resetDialog = false">取消</SButton>
        <SButton type="button" variant="danger" @click="reset">确认重置</SButton>
      </template>
    </SDialog>
  </SCard>
</template>
<style scoped>
.wake-prompt-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.wake-prompt-preview { display: grid; gap: 8px; font-size: 12px; }
.wake-prompt-preview pre { margin: 0; padding: 14px; border-radius: 10px; background: var(--surface-alt); color: var(--ink); white-space: pre-wrap; overflow-wrap: anywhere; font: 12px/1.8 var(--mono); }
</style>
