<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { api, ApiError } from '../api'
import { useConsole } from '../stores/console'
import SecretInput from '../components/SecretInput.vue'
import WakePromptEditor from '../components/WakePromptEditor.vue'
import { rememberToken } from '../credentials'
const store = useConsole()
const values = reactive({
  wake_prompt_template: '',
  max_steps: 16,
  context_chars: 48000,
  agent_concurrency: 3,
  progress_reminder: { enabled: false, tool_threshold: 5, seconds_threshold: 30, mode: 'remind', prompt: '请使用 message_send 向当前主会话源简短说明刚刚完成了什么，以及接下来准备做什么。无需罗列工具，不要泄露当前会话源不应获知的信息。' },
  request_retry: { max_retries: 3, retry_notice: '刚刚开小差了，让我尝试重新集中注意力', exhausted_notice: '（睡着了）', fatal_notice: '没精力理你了…' },
  compression_notice: '稍等，脑子太乱了，给我点时间让我整理一下思绪',
  compression_enabled: true,
  threshold: 80,
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
  trusted: boolean
  reason: string
  capabilities: string[]
}
const sources = ref<ConversationSource[]>([])
const trustBusy = ref<Record<string, boolean>>({})
async function setTrust(sourceId: string, trusted: boolean) {
  if (trustBusy.value[sourceId]) return
  trustBusy.value[sourceId] = true
  try {
    const result = await api<{ items: ConversationSource[]; current: string }>('conversation-sources/trust', {
      method: 'PUT', body: { source_id: sourceId, trusted },
    })
    sources.value = result.items
    currentSource.value = result.current
  } catch (exc) { store.toast(exc instanceof Error ? exc.message : '更新失败', true) }
  finally { trustBusy.value[sourceId] = false }
}
const currentSource = ref('')
const routing = reactive<{ mode: 'intelligent'; targets: string[]; tool_events: boolean; wake_insertion: 'queue' | 'next_boundary' | 'same_source_boundary'; same_source_priority: boolean; untrusted_source_template: string; source_change_enabled: boolean; source_change_mode: 'context' | 'temporary'; source_change_template: string }>({
  mode: 'intelligent',
  targets: [],
  tool_events: false,
  wake_insertion: 'queue',
  same_source_priority: false,
  untrusted_source_template: '',
  source_change_enabled: true,
  source_change_mode: 'context',
  source_change_template: '',
})
const routingDirty = ref(false)
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
const saving = ref(false)
watch(
  () => store.config,
  (config) => {
    if (!config || dirty.value) return
    Object.assign(values, {
      wake_prompt_template: config.wake_prompt_template,
      max_steps: config.max_steps,
      context_chars: config.context_chars,
      agent_concurrency: config.agent_concurrency,
      progress_reminder: { ...values.progress_reminder, ...config.progress_reminder },
      request_retry: { ...values.request_retry, ...config.request_retry },
      compression_notice: config.compression_notice,
      compression_enabled: config.compression_enabled,
      threshold: config.compression_threshold * 100,
    })
  },
  { immediate: true },
)
async function save() {
  if (saving.value || (!dirty.value && !routingDirty.value)) return
  error.value = ''
  saving.value = true
  try {
    if (dirty.value) {
      await store.save('settings', {
        wake_prompt_template: values.wake_prompt_template,
        max_steps: values.max_steps,
        context_chars: values.context_chars,
        agent_concurrency: values.agent_concurrency,
        progress_reminder: { ...values.progress_reminder },
        request_retry: { ...values.request_retry },
        compression_notice: values.compression_notice,
        compression_enabled: values.compression_enabled,
        compression_threshold: values.threshold / 100,
        ...(routingDirty.value ? { conversation: { ...routing, targets: [...routing.targets] } } : {}),
      })
    } else {
      const result = await api<{ config: NonNullable<typeof store.config> }>('config', {
        method: 'PATCH', body: { section: 'conversation', values: { conversation: { ...routing, targets: [...routing.targets] } } },
      })
      store.config = result.config
      store.toast('已保存')
    }
    dirty.value = false
    routingDirty.value = false
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : '保存失败'
  } finally {
    saving.value = false
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
    rememberToken(token.value)
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
    <SForm id="runtime-settings" :disabled="saving" @submit="save">
      <div class="settings-grid" @input="dirty = true" @change="dirty = true">
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
        <WakePromptEditor v-model="values.wake_prompt_template" @update:model-value="dirty = true" />
        <SCard title="模型请求重试" class="settings-section">
          <div class="form-body">
            <SFormItem label="最大重试次数" for="request-retries">
              <SInput id="request-retries" v-model.number="values.request_retry.max_retries" type="number" min="0" max="10" required />
            </SFormItem>
            <SFormItem label="可重试失败提示（仅首次）" for="retry-notice">
              <STextarea id="retry-notice" v-model="values.request_retry.retry_notice" rows="2" maxlength="2000" />
            </SFormItem>
            <SFormItem label="重试次数耗尽提示" for="retry-exhausted">
              <STextarea id="retry-exhausted" v-model="values.request_retry.exhausted_notice" rows="2" maxlength="2000" />
            </SFormItem>
            <SFormItem label="不可重试失败提示" for="retry-fatal">
              <STextarea id="retry-fatal" v-model="values.request_retry.fatal_notice" rows="2" maxlength="2000" />
            </SFormItem>
          </div>
        </SCard>
        <SCard title="汇报进度提醒" class="settings-section">
          <div class="form-body">
            <div class="settings-row">
              <label id="progress-enabled">汇报进度提醒</label>
              <SSwitch v-model="values.progress_reminder.enabled" aria-labelledby="progress-enabled" @change="dirty = true" />
            </div>
            <template v-if="values.progress_reminder.enabled">
              <SFormItem label="提醒工具调用量阈值" for="progress-count">
                <SInput id="progress-count" v-model.number="values.progress_reminder.tool_threshold" type="number" min="1" max="1000" required />
              </SFormItem>
              <SFormItem label="累计工具耗时阈值（秒）" for="progress-seconds">
                <SInput id="progress-seconds" v-model.number="values.progress_reminder.seconds_threshold" type="number" min="1" max="86400" required />
              </SFormItem>
              <SFormItem label="要求模式" for="progress-mode">
                <SSelect id="progress-mode" v-model="values.progress_reminder.mode"><option value="remind">提醒</option><option value="require">强制</option></SSelect>
              </SFormItem>
              <SFormItem label="提示词" for="progress-prompt">
                <STextarea id="progress-prompt" v-model="values.progress_reminder.prompt" :rows="4" maxlength="10000" required />
              </SFormItem>
            </template>
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
            <SFormItem label="压缩提示消息" for="compression-notice">
              <STextarea id="compression-notice" v-model="values.compression_notice" rows="3" maxlength="2000" />
            </SFormItem>
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
      </div>
    <SCard id="conversation" title="主对话" class="settings-section security-card">
      <div
        class="form-body"
        @input="routingDirty = true"
        @change="routingDirty = true"
      >
        <SFormItem label="消息唤醒方式" for="wake-insertion">
          <SSelect id="wake-insertion" v-model="routing.wake_insertion">
            <option value="queue">加入队列</option>
            <option value="next_boundary">在安全位置插入</option>
            <option value="same_source_boundary">同源时在安全位置插入</option>
          </SSelect>
        </SFormItem>
        <div v-if="routing.wake_insertion === 'same_source_boundary'" class="settings-row">
          <label id="same-source-priority-label">同源优先插入</label>
          <SSwitch v-model="routing.same_source_priority" aria-labelledby="same-source-priority-label" @change="routingDirty = true" />
        </div>
        <div class="settings-row">
          <label>同步工具调用过程</label>
          <SSwitch v-model="routing.tool_events" @change="routingDirty = true" />
        </div>
        <SFormItem label="当前响应源">
          <span>{{ sources.find((item) => item.id === currentSource)?.name || currentSource || '—' }}</span>
        </SFormItem>
        <STable v-if="sources.length">
          <thead>
            <tr>
              <th>对话源</th>
              <th>插件</th>
              <th>状态</th>
              <th>支持的消息类型</th>
              <th>信任</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="source in sources" :key="source.id">
              <td>{{ source.name }}</td>
              <td>{{ source.plugin_id }}</td>
              <td :title="source.reason">{{ source.available ? '已连接' : '不可用' }}</td>
              <td>{{ source.capabilities.map((key) => capabilityNames[key] || key).join(' · ') || '—' }}</td>
              <td @change.stop @input.stop><SSwitch :model-value="source.trusted" :disabled="trustBusy[source.id]" :aria-label="`信任 ${source.name}`" @update:model-value="setTrust(source.id, $event)" /></td>
            </tr>
          </tbody>
        </STable>
        <SEmpty v-else label="暂无对话源" />
      </div>
    </SCard>
    <WakePromptEditor v-model="routing.source_change_template" kind="source_change" title="主会话源变更提醒" class="settings-section security-card" @update:model-value="routingDirty = true">
      <template #controls>
        <div class="settings-row"><label>启用</label><SSwitch v-model="routing.source_change_enabled" @change="routingDirty = true" /></div>
        <SFormItem label="插入模式">
          <SSelect v-model="routing.source_change_mode" :disabled="!routing.source_change_enabled" @change="routingDirty = true">
            <option value="context">上下文</option><option value="temporary">临时</option>
          </SSelect>
        </SFormItem>
      </template>
    </WakePromptEditor>
    <WakePromptEditor v-model="routing.untrusted_source_template" kind="source_risk" title="不可信来源风险警告" class="settings-section security-card" @update:model-value="routingDirty = true" />
    </SForm>
    <Teleport to="body">
      <div class="floating-actions runtime-save">
        <span v-if="error" class="form-error">{{ error }}</span>
        <SButton type="submit" form="runtime-settings" :variant="dirty || routingDirty ? 'primary' : 'default'"
          :disabled="!dirty && !routingDirty" :loading="saving" icon="check">保存设置</SButton>
      </div>
    </Teleport>
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
.runtime-layout { width: 100%; max-width: 820px; margin: 0 auto; }
.settings-grid { grid-template-columns: minmax(0, 1fr); }
.runtime-layout .form-row { grid-template-columns: minmax(0, 1fr); }
.danger-zone {
  border-color: var(--danger, var(--palette-border-dc5c62));
}
</style>
