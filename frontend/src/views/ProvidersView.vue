<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useConsole } from '../stores/console'
import type { Provider } from '../types'
import UiIcon from '../components/UiIcon.vue'
import UiBadge from '../components/UiBadge.vue'
import UiEmpty from '../components/UiEmpty.vue'
import UiModal from '../components/UiModal.vue'
import SecretInput from '../components/SecretInput.vue'

defineProps<{ embedded?: boolean }>()
const store = useConsole()
const router = useRouter()
const query = ref('')
const editing = ref(false)
const deleting = ref<Provider | null>(null)
const saving = ref(false)
const providerForm = ref<HTMLFormElement>()
const selected = ref<Provider | null>(null)
const draft = reactive({ name: '', api_base: 'https://api.deepseek.com/v1', api_key: '', enabled: true })
const providers = computed(
  () =>
    store.config?.providers.filter((item) =>
      (item.name + item.api_base).toLowerCase().includes(query.value.toLowerCase()),
    ) || [],
)
const count = (id: string) => store.config?.models.filter((item) => item.provider_id === id).length || 0
function edit(provider?: Provider) {
  selected.value = provider || null
  Object.assign(draft, {
    name: provider?.name || '',
    api_base: provider?.api_base || 'https://api.deepseek.com/v1',
    api_key: '',
    enabled: provider?.enabled ?? true,
  })
  editing.value = true
}
async function save(fetchModels = false) {
  if (!providerForm.value?.reportValidity()) return
  saving.value = true
  try {
    const response = await api<{ id: string }>('providers', {
      body: { ...draft, ...(selected.value ? { id: selected.value.id } : {}) },
    })
    await store.refresh()
    editing.value = false
    store.toast('已保存')
    if (fetchModels) router.push({ path: '/model', query: { provider: response.id, discover: '1' } })
  } catch {
    store.toast('保存失败', true)
  } finally {
    saving.value = false
  }
}
async function toggle(provider: Provider) {
  saving.value = true
  try {
    await api('providers', {
      body: { id: provider.id, name: provider.name, api_base: provider.api_base, enabled: !provider.enabled },
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
    await api('providers/' + deleting.value.id, { method: 'DELETE' })
    await store.refresh()
    deleting.value = null
    store.toast('已删除')
  } catch {
    store.toast('删除失败', true)
  } finally {
    saving.value = false
  }
}
</script>
<template>
  <div class="page-heading">
    <div v-if="!embedded" class="heading-title">
      <span class="page-kicker">Agent</span>
      <h1>供应商</h1>
      <span class="heading-count">{{ store.config?.providers.length || 0 }}</span>
    </div>
    <SButton class="button primary" @click="edit()">
      <UiIcon name="plus" :size="17" />
      新增供应商
    </SButton>
  </div>
  <div class="page-toolbar">
    <div class="search-field">
      <UiIcon name="search" :size="17" />
      <SInput v-model="query" aria-label="搜索供应商" placeholder="搜索供应商" />
    </div>
    <RouterLink v-if="!embedded" to="/model" class="button">
      <UiIcon name="model" :size="17" />
      模型管理
      <UiIcon name="arrow" :size="15" />
    </RouterLink>
  </div>
  <div v-if="providers.length" class="provider-grid">
    <SCard v-for="provider in providers" :key="provider.id" class="surface provider-card">
      <div class="provider-heading">
        <span class="provider-avatar">{{ provider.name.slice(0, 1).toUpperCase() }}</span>
        <div>
          <h2>{{ provider.name }}</h2>
        </div>
        <SSwitch
          :model-value="provider.enabled"
          :aria-label="provider.name"
          :disabled="saving"
          @change="toggle(provider)"
        />
      </div>
      <div class="provider-address mono">{{ provider.api_base }}</div>
      <div class="provider-details">
        <UiBadge :status="provider.enabled ? 'enabled' : 'disabled'" />
        <span>
          <UiIcon name="key" :size="13" />
          {{ provider.api_key_configured ? '已设置' : '未设置' }}
        </span>
        <span>{{ count(provider.id) }} 模型</span>
      </div>
      <div class="provider-actions">
        <SButton
          class="button compact"
          @click="router.push({ path: '/model', query: { provider: provider.id, discover: '1' } })"
        >
          <UiIcon name="refresh" :size="14" />
          获取模型
        </SButton>
        <SButton class="icon-button" aria-label="编辑供应商" @click="edit(provider)">
          <UiIcon name="edit" :size="16" />
        </SButton>
        <SButton class="icon-button danger-text" aria-label="删除供应商" @click="deleting = provider">
          <UiIcon name="trash" :size="16" />
        </SButton>
      </div>
    </SCard>
  </div>
  <SCard v-else class="surface">
    <UiEmpty label="暂无供应商" icon="connection">
      <SButton class="button primary" @click="edit()">
        <UiIcon name="plus" :size="16" />
        新增供应商
      </SButton>
    </UiEmpty>
  </SCard>
  <UiModal :open="editing" :title="selected ? '编辑供应商' : '新增供应商'" @close="editing = false">
    <form ref="providerForm" id="provider-form" class="form-stack" @submit.prevent="save(false)">
      <div class="field">
        <label for="provider-name">名称</label>
        <SInput id="provider-name" v-model="draft.name" maxlength="100" required />
      </div>
      <div class="field">
        <label for="provider-base">API 地址</label>
        <SInput id="provider-base" v-model="draft.api_base" type="url" required />
      </div>
      <div class="field">
        <label for="provider-key">
          API Key
          <span v-if="selected?.api_key_configured" class="field-state">已设置</span>
        </label>
        <SecretInput id="provider-key" v-model="draft.api_key" />
      </div>
      <label class="checkbox-field">
        <SCheckbox v-model="draft.enabled" />
        启用供应商
      </label>
    </form>
    <template #footer>
      <SButton class="button" :disabled="saving" @click="save(true)">
        保存并获取模型
        <UiIcon name="arrow" :size="15" />
      </SButton>
      <SButton class="button primary" form="provider-form" :disabled="saving">保存</SButton>
    </template>
  </UiModal>
  <UiModal :open="!!deleting" title="删除供应商" @close="deleting = null">
    <div class="delete-target">
      <UiIcon name="trash" :size="24" />
      <strong>{{ deleting?.name }}</strong>
      <span class="badge neutral">{{ deleting ? count(deleting.id) : 0 }} 模型</span>
    </div>
    <template #footer>
      <SButton class="button" @click="deleting = null">取消</SButton>
      <SButton class="button danger" :disabled="saving" @click="remove">删除</SButton>
    </template>
  </UiModal>
</template>
