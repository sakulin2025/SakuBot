<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, ApiError } from '../api'
import { useConsole } from '../stores/console'
import type { AvailableModel, Capabilities, ModelEntry } from '../types'
import UiIcon from '../components/UiIcon.vue'
import UiBadge from '../components/UiBadge.vue'
import UiEmpty from '../components/UiEmpty.vue'
import UiModal from '../components/UiModal.vue'

defineProps<{ embedded?: boolean }>()
const store = useConsole()
const route = useRoute()
const router = useRouter()
const search = ref('')
const providerFilter = ref('')
const editing = ref(false)
const saving = ref(false)
const deleting = ref<ModelEntry | null>(null)
const original = ref<ModelEntry | null>(null)
const formError = ref('')
const modelForm = ref<HTMLFormElement>()
const draft = reactive({
  provider_id: '',
  model_id: '',
  name: '',
  enabled: true,
  context_window: 0,
  capabilities: { text: true, image: false, audio: false, tools: true, embedding: false } as Capabilities,
})
type Parameter = { key: string; type: 'string' | 'number' | 'boolean' | 'json'; value: string }
const parameters = ref<Parameter[]>([])
const capabilities: { key: keyof Capabilities; label: string }[] = [
  { key: 'text', label: '文本' },
  { key: 'image', label: '图像' },
  { key: 'audio', label: '音频' },
  { key: 'tools', label: '工具使用' },
  { key: 'embedding', label: 'Embedding' },
]
const providers = computed(() => store.config?.providers || [])
const models = computed(() => store.config?.models || [])
const usable = computed(() =>
  models.value.filter(
    (model) =>
      model.enabled &&
      model.capabilities.text &&
      providers.value.some((provider) => provider.id === model.provider_id && provider.enabled),
  ),
)
const visible = computed(() =>
  models.value.filter(
    (model) =>
      (!providerFilter.value || model.provider_id === providerFilter.value) &&
      (model.name + model.model_id).toLowerCase().includes(search.value.toLowerCase()),
  ),
)
const providerName = (id: string) => providers.value.find((item) => item.id === id)?.name || id
const formatWindow = (window: number) => (window ? window.toLocaleString('en-US') : '未知')

function edit(model?: ModelEntry) {
  original.value = model || null
  formError.value = ''
  Object.assign(draft, {
    provider_id: model?.provider_id || providers.value[0]?.id || '',
    model_id: model?.model_id || '',
    name: model?.name || '',
    enabled: model?.enabled ?? true,
    context_window: model?.context_window || 0,
    capabilities: { ...(model?.capabilities || { text: true, image: false, audio: false, tools: true, embedding: false }) },
  })
  parameters.value = Object.entries(model?.extra_body || {}).map(([key, value]) => ({
    key,
    type:
      typeof value === 'number'
        ? 'number'
        : typeof value === 'boolean'
          ? 'boolean'
          : typeof value === 'string'
            ? 'string'
            : 'json',
    value: typeof value === 'string' ? value : JSON.stringify(value),
  }))
  editing.value = true
}
function bodyParameters() {
  const body: Record<string, unknown> = Object.create(null)
  for (const parameter of parameters.value) {
    const key = parameter.key.trim()
    if (!key || Object.hasOwn(body, key)) throw Error('参数名称无效')
    if (['model', 'messages', 'stream', 'tools'].includes(key)) throw Error('参数名称无效')
    let value: unknown = parameter.value
    if (parameter.type === 'number') {
      if (!parameter.value.trim() || !Number.isFinite(Number(parameter.value))) throw Error('参数值无效')
      value = Number(parameter.value)
    } else if (parameter.type === 'boolean') {
      if (!['true', 'false'].includes(parameter.value)) throw Error('布尔值无效')
      value = parameter.value === 'true'
    } else if (parameter.type === 'json') {
      try {
        value = JSON.parse(parameter.value)
      } catch {
        throw Error('JSON 无效')
      }
    }
    body[key] = value
  }
  return body
}
async function save() {
  if (!modelForm.value?.reportValidity()) return
  saving.value = true
  formError.value = ''
  try {
    await api('models', {
      body: {
        ...draft,
        context_window: Number(draft.context_window),
        extra_body: bodyParameters(),
        ...(original.value ? { id: original.value.id } : {}),
      },
    })
    await store.refresh()
    editing.value = false
    store.toast('已保存')
  } catch (error) {
    formError.value =
      error instanceof Error ? error.message : '保存失败'
  } finally {
    saving.value = false
  }
}
async function toggle(model: ModelEntry) {
  saving.value = true
  try {
    await api('models', {
      body: {
        id: model.id,
        provider_id: model.provider_id,
        model_id: model.model_id,
        name: model.name,
        enabled: !model.enabled,
        capabilities: model.capabilities,
        extra_body: model.extra_body,
        context_window: model.context_window,
      },
    })
    await store.refresh()
  } catch {
    store.toast('操作失败', true)
  } finally {
    saving.value = false
  }
}
async function remove() {
  if (!deleting.value) return
  saving.value = true
  try {
    await api('models/' + deleting.value.id, { method: 'DELETE' })
    await store.refresh()
    deleting.value = null
    store.toast('已删除')
  } catch {
    store.toast('删除失败', true)
  } finally {
    saving.value = false
  }
}

const discovering = ref(false)
const discoveryProvider = ref('')
const fetching = ref(false)
const discovered = ref<AvailableModel[]>([])
const discoveredSearch = ref('')
const importSelection = ref<string[]>([])
const imported = computed(
  () =>
    new Set(
      models.value
        .filter((item) => item.provider_id === discoveryProvider.value)
        .map((item) => item.model_id),
    ),
)
const discoveryVisible = computed(() =>
  discovered.value.filter((item) =>
    item.model_id.toLowerCase().includes(discoveredSearch.value.toLowerCase()),
  ),
)
const selectable = computed(() => discoveryVisible.value.filter((item) => !imported.value.has(item.model_id)))
const allSelected = computed(
  () =>
    selectable.value.length > 0 &&
    selectable.value.every((item) => importSelection.value.includes(item.model_id)),
)
async function loadCached() {
  importSelection.value = []
  discovered.value = []
  if (!discoveryProvider.value) return
  try {
    discovered.value = (
      await api<{ items: AvailableModel[] }>('providers/' + discoveryProvider.value + '/models')
    ).items
  } catch {
    store.toast('加载失败', true)
  }
}
async function fetchModels() {
  if (!discoveryProvider.value) return
  fetching.value = true
  importSelection.value = []
  try {
    discovered.value = (
      await api<{ items: AvailableModel[] }>('providers/' + discoveryProvider.value + '/models/fetch', {
        body: {},
      })
    ).items
    await store.refresh()
    store.toast('已获取模型')
  } catch (error) {
    store.toast(error instanceof ApiError ? '获取失败 · ' + error.status : '获取失败', true)
  } finally {
    fetching.value = false
  }
}
async function discover(providerId?: string, fetch = false) {
  discoveryProvider.value = providerId || providers.value[0]?.id || ''
  discoveredSearch.value = ''
  discovering.value = true
  await loadCached()
  if (fetch) await fetchModels()
}
function selectAll() {
  const ids = selectable.value.map((item) => item.model_id)
  importSelection.value = allSelected.value
    ? importSelection.value.filter((id) => !ids.includes(id))
    : [...new Set([...importSelection.value, ...ids])]
}
async function importModels() {
  saving.value = true
  try {
    await api('models/import', {
      body: { provider_id: discoveryProvider.value, model_ids: importSelection.value },
    })
    await store.refresh()
    discovering.value = false
    store.toast('已添加模型')
  } catch {
    store.toast('添加失败', true)
  } finally {
    saving.value = false
  }
}
onMounted(async () => {
  if (route.query.discover === '1') {
    const provider = String(route.query.provider || '')
    await router.replace('/model')
    await discover(provider, true)
  }
})
</script>
<template>
  <div class="page-heading">
    <div class="heading-actions">
      <RouterLink to="/agents" class="button">Agent 管理</RouterLink>
      <SButton class="button" :disabled="!providers.length" @click="edit()">
        <UiIcon name="plus" :size="17" />
        自定义模型
      </SButton>
      <SButton class="button primary" :disabled="!providers.length" @click="discover()">
        <UiIcon name="model" :size="17" />
        从供应商添加
      </SButton>
    </div>
  </div>
  <SCard class="surface">
    <div class="table-toolbar">
      <div class="search-field">
        <UiIcon name="search" :size="17" />
        <SInput v-model="search" aria-label="搜索模型" placeholder="搜索模型" />
      </div>
      <SSelect v-model="providerFilter" class="filter-select" aria-label="供应商">
        <option value="">全部供应商</option>
        <option v-for="provider in providers" :key="provider.id" :value="provider.id">
          {{ provider.name }}
        </option>
      </SSelect>
    </div>
    <div v-if="visible.length" class="table-scroll">
      <STable class="data-table model-table">
        <thead>
          <tr>
            <th>模型</th>
            <th>供应商</th>
            <th>模型能力</th>
            <th>上下文 · Token</th>
            <th>启用</th>
            <th class="align-right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="model in visible" :key="model.id">
            <td>
              <div class="model-name-row">
                <strong>{{ model.name || model.model_id }}</strong>
                <span v-if="model.id === store.config?.main_model_id" class="badge accent">默认模型</span>
              </div>
              <span class="cell-sub mono">{{ model.model_id }}</span>
            </td>
            <td>{{ providerName(model.provider_id) }}</td>
            <td>
              <div class="capability-tags">
                <span
                  v-for="cap in capabilities.filter(item => model.capabilities[item.key])"
                  :key="cap.key"
                  class="capability-tag enabled"
                >
                  <UiIcon name="check" :size="11" />
                  {{ cap.label }}<template v-if="cap.key === 'embedding' && model.embedding_dimensions"> · {{ model.embedding_dimensions }} 维</template>
                </span>
              </div>
            </td>
            <td class="mono nowrap">
              {{ formatWindow(model.effective_context_window) }}
              <span v-if="model.context_window === 0" class="cell-sub">自动</span>
            </td>
            <td>
              <SSwitch
                :model-value="model.enabled"
                :disabled="saving"
                :aria-label="model.name || model.model_id"
                @change="toggle(model)"
              />
            </td>
            <td>
              <div class="row-actions">
                <SButton class="icon-button" aria-label="配置模型" @click="edit(model)">
                  <UiIcon name="settings" :size="16" />
                </SButton>
                <SButton class="icon-button danger-text" aria-label="删除模型" @click="deleting = model">
                  <UiIcon name="trash" :size="16" />
                </SButton>
              </div>
            </td>
          </tr>
        </tbody>
      </STable>
    </div>
    <UiEmpty v-else :label="providers.length ? '暂无模型' : '暂无供应商'" icon="model">
      <SButton v-if="providers.length" class="button" @click="discover()">
        从供应商添加
        <UiIcon name="arrow" :size="15" />
      </SButton>
      <RouterLink v-else to="/providers" class="button primary">
        新增供应商
        <UiIcon name="arrow" :size="15" />
      </RouterLink>
    </UiEmpty>
  </SCard>
  <UiModal :open="editing" :title="original ? '模型配置' : '自定义模型'" wide @close="editing = false">
    <form ref="modelForm" id="model-form" class="form-stack" @submit.prevent="save">
      <div class="form-row">
        <div class="field">
          <label for="model-provider">供应商</label>
          <SSelect id="model-provider" v-model="draft.provider_id" required>
            <option v-for="provider in providers" :key="provider.id" :value="provider.id">
              {{ provider.name }}
            </option>
          </SSelect>
        </div>
        <div class="field">
          <label for="model-name">名称</label>
          <SInput id="model-name" v-model="draft.name" maxlength="100" />
        </div>
      </div>
      <div class="field">
        <label for="model-id">模型 ID</label>
        <SInput id="model-id" v-model="draft.model_id" class="mono" required maxlength="300" />
      </div>
      <label class="checkbox-field">
        <SCheckbox v-model="draft.enabled" />
        启用模型
      </label>
      <div class="field">
        <label>模型能力</label>
        <div class="capability-options">
          <label
            v-for="cap in capabilities"
            :key="cap.key"
            class="capability-option"
            :class="{ selected: draft.capabilities[cap.key] }"
          >
            <SCheckbox v-model="draft.capabilities[cap.key]" />
            <span>{{ cap.label }}</span>
            <UiIcon v-if="draft.capabilities[cap.key]" name="check" :size="15" />
          </label>
        </div>
      </div>
      <div v-if="original?.capabilities.embedding && original.embedding_dimensions" class="field-state">向量维度：{{ original.embedding_dimensions }}</div>
      <div class="field">
        <label for="context-window">
          模型上下文窗口 · Token
          <span v-if="draft.context_window === 0" class="field-state">自动</span>
        </label>
        <SInput
          id="context-window"
          v-model.number="draft.context_window"
          type="number"
          min="0"
          max="100000000"
          required
        />
        <div v-if="draft.context_window === 0" class="metadata-values">
          <span class="metadata-tag">元数据</span>
          <span class="mono">{{ formatWindow(original?.metadata.context_window || 0) }}</span>
        </div>
      </div>
      <div class="parameters-section">
        <div class="parameters-heading">
          <label>自定义请求体参数</label>
          <SButton
            class="text-button"
            type="button"
            @click="parameters.push({ key: '', type: 'number', value: '' })"
          >
            <UiIcon name="plus" :size="14" />
            添加参数
          </SButton>
        </div>
        <div v-if="!parameters.length" class="parameter-empty">暂无参数</div>
        <div v-else class="parameter-list">
          <div class="parameter-labels">
            <span>参数</span>
            <span>类型</span>
            <span>值</span>
          </div>
          <div v-for="(parameter, index) in parameters" :key="index" class="parameter-row">
            <SInput
              v-model="parameter.key"
              :aria-label="'参数 ' + (index + 1)"
              list="parameter-keys"
              required
            />
            <SSelect v-model="parameter.type" :aria-label="'类型 ' + (index + 1)">
              <option value="number">数字</option>
              <option value="string">字符串</option>
              <option value="boolean">布尔</option>
              <option value="json">JSON</option>
            </SSelect>
            <SSelect
              v-if="parameter.type === 'boolean'"
              v-model="parameter.value"
              :aria-label="'值 ' + (index + 1)"
            >
              <option value="true">true</option>
              <option value="false">false</option>
            </SSelect>
            <SInput
              v-else
              v-model="parameter.value"
              :type="parameter.type === 'number' ? 'number' : 'text'"
              step="any"
              :aria-label="'值 ' + (index + 1)"
            />
            <SButton
              class="icon-button danger-text"
              type="button"
              aria-label="删除参数"
              @click="parameters.splice(index, 1)"
            >
              <UiIcon name="close" :size="15" />
            </SButton>
          </div>
        </div>
        <datalist id="parameter-keys">
          <option
            v-for="key in [
              'temperature',
              'top_p',
              'max_tokens',
              'max_completion_tokens',
              'reasoning_effort',
              'seed',
              'frequency_penalty',
              'presence_penalty',
            ]"
            :key="key"
            :value="key"
          ></option>
        </datalist>
      </div>
      <span v-if="formError" class="form-error" role="alert">{{ formError }}</span>
    </form>
    <template #footer>
      <SButton class="button" @click="editing = false">取消</SButton>
      <SButton class="button primary" form="model-form" :disabled="saving">保存</SButton>
    </template>
  </UiModal>
  <UiModal :open="discovering" title="供应商模型" wide @close="discovering = false">
    <div class="discovery-toolbar">
      <SSelect v-model="discoveryProvider" aria-label="选择供应商" :disabled="fetching" @change="loadCached">
        <option v-for="provider in providers" :key="provider.id" :value="provider.id">
          {{ provider.name }}
        </option>
      </SSelect>
      <SButton class="button primary" :disabled="fetching || !discoveryProvider" @click="fetchModels">
        <UiIcon name="refresh" :class="{ spinning: fetching }" :size="16" />
        {{ fetching ? '获取中' : '获取模型' }}
      </SButton>
    </div>
    <div class="search-field modal-search">
      <UiIcon name="search" :size="17" />
      <SInput v-model="discoveredSearch" aria-label="搜索供应商模型" placeholder="搜索模型" />
    </div>
    <div v-if="fetching" class="loading-state"><UiIcon name="loading" class="spinning" :size="24" /></div>
    <div v-else-if="discoveryVisible.length" class="discovery-list">
      <div class="discovery-list-heading">
        <label class="checkbox-field">
          <SCheckbox :checked="allSelected" @change="selectAll" />
          全选
        </label>
        <span>{{ discoveryVisible.length }} 模型</span>
      </div>
      <label v-for="model in discoveryVisible" :key="model.model_id" class="discovery-item">
        <SCheckbox
          v-model="importSelection"
          :value="model.model_id"
          :disabled="imported.has(model.model_id)"
        />
        <div>
          <strong>{{ model.name || model.model_id }}</strong>
          <span class="mono">{{ model.model_id }}</span>
        </div>
        <span class="discovery-context mono">{{ formatWindow(model.metadata.context_window) }}</span>
        <UiBadge v-if="imported.has(model.model_id)" status="done" label="已添加" />
      </label>
    </div>
    <UiEmpty v-else label="暂无模型" icon="model" />
    <template #footer>
      <span class="selection-total">已选择 {{ importSelection.length }}</span>
      <SButton class="button" @click="discovering = false">取消</SButton>
      <SButton
        class="button primary"
        :disabled="saving || fetching || !importSelection.length"
        @click="importModels"
      >
        添加模型
        <UiIcon name="plus" :size="15" />
      </SButton>
    </template>
  </UiModal>
  <UiModal :open="!!deleting" title="删除模型" @close="deleting = null">
    <div class="delete-target">
      <UiIcon name="trash" :size="24" />
      <strong>{{ deleting?.name || deleting?.model_id }}</strong>
      <span v-if="deleting?.id === store.config?.main_model_id" class="badge accent">默认模型</span>
    </div>
    <template #footer>
      <SButton class="button" @click="deleting = null">取消</SButton>
      <SButton class="button danger" :disabled="saving" @click="remove">删除</SButton>
    </template>
  </UiModal>
</template>
