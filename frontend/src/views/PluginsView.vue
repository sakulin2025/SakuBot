<script setup lang="ts">
import { ref, computed } from 'vue'
import { api } from '../api'
import { useConsole } from '../stores/console'
import UiIcon from '../components/UiIcon.vue'
import UiBadge from '../components/UiBadge.vue'
import UiModal from '../components/UiModal.vue'
import UiEmpty from '../components/UiEmpty.vue'
import PluginSettingsDialog from '../components/PluginSettingsDialog.vue'
import type { PluginInfo } from '../types'
const store = useConsole()
const search = ref('')
const builtinsOpen = ref(false)
const matched = computed(() => store.plugins.filter(p =>
  (p.name + p.label).toLowerCase().includes(search.value.toLowerCase())))
const groups = computed(() => [
  { id: 'builtin', label: '内置插件', items: matched.value.filter(p => p.builtin) },
  { id: 'external', label: '第三方扩展', items: matched.value.filter(p => !p.builtin) },
])
const page = (id: string) => store.pages.find((p) => p.plugin_id === id)
const busy = ref(false)
const settingsPlugin = ref<PluginInfo | null>(null)
const importing = ref(false),
  importData = ref(false),
  file = ref<File | null>(null),
  importSession = ref(0)
const exporting = ref<PluginInfo | null>(null),
  exportData = ref(false)
const deleting = ref<PluginInfo | null>(null),
  purge = ref(false)
function fail(error: unknown, fallback: string) {
  store.toast(error instanceof Error ? error.message : fallback, true)
}
async function toggle(name: string, enabled: boolean) {
  try {
    await store.togglePlugin(name, enabled)
  } catch {}
}
async function reload(name: string) {
  busy.value = true
  try {
    await api('plugins/' + name + '/reload', { method: 'POST' })
    await store.refresh()
    store.toast('已重载')
  } catch (error) {
    fail(error, '重载失败')
  } finally {
    busy.value = false
  }
}
function openExport(plugin: PluginInfo) {
  exporting.value = plugin
  exportData.value = false
}
function openDelete(plugin: PluginInfo) {
  deleting.value = plugin
  purge.value = false
}
function openImport() {
  importing.value = true
  file.value = null
  importData.value = false
  importSession.value++
}
function choose(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0] || null
}
async function transfer(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers)
  headers.set('Authorization', 'Bearer ' + (sessionStorage.getItem('sakubot-token') || ''))
  const response = await fetch('/api/' + path, { ...init, headers })
  if (response.status === 401) window.dispatchEvent(new Event('sakubot-unauthorized'))
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: '操作失败' }))
    throw new Error(typeof body.detail === 'string' ? body.detail : '操作失败')
  }
  return response
}
async function importPlugin() {
  if (!file.value) return
  busy.value = true
  try {
    await transfer('plugin-packages/import?include_data=' + importData.value, {
      method: 'POST',
      headers: { 'Content-Type': 'application/zip' },
      body: file.value,
    })
    await store.refresh()
    importing.value = false
    store.toast('已导入')
  } catch (error) {
    fail(error, '导入失败')
  } finally {
    busy.value = false
  }
}
async function exportPlugin() {
  if (!exporting.value) return
  busy.value = true
  try {
    const response = await transfer(
      'plugins/' + exporting.value.name + '/export?include_data=' + exportData.value,
    )
    const url = URL.createObjectURL(await response.blob())
    const link = document.createElement('a')
    link.href = url
    link.download = exporting.value.name + '.zip'
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    exporting.value = null
    store.toast('已导出')
  } catch (error) {
    fail(error, '导出失败')
  } finally {
    busy.value = false
  }
}
async function removePlugin() {
  if (!deleting.value) return
  busy.value = true
  try {
    await api('plugins/' + deleting.value.name + '?confirm=true&purge=' + purge.value, { method: 'DELETE' })
    await store.refresh()
    deleting.value = null
    store.toast('已删除')
  } catch (error) {
    fail(error, '删除失败')
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <div class="page-toolbar">
    <div class="search-field">
      <UiIcon name="search" :size="17" />
      <SInput v-model="search" placeholder="搜索插件" aria-label="搜索插件" />
    </div>
    <SButton icon="upload" :disabled="busy" @click="openImport">导入</SButton>
  </div>
  <div v-for="group in groups" :key="group.id" class="plugin-section">
    <button v-if="group.id === 'builtin'" class="plugin-section-toggle" type="button" :aria-expanded="builtinsOpen" @click="builtinsOpen = !builtinsOpen">
      <UiIcon name="right" :size="16" :class="{ expanded: builtinsOpen }" />
      <strong>{{ group.label }}</strong><span class="plugin-section-count">{{ group.items.length }}</span>
    </button>
    <div v-else class="plugin-section-heading"><strong>{{ group.label }}</strong><span class="plugin-section-count">{{ group.items.length }}</span></div>
    <div v-if="group.id !== 'builtin' || builtinsOpen" class="plugin-grid">
    <section v-for="plugin in group.items" :key="plugin.name" class="plugin-card">
      <div class="plugin-card-top">
        <span class="plugin-icon"><UiIcon :name="plugin.icon || 'plugins'" :size="26" /></span>
        <SSwitch
          :model-value="plugin.required || plugin.loaded"
          :disabled="plugin.required || store.saving || busy"
          :label="plugin.label"
          :title="plugin.required ? '基础能力已锁定' : plugin.loaded ? '停用插件' : '启用插件'"
          @change="toggle(plugin.name, $event)"
        />
      </div>
      <div class="plugin-name-row">
        <h2>{{ plugin.label }}</h2>
        <UiBadge v-if="plugin.required" status="enabled" label="基础能力" class="plugin-core-tag" />
      </div>
      <span class="plugin-id mono">{{ plugin.name }}</span>
      <div class="plugin-card-bottom">
        <div class="plugin-status"><UiBadge :status="plugin.state" :title="plugin.reason" /></div>
        <div class="plugin-actions">
          <RouterLink
            v-if="page(plugin.name)"
            class="plugin-action"
            :to="page(plugin.name)!.route"
            title="打开页面"
            aria-label="打开页面"
          >
            <UiIcon name="external" :size="16" />
          </RouterLink>
          <SButton
            v-if="plugin.loaded && !plugin.required"
            class="plugin-action"
            icon="refresh"
            :disabled="busy || store.saving"
            title="重载插件"
            aria-label="重载插件"
            @click="reload(plugin.name)"
          />
          <SButton
            v-if="plugin.has_settings"
            class="plugin-action"
            icon="settings"
            :disabled="busy"
            title="插件设置"
            aria-label="插件设置"
            @click="settingsPlugin = plugin"
          />
          <SButton
            v-if="!plugin.builtin"
            class="plugin-action"
            icon="download"
            :disabled="busy"
            title="导出插件"
            aria-label="导出插件"
            @click="openExport(plugin)"
          />
          <SButton
            v-if="!plugin.builtin"
            class="plugin-action plugin-action-danger"
            icon="trash"
            :disabled="busy"
            title="删除插件"
            aria-label="删除插件"
            @click="openDelete(plugin)"
          />
        </div>
      </div>
    </section>
    </div>
    <UiEmpty v-if="(group.id !== 'builtin' || builtinsOpen) && !group.items.length" label="暂无插件" />
  </div>
  <PluginSettingsDialog :plugin="settingsPlugin" @close="settingsPlugin = null" />
  <UiModal :open="importing" title="导入插件" @close="!busy && (importing = false)">
    <SFormItem label="插件包">
      <SInput
        :key="importSession"
        type="file"
        accept=".zip,application/zip"
        :disabled="busy"
        @change="choose"
      />
    </SFormItem>
    <label class="check-label">
      <SCheckbox v-model="importData" :disabled="busy" />
      导入配置与数据
    </label>
    <template #footer>
      <SButton :disabled="busy" @click="importing = false">取消</SButton>
      <SButton variant="primary" :loading="busy" :disabled="!file" @click="importPlugin">导入</SButton>
    </template>
  </UiModal>
  <UiModal :open="!!exporting" title="导出插件" @close="!busy && (exporting = null)">
    <strong>{{ exporting?.label }}</strong>
    <label class="check-label">
      <SCheckbox v-model="exportData" :disabled="busy" />
      包含配置与数据
    </label>
    <template #footer>
      <SButton :disabled="busy" @click="exporting = null">取消</SButton>
      <SButton variant="primary" :loading="busy" @click="exportPlugin">导出</SButton>
    </template>
  </UiModal>
  <UiModal :open="!!deleting" title="删除插件" @close="!busy && (deleting = null)">
    <strong>{{ deleting?.label }}</strong>
    <span class="cell-sub mono">{{ deleting?.name }}</span>
    <label class="check-label">
      <SCheckbox v-model="purge" :disabled="busy" />
      清除配置与数据
    </label>
    <template #footer>
      <SButton :disabled="busy" @click="deleting = null">取消</SButton>
      <SButton variant="danger" :loading="busy" @click="removePlugin">确认删除</SButton>
    </template>
  </UiModal>
</template>

<style scoped>
.plugin-section { margin-top: 22px; }
.plugin-section-toggle, .plugin-section-heading { display:flex;align-items:center;gap:10px;width:100%;padding:14px 16px;margin:0 0 14px;border:1px solid var(--border);border-radius:12px;background:#fff;color:var(--ink);text-align:left;font:inherit; }
.plugin-section-toggle { cursor:pointer; transition:border-color .18s, background .18s; }
.plugin-section-toggle:hover { border-color:#c9c1e8;background:#fcfbff; }
.plugin-section-toggle svg { color:var(--accent);transition:transform .2s ease; }
.plugin-section-toggle svg.expanded { transform:rotate(90deg); }
.plugin-section-heading { border:0;background:transparent;padding:8px 0; }
.plugin-section-count { margin-left:auto;color:var(--muted);font-size:12px; }

.plugin-name-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 28px;
  flex-wrap: wrap;
}
.plugin-name-row h2 {
  margin: 0;
  font-size: 15px;
  line-height: 1.6;
}
.plugin-core-tag {
  font-size: 10px;
  white-space: nowrap;
  flex-shrink: 0;
}
.plugin-card-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: nowrap;
}
.plugin-status {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.plugin-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 5px;
  flex-wrap: wrap;
  margin-left: auto;
}
.plugin-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  min-height: 30px;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
  color: var(--muted);
  box-shadow: 0 1px 2px #30294604;
  transition:
    background var(--s-motion),
    border-color var(--s-motion),
    color var(--s-motion),
    transform var(--s-motion);
}
.plugin-action:hover:not(:disabled) {
  color: var(--accent);
  border-color: #d7cfed;
  background: #f6f3fd;
  transform: translateY(-1px);
}
.plugin-action:focus-visible {
  outline: 0;
  box-shadow: var(--s-ring);
}
.plugin-action-danger:hover:not(:disabled) {
  color: var(--negative);
  border-color: #eacbd3;
  background: #fff5f7;
}
.plugin-action:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}
@media (max-width: 420px) {
  .plugin-actions {
    gap: 4px;
  }
  .plugin-action {
    width: 28px;
    height: 28px;
    min-height: 28px;
  }
}
</style>
