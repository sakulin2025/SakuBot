<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import UiIcon from '../components/UiIcon.vue'
import WorkbenchField from './WorkbenchField.vue'
import WorkbenchData from './WorkbenchData.vue'
import { usePluginHost } from './index'
const host = usePluginHost()
const state = ref<any>({ sections: [], data: {} })
const tab = ref('')
const query = ref('')
const busy = ref(false)
const loading = ref(true)
const page = ref(1)
const inspection = ref<any>(null)
const pageSize = 20
const dialog = ref(false)
const removal = ref<any>(null)
const output = ref<any>(null)
const currentKey = ref('')
const draft = reactive<Record<string, any>>({})
const section = computed<any>(() => state.value.sections.find((x: any) => x.id === tab.value) || {})
const rows = computed(() =>
  (state.value.data[tab.value] || []).filter((x: any) =>
    JSON.stringify(x).toLowerCase().includes(query.value.toLowerCase()),
  ),
)
function options(field: any) {
  return field.options_from
    ? (state.value.data[field.options_from] || []).map((x: any) => ({
        value: x.id || x.mac,
        label: x.name || x.description || x.id || x.mac,
      }))
    : field.options || []
}
function fill(row: any = {}) {
  Object.keys(draft).forEach((k) => delete draft[k])
  for (const field of section.value.fields || [])
    draft[field.key] =
      row[field.key] ?? field.default ?? (field.type === 'boolean' ? false : field.type === 'number' ? 0 : '')
}
async function load() {
  loading.value = true
  try {
    state.value = await host.api('manage')
    tab.value ||= state.value.sections[0]?.id || ''
    if (section.value.kind === 'form') fill(state.value.data[tab.value])
  } catch (e: any) {
    host.toast(e.message || '加载失败', true)
  } finally {
    loading.value = false
  }
}
function edit(row?: any) {
  currentKey.value = row?.[section.value.key || 'id'] || ''
  fill(row || {})
  dialog.value = true
}
function select(value: string) {
  tab.value = value
  currentKey.value = ''
  query.value = ''
  if (section.value.kind === 'form') fill(state.value.data[value])
}
async function act(action: string, value?: any, key?: string, command?: string) {
  busy.value = true
  try {
    const payload =
      action === 'save'
        ? Object.fromEntries(
            (section.value.fields || [])
              .filter((field: any) => !field.readonly)
              .map((field: any) => [
                field.key,
                field.type === 'number' ? Number(value?.[field.key]) : value?.[field.key],
              ]),
          )
        : value || {}
    const result: any = await host.api('manage', {
      section: tab.value,
      action,
      value: payload,
      expected: state.value.data[tab.value],
      key: key || '',
      command: command || '',
    })
    state.value = result.state
    dialog.value = false
    removal.value = null
    if (section.value.kind === 'form') fill(state.value.data[tab.value])
    if (action === 'command' && result.result != null) output.value = result.result
    host.toast(action === 'remove' ? '已删除' : action === 'command' ? '已完成' : '已保存')
  } catch (e: any) {
    host.toast(e.message || '操作失败', true)
  } finally {
    busy.value = false
  }
}
const display = (value: any) =>
  value == null
    ? '—'
    : typeof value === 'boolean'
      ? value
        ? '开启'
        : '关闭'
      : typeof value === 'object'
        ? JSON.stringify(value)
        : String(value)
const pagedRows = computed(() => rows.value.slice((page.value - 1) * pageSize, page.value * pageSize))
const pages = computed(() => Math.max(1, Math.ceil(rows.value.length / pageSize)))
const columns = computed<any[]>(() => section.value.columns || section.value.fields || [])
const hasActions = computed(
  () => section.value.edit || section.value.remove || section.value.row_commands?.length,
)
const textValue = computed(() => state.value.data[tab.value])
const keyText = computed(() =>
  typeof textValue.value === 'string' ? textValue.value.trim().split('\n')[0] : '',
)
const trustCommand = computed(() =>
  publicKey.value ? String(textValue.value).trim().split('\n').slice(1).join('\n').trim() : '',
)
const publicKey = computed(
  () => typeof textValue.value === 'string' && /^ssh-|^ecdsa-/.test(textValue.value.trim()),
)
const tabs = computed(() =>
  state.value.sections.map((x: any) => ({
    value: x.id,
    label: x.label,
    disabled: busy.value,
    count: Array.isArray(state.value.data[x.id]) ? state.value.data[x.id].length : undefined,
  })),
)
watch([tab, query], () => {
  page.value = 1
})
watch(pages, (n) => {
  page.value = Math.min(page.value, n)
})
function cell(field: any, value: any) {
  const option = options(field).find((x: any) => x.value === value)
  return option?.label ?? display(value)
}
function identity(row: any) {
  return (
    row?.name || row?.alias || row?.description || row?.[section.value.key || 'id'] || section.value.label
  )
}
async function copyText(text: string, label: string) {
  try {
    await navigator.clipboard.writeText(text)
    host.toast(label + '已复制')
  } catch {
    host.toast('复制失败，请手动选择复制', true)
  }
}
onMounted(load)
</script>
<template>
  <main class="wb-page">
    <SPageHeader :title="state.title || '插件管理'">
      <SButton icon="refresh" :loading="loading" :disabled="busy || dialog" @click="load">刷新</SButton>
      <SButton v-if="section.create" variant="primary" icon="plus" :disabled="busy" @click="edit()">
        新增{{ section.label }}
      </SButton>
    </SPageHeader>
    <div v-if="loading && !state.sections.length" class="wb-skeleton"><div v-for="i in 5" :key="i" /></div>
    <template v-else>
      <STabs :model-value="tab" :items="tabs" @update:model-value="select" />
      <Transition name="s-page" mode="out-in">
        <SCard :key="tab" class="wb-panel" :loading="busy">
          <div class="wb-toolbar">
            <div class="wb-section-title">
              <span class="wb-section-icon">
                <UiIcon
                  :name="
                    section.kind === 'form'
                      ? 'settings'
                      : publicKey
                        ? 'key'
                        : section.kind === 'text'
                          ? 'file'
                          : 'plugins'
                  "
                  :size="18"
                />
              </span>
              <h2>{{ section.label }}</h2>
              <span v-if="section.kind === 'table'" class="wb-count">{{ rows.length }}</span>
            </div>
            <div class="wb-toolbar-actions">
              <div v-if="section.kind === 'table'" class="wb-search">
                <UiIcon name="search" :size="16" />
                <SInput
                  v-model="query"
                  :placeholder="'搜索' + section.label"
                  :aria-label="'搜索' + section.label"
                />
              </div>
              <SButton
                v-for="command in section.commands || []"
                :key="command.id"
                :disabled="busy"
                @click="act('command', {}, '', command.id)"
              >
                {{ command.label }}
              </SButton>
              <SButton v-if="publicKey" icon="copy" @click="copyText(keyText, '公钥')">复制公钥</SButton>
            </div>
          </div>
          <form v-if="section.kind === 'form'" class="wb-settings" @submit.prevent="act('save', draft)">
            <div class="wb-form-grid">
              <WorkbenchField
                v-for="field in section.fields"
                :key="field.key"
                v-model="draft[field.key]"
                :field="field"
                :options="options(field)"
                :configured="!!state.data[tab]?.[field.key + '_configured']"
              />
            </div>
            <div class="wb-form-footer">
              <SButton variant="primary" type="submit" icon="check" :loading="busy">
                保存{{ section.label }}
              </SButton>
            </div>
          </form>
          <div v-else-if="section.kind === 'text'" class="wb-text-panel">
            <div v-if="publicKey" class="wb-key">
              <UiIcon name="key" :size="22" />
              <code>{{ keyText }}</code>
            </div>
            <div v-if="trustCommand" class="wb-trust">
              <div>
                <strong>信任命令</strong>
                <SButton size="small" icon="copy" @click="copyText(trustCommand, '命令')">复制命令</SButton>
              </div>
              <pre>{{ trustCommand }}</pre>
            </div>
            <WorkbenchData v-if="!publicKey" :value="textValue" />
          </div>
          <template v-else>
            <div class="wb-table-scroll">
              <STable>
                <thead>
                  <tr>
                    <th v-for="field in columns" :key="field.key">{{ field.label }}</th>
                    <th v-if="hasActions" class="wb-actions-col">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, index) in pagedRows" :key="row[section.key || 'id'] || index">
                    <td v-for="(field, columnIndex) in columns" :key="field.key">
                      <img
                        v-if="field.type === 'image' && row[field.key]"
                        :src="row[field.key]"
                        class="wb-image"
                        alt=""
                        loading="lazy"
                      />
                      <span v-else-if="row[field.key] == null" class="subtle">—</span>
                      <STag
                        v-else-if="field.type === 'boolean'"
                        :status="row[field.key] ? 'enabled' : 'disabled'"
                        :label="row[field.key] ? '是' : '否'"
                      />
                      <SButton
                        v-else-if="typeof row[field.key] === 'object'"
                        variant="text"
                        icon="file"
                        @click="inspection = row"
                      >
                        查看详情
                      </SButton>
                      <span v-else-if="field.type === 'select'" class="wb-enum">
                        {{ cell(field, row[field.key]) }}
                      </span>
                      <button
                        v-else-if="columnIndex === 0"
                        class="wb-identity"
                        :title="cell(field, row[field.key])"
                        @click="inspection = row"
                      >
                        {{ cell(field, row[field.key]) }}
                      </button>
                      <div
                        v-else
                        class="wb-cell"
                        :class="{
                          'wb-mono': ['id', 'mac', 'ip', 'address', 'path', 'entity_id', 'cwd'].includes(
                            field.key,
                          ),
                        }"
                        :title="cell(field, row[field.key])"
                      >
                        {{ cell(field, row[field.key]) }}
                      </div>
                    </td>
                    <td v-if="hasActions" class="wb-actions-col">
                      <div class="wb-row-actions">
                        <SButton
                          v-for="command in section.row_commands || []"
                          :key="command.id"
                          size="small"
                          :disabled="busy"
                          @click="act('command', row, row[section.key || 'id'], command.id)"
                        >
                          {{ command.label }}
                        </SButton>
                        <SButton
                          v-if="section.edit"
                          variant="text"
                          icon="edit"
                          :aria-label="'编辑' + identity(row)"
                          @click="edit(row)"
                        >
                          编辑
                        </SButton>
                        <SButton
                          v-if="section.remove"
                          variant="text"
                          class="wb-delete"
                          icon="trash"
                          :aria-label="'删除' + identity(row)"
                          @click="removal = row"
                        >
                          删除
                        </SButton>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </STable>
              <SEmpty v-if="!rows.length" :label="query ? '无匹配结果' : '暂无' + section.label" />
            </div>
            <div v-if="rows.length" class="wb-pagination">
              <span>共 {{ rows.length }} 项</span>
              <div>
                <SButton size="small" icon="left" :disabled="page <= 1" aria-label="上一页" @click="page--" />
                <span>{{ page }} / {{ pages }}</span>
                <SButton
                  size="small"
                  icon="right"
                  :disabled="page >= pages"
                  aria-label="下一页"
                  @click="page++"
                />
              </div>
            </div>
          </template>
        </SCard>
      </Transition>
    </template>
    <SDialog
      :open="dialog"
      :title="(currentKey ? '编辑' : '新增') + (section.label || '')"
      wide
      @close="!busy && (dialog = false)"
    >
      <form
        id="plugin-record-form"
        class="wb-form-grid wb-dialog-form"
        @submit.prevent="act('save', draft, currentKey)"
      >
        <WorkbenchField
          v-for="field in section.fields"
          :key="field.key"
          v-model="draft[field.key]"
          :field="field"
          :options="options(field)"
          :editing="!!currentKey"
        />
      </form>
      <template #footer>
        <SButton :disabled="busy" @click="dialog = false">取消</SButton>
        <SButton variant="primary" form="plugin-record-form" type="submit" :loading="busy">保存</SButton>
      </template>
    </SDialog>
    <SDialog :open="!!removal" title="确认删除" @close="!busy && (removal = null)">
      <div class="wb-remove-target">
        <span><UiIcon name="trash" :size="22" /></span>
        <strong>{{ identity(removal) }}</strong>
      </div>
      <template #footer>
        <SButton :disabled="busy" @click="removal = null">取消</SButton>
        <SButton
          variant="danger"
          :loading="busy"
          @click="act('remove', removal, removal[section.key || 'id'])"
        >
          确认删除
        </SButton>
      </template>
    </SDialog>
    <SDialog :open="inspection !== null" :title="section.label + '详情'" wide @close="inspection = null">
      <WorkbenchData :value="inspection" />
    </SDialog>
    <SDialog :open="output !== null" title="操作结果" wide @close="output = null">
      <WorkbenchData :value="output" />
    </SDialog>
  </main>
</template>
<style scoped>
.wb-page {
  --wb-soft: color-mix(in srgb, var(--accent) 7%, white);
  padding-bottom: 20px;
}
.wb-panel {
  margin-top: 18px;
  overflow: hidden;
  border-radius: 16px;
  box-shadow: 0 3px 18px #29234405;
}
.wb-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 22px;
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
}
.wb-section-title {
  display: flex;
  align-items: center;
  gap: 10px;
}
.wb-section-title h2 {
  font-size: 14px;
  font-weight: 650;
  margin: 0;
}
.wb-section-icon {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  background: var(--wb-soft);
  color: var(--accent);
  border: 1px solid color-mix(in srgb, var(--accent) 12%, white);
  border-radius: 10px;
}
.wb-count {
  font-size: 11px;
  font-weight: 600;
  color: var(--muted);
  background: var(--canvas);
  border-radius: 6px;
  padding: 3px 7px;
}
.wb-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.wb-search {
  position: relative;
  width: 230px;
}
.wb-search > svg {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--muted);
  z-index: 1;
}
.wb-search .s-input {
  width: 100%;
  padding-left: 36px;
  background: var(--canvas);
}
.wb-settings {
  max-width: 1000px;
  margin: auto;
  padding: 28px 30px 0;
}
.wb-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 24px 28px;
}
.wb-form-footer {
  display: flex;
  justify-content: flex-end;
  padding: 22px 0;
  margin-top: 26px;
  border-top: 1px solid var(--border);
}
.wb-dialog-form {
  padding: 4px 0 8px;
}
.wb-table-scroll {
  overflow: auto;
}
.wb-table-scroll :deep(.data-table) {
  min-width: 100%;
  width: max-content;
}
.wb-table-scroll :deep(th) {
  font-size: 11px;
  letter-spacing: 0.03em;
  background: #fafafe;
  padding: 12px 20px;
  color: var(--muted);
}
.wb-table-scroll :deep(td) {
  padding: 15px 20px;
  font-size: 13px;
  vertical-align: middle;
  border-bottom: 1px solid var(--border);
}
.wb-table-scroll :deep(tbody tr) {
  transition: background 0.18s ease;
}
.wb-table-scroll :deep(tbody tr:hover) {
  background: #faf9ff;
}
.wb-cell {
  max-width: 280px;
  min-width: 60px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.65;
}
.wb-mono {
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  color: var(--muted);
}
.wb-identity {
  background: none;
  border: 0;
  padding: 0;
  text-align: left;
  color: var(--ink);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  max-width: 250px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wb-identity:hover {
  color: var(--accent);
}
.wb-enum {
  display: inline-flex;
  background: var(--wb-soft);
  color: var(--accent);
  font-size: 12px;
  padding: 4px 9px;
  border-radius: 6px;
  white-space: nowrap;
}
.wb-actions-col {
  position: sticky;
  right: 0;
  background: #fff;
  border-left: 1px solid var(--border);
  width: 1%;
  box-shadow: -8px 0 12px #29234403;
}
.wb-row-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  white-space: nowrap;
}
.wb-row-actions :deep(.wb-delete) {
  color: var(--negative);
}
.wb-image {
  width: 66px;
  height: 58px;
  border-radius: 10px;
  object-fit: cover;
  border: 1px solid var(--border);
  background: var(--canvas);
}
.wb-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 22px;
  color: var(--muted);
  font-size: 12px;
  border-top: 1px solid var(--border);
}
.wb-pagination > div {
  display: flex;
  align-items: center;
  gap: 16px;
}
.wb-text-panel {
  padding: 24px;
  max-height: 70vh;
  overflow: auto;
}
.wb-key {
  display: flex;
  gap: 18px;
  align-items: flex-start;
  padding: 24px;
  border: 1px solid color-mix(in srgb, var(--accent) 16%, white);
  background: linear-gradient(130deg, var(--wb-soft), #fafafe);
  border-radius: 12px;
  color: var(--accent);
}
.wb-key code {
  font-size: 13px;
  line-height: 1.9;
  word-break: break-all;
  user-select: all;
  color: var(--ink);
}
.wb-trust {
  margin-top: 22px;
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}
.wb-trust > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--canvas);
  border-bottom: 1px solid var(--border);
}
.wb-trust strong {
  font-size: 12px;
}
.wb-trust pre {
  margin: 0;
  padding: 18px;
  font-size: 12px;
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.wb-key > svg {
  flex-shrink: 0;
  margin-top: 3px;
}
.wb-remove-target {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 0;
}
.wb-remove-target > span {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: #fff1f1;
  color: var(--negative);
}
.wb-remove-target strong {
  overflow-wrap: anywhere;
}
.wb-skeleton {
  display: grid;
  gap: 20px;
  padding: 28px;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: white;
}
.wb-skeleton > div {
  height: 42px;
  border-radius: 10px;
  background: linear-gradient(90deg, #f5f4fa, #eeecf6, #f5f4fa);
  background-size: 200% 100%;
  animation: wb-shimmer 1.6s ease infinite;
}
.wb-skeleton > div:first-child {
  width: 35%;
}
@keyframes wb-shimmer {
  to {
    background-position: -200% 0;
  }
}
@media (max-width: 800px) {
  .wb-toolbar {
    padding: 16px;
  }
  .wb-toolbar-actions {
    width: 100%;
  }
  .wb-search {
    flex: 1;
    min-width: 130px;
  }
  .wb-settings {
    padding: 20px 18px 0;
  }
  .wb-form-grid {
    grid-template-columns: 1fr;
    gap: 20px;
  }
  .wb-key {
    padding: 16px;
  }
  .wb-actions-col {
    position: static;
  }
  .wb-text-panel {
    padding: 18px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .wb-skeleton > div {
    animation: none;
  }
}
</style>
