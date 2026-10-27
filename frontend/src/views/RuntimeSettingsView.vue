<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { api, ApiError } from '../api'
import { useConsole } from '../stores/console'
import SecretInput from '../components/SecretInput.vue'
const store = useConsole()
const values = reactive({
  max_steps: 16,
  context_chars: 48000,
  agent_concurrency: 3,
  compression_enabled: true,
  threshold: 80,
  image_model_id: '',
})
const capabilityNames: Record<string, string> = {
  text: '文字',
  image: '图片',
  video: '视频',
  file: '文件',
  audio: '语音',
  stream: '流式',
  tool: '工具调用',
  lifecycle: '生命周期',
}
interface ConversationSource {
  id: string
  name: string
  plugin_id: string
  available: boolean
  reason: string
  capabilities: string[]
}
const sources = ref<ConversationSource[]>([])
const currentSource = ref('')
const routing = reactive<{ mode: 'broadcast' | 'intelligent'; targets: string[]; tool_events: boolean }>({
  mode: 'intelligent',
  targets: [],
  tool_events: false,
})
const routingBusy = ref(false)
const routingDirty = ref(false)
const routingError = ref('')
let sourceTimer: ReturnType<typeof setInterval> | undefined
async function loadSources() {
  try {
    const data = await api<{ items: ConversationSource[]; current: string }>('conversation-sources')
    sources.value = data.items
    currentSource.value = data.current
  } catch {
    /* Keep last known source list. */
  }
}
watch(
  () => store.config?.conversation,
  (value) => {
    if (value && !routingDirty.value) Object.assign(routing, { ...value, targets: [...value.targets] })
  },
  { immediate: true },
)
async function saveRouting() {
  routingBusy.value = true
  routingError.value = ''
  try {
    const result = await api<{ config: NonNullable<typeof store.config> }>('config', {
      method: 'PATCH',
      body: { section: 'conversation', values: { conversation: routing } },
    })
    routingDirty.value = false
    store.config = result.config
    store.toast('已保存')
  } catch {
    routingError.value = '保存失败'
  } finally {
    routingBusy.value = false
  }
}
onMounted(() => {
  void loadSources()
  sourceTimer = setInterval(loadSources, 3000)
})
onUnmounted(() => clearInterval(sourceTimer))
const clearDialog = ref(false)
const clearConfirmation = ref('')
const clearBusy = ref(false)
const clearError = ref('')
function openClearDialog() {
  clearConfirmation.value = ''
  clearError.value = ''
  clearDialog.value = true
}
function closeClearDialog() {
  if (!clearBusy.value) clearDialog.value = false
}
async function clearContext() {
  if (clearConfirmation.value !== '清除' || clearBusy.value) return
  clearBusy.value = true
  clearError.value = ''
  try {
    await api('chat/clear-context', { body: { confirmation: clearConfirmation.value } })
    clearDialog.value = false
    store.toast('主对话上下文已清除')
  } catch (exc) {
    clearError.value =
      exc instanceof ApiError && exc.status === 409 ? '主对话正在运行或有待处理消息' : '清除失败'
  } finally {
    clearBusy.value = false
  }
}
const token = reactive({ value: '', confirmation: '' })
const tokenBusy = ref(false)
const tokenError = ref('')
const error = ref('')
const dirty = ref(false)
function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
const imageModels = computed(
  () =>
    store.config?.models.filter(
      (m) =>
        m.enabled &&
        m.capabilities.text &&
        m.capabilities.image &&
        store.config?.providers.some((p) => p.id === m.provider_id && p.enabled),
    ) || [],
)
watch(
  () => store.config,
  (config) => {
    if (!config || dirty.value) return
    Object.assign(values, {
      max_steps: config.max_steps,
      context_chars: config.context_chars,
      agent_concurrency: config.agent_concurrency,
      compression_enabled: config.compression_enabled,
      threshold: config.compression_threshold * 100,
      image_model_id: config.message_processing.image_model_id,
    })
  },
  { immediate: true },
)
async function save() {
  error.value = ''
  try {
    await store.save('settings', {
      max_steps: values.max_steps,
      context_chars: values.context_chars,
      agent_concurrency: values.agent_concurrency,
      compression_enabled: values.compression_enabled,
      compression_threshold: values.threshold / 100,
      message_processing: { image_model_id: values.image_model_id, speech_recognition: 'unimplemented' },
    })
    dirty.value = false
  } catch {
    error.value = '保存失败'
  }
}
async function changeToken() {
  tokenError.value = ''
  if (token.value !== token.confirmation) {
    tokenError.value = '两次输入不一致'
    return
  }
  tokenBusy.value = true
  try {
    await api('admin-token', { method: 'PATCH', body: { token: token.value } })
    sessionStorage.setItem('sakubot-token', token.value)
    token.value = ''
    token.confirmation = ''
    store.toast('令牌已更新')
  } catch (exc) {
    tokenError.value = exc instanceof ApiError && exc.status === 400 ? '令牌格式不正确' : '更新失败'
  } finally {
    tokenBusy.value = false
  }
}
</script>
<template>
  <div class="runtime-layout">
    <SPageHeader title="运行设置">
      <div class="settings-shortcuts">
        <SButton type="button" variant="text" @click="scrollTo('execution')">执行参数</SButton>
        <SButton type="button" variant="text" @click="scrollTo('compression')">上下文压缩</SButton>
        <SButton type="button" variant="text" @click="scrollTo('processing')">消息处理</SButton>
        <SButton type="button" variant="text" @click="scrollTo('conversation')">主对话</SButton>
        <SButton type="button" variant="text" @click="scrollTo('security')">管理令牌</SButton>
        <SButton type="button" variant="text" @click="scrollTo('danger')">危险操作</SButton>
      </div>
    </SPageHeader>
    <SForm id="runtime-settings" @submit="save" @input="dirty = true" @change="dirty = true">
      <div class="settings-grid">
        <SCard id="execution" title="执行参数" class="settings-section">
          <div class="form-body">
            <div class="form-row">
              <SFormItem label="每轮最大工具调用轮数" for="max-steps">
                <SInput
                  id="max-steps"
                  v-model.number="values.max_steps"
                  type="number"
                  min="1"
                  max="64"
                  required
                />
              </SFormItem>
              <SFormItem label="Agent 最大并发数" for="concurrency">
                <SInput
                  id="concurrency"
                  v-model.number="values.agent_concurrency"
                  type="number"
                  min="1"
                  max="8"
                  required
                />
              </SFormItem>
            </div>
            <SFormItem label="上下文字符预算" for="context-budget">
              <SInput
                id="context-budget"
                v-model.number="values.context_chars"
                type="number"
                min="8000"
                max="200000"
                required
              />
            </SFormItem>
          </div>
        </SCard>
        <SCard id="compression" title="上下文压缩" class="settings-section">
          <div class="form-body">
            <div class="settings-row">
              <label id="compression-label">自动压缩</label>
              <SSwitch
                v-model="values.compression_enabled"
                aria-labelledby="compression-label"
                @change="dirty = true"
              />
            </div>
            <SFormItem label="上下文压缩触发比例 (%)" for="compression-threshold">
              <SInput
                id="compression-threshold"
                v-model.number="values.threshold"
                type="number"
                min="10"
                max="95"
                step="1"
                required
                :disabled="!values.compression_enabled"
              />
            </SFormItem>
          </div>
        </SCard>
        <SCard id="processing" title="消息处理" class="settings-section">
          <div class="form-body">
            <SFormItem label="图片解读模型" for="image-model">
              <SSelect id="image-model" v-model="values.image_model_id">
                <option value="">关闭</option>
                <option v-for="model in imageModels" :key="model.id" :value="model.id">
                  {{ model.name || model.model_id }}
                </option>
              </SSelect>
            </SFormItem>
            <SFormItem label="语音识别" for="speech">
              <SSelect id="speech" disabled><option>未实现</option></SSelect>
            </SFormItem>
          </div>
        </SCard>
      </div>
      <div class="settings-save">
        <span v-if="error" class="form-error">{{ error }}</span>
        <SButton variant="primary" type="submit" :loading="store.saving" icon="check">保存设置</SButton>
      </div>
    </SForm>
    <SCard id="conversation" title="主对话" class="settings-section security-card">
      <SForm
        class="form-body"
        @submit="saveRouting"
        @input="routingDirty = true"
        @change="routingDirty = true"
      >
        <SFormItem label="回复发送方式" for="conversation-mode">
          <SSelect id="conversation-mode" v-model="routing.mode">
            <option value="intelligent">跟随消息来源</option>
            <option value="broadcast">广播至指定对话源</option>
          </SSelect>
        </SFormItem>
        <div class="settings-row">
          <label>网页同步</label>
          <SSwitch :model-value="true" disabled />
        </div>
        <div class="settings-row">
          <label>同步工具调用过程</label>
          <SSwitch v-model="routing.tool_events" @change="routingDirty = true" />
        </div>
        <SFormItem v-if="routing.mode === 'intelligent'" label="当前响应源">
          <span>{{ sources.find((item) => item.id === currentSource)?.name || currentSource || '—' }}</span>
        </SFormItem>
        <STable v-if="sources.length">
          <thead>
            <tr>
              <th v-if="routing.mode === 'broadcast'">接收</th>
              <th>对话源</th>
              <th>插件</th>
              <th>状态</th>
              <th>支持的消息类型</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="source in sources" :key="source.id">
              <td v-if="routing.mode === 'broadcast'">
                <SCheckbox v-model="routing.targets" :value="source.id" @change="routingDirty = true" />
              </td>
              <td>{{ source.name }}</td>
              <td>{{ source.plugin_id }}</td>
              <td :title="source.reason">{{ source.available ? '已连接' : '不可用' }}</td>
              <td>{{ source.capabilities.map((key) => capabilityNames[key] || key).join(' · ') || '—' }}</td>
            </tr>
          </tbody>
        </STable>
        <SEmpty v-else label="暂无对话源" />
        <div class="settings-save">
          <span v-if="routingError" class="form-error">{{ routingError }}</span>
          <SButton type="submit" variant="primary" :loading="routingBusy">保存</SButton>
        </div>
      </SForm>
    </SCard>
    <SCard id="security" title="管理令牌" class="settings-section security-card">
      <SForm class="form-body security-form" @submit="changeToken">
        <SFormItem label="新令牌" for="new-admin-token" required>
          <SecretInput
            id="new-admin-token"
            v-model="token.value"
            required
            :maxlength="256"
            pattern="[!-~]+"
          />
        </SFormItem>
        <SFormItem label="确认令牌" for="confirm-admin-token" :error="tokenError" required>
          <SecretInput
            id="confirm-admin-token"
            v-model="token.confirmation"
            required
            :maxlength="256"
            pattern="[!-~]+"
          />
        </SFormItem>
        <SButton variant="primary" type="submit" :loading="tokenBusy" icon="key">修改令牌</SButton>
      </SForm>
    </SCard>
    <SCard id="danger" title="危险操作" class="settings-section security-card danger-zone">
      <div class="form-body">
        <SButton type="button" variant="danger" @click="openClearDialog">清除主对话上下文</SButton>
      </div>
    </SCard>
    <SDialog :open="clearDialog" title="确认清除主对话上下文" @close="closeClearDialog">
      <SForm id="clear-main-context" @submit="clearContext">
        <SFormItem label="输入「清除」" for="clear-confirmation" :error="clearError" required>
          <SInput
            id="clear-confirmation"
            v-model="clearConfirmation"
            autocomplete="off"
            :disabled="clearBusy"
            required
          />
        </SFormItem>
      </SForm>
      <template #footer>
        <SButton type="button" :disabled="clearBusy" @click="closeClearDialog">取消</SButton>
        <SButton
          type="submit"
          form="clear-main-context"
          variant="danger"
          :loading="clearBusy"
          :disabled="clearConfirmation !== '清除'"
        >
          确认清除
        </SButton>
      </template>
    </SDialog>
  </div>
</template>

<style scoped>
.danger-zone {
  border-color: var(--danger, #dc5c62);
}
</style>
