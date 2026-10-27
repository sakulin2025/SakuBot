<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, reactive } from 'vue'
import { useRoute } from 'vue-router'
import { api, formatDate, parseJson } from '../api'
import { useConsole } from '../stores/console'
import UiIcon from '../components/UiIcon.vue'
import UiBadge from '../components/UiBadge.vue'
import UiModal from '../components/UiModal.vue'
import UiEmpty from '../components/UiEmpty.vue'
import type { LogRecord, ToolCall } from '../types'
const props = defineProps<{ kind: string; embedded?: boolean }>()
const store = useConsole()
const route = useRoute()
const items = ref<(LogRecord | ToolCall)[]>([])
const next = ref<number | null>(null)
const busy = ref(false)
const live = ref(true)
const detail = ref<LogRecord | ToolCall | null>(null)
const filters = reactive({
  query: '',
  run_id: String(route.query.run_id || ''),
  plugin_id: '',
  level: '',
  status: '',
})
let timer: ReturnType<typeof setInterval> | undefined
let generation = 0
let reloadPending = false
async function load(more = false) {
  if (busy.value) {
    if (!more) reloadPending = true
    return
  }
  busy.value = true
  const current = generation
  try {
    const q = new URLSearchParams()
    if (filters.query) q.set('query', filters.query)
    if (filters.run_id) q.set('run_id', filters.run_id)
    if (props.kind === 'logs') {
      if (filters.plugin_id) q.set('source', filters.plugin_id)
      if (filters.level) q.set('level', filters.level)
    } else {
      if (filters.plugin_id) q.set('plugin_id', filters.plugin_id)
      if (filters.status) q.set('status', filters.status)
    }
    if (more && next.value) q.set('before', String(next.value))
    const data = await api<{ items: (LogRecord | ToolCall)[]; next_before: number | null }>(
      props.kind + '?' + q,
    )
    if (current === generation) {
      items.value = more ? [...items.value, ...data.items] : data.items
      next.value = data.next_before
    }
  } catch {
    store.toast('加载失败', true)
  } finally {
    busy.value = false
    if (reloadPending) {
      reloadPending = false
      void load()
    }
  }
}
function reset() {
  generation++
  items.value = []
  next.value = null
  void load()
}
watch(
  () => props.kind,
  () => {
    detail.value = null
    reset()
  },
)
watch(
  () => route.query.run_id,
  (value) => {
    filters.run_id = String(value || '')
    reset()
  },
)
onMounted(() => {
  load()
  timer = setInterval(() => {
    if (live.value && !document.hidden) load()
  }, 3000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
const payload = computed(() => {
  if (!detail.value) return null
  const row = detail.value
  return 'tool_name' in row
    ? { ...row, arguments: parseJson(row.arguments), output: parseJson(row.output) }
    : { ...row, data: parseJson(row.data) }
})
</script>
<template>
  <div class="page-heading">
    <div class="topbar-actions">
      <label class="check-label">
        <SCheckbox v-model="live" />
        实时
      </label>
      <SButton class="button" :disabled="busy" @click="load()">刷新</SButton>
    </div>
  </div>
  <form class="page-toolbar trace-filters" @submit.prevent="reset">
    <div class="search-field">
      <UiIcon name="search" :size="17" />
      <SInput v-model="filters.query" placeholder="搜索" aria-label="搜索" />
    </div>
    <SInput v-model="filters.run_id" placeholder="运行 ID" aria-label="运行 ID" />
    <SInput
      v-model="filters.plugin_id"
      :placeholder="kind === 'logs' ? '来源' : '来源插件'"
      aria-label="来源"
    />
    <SSelect v-if="kind === 'logs'" v-model="filters.level" aria-label="级别">
      <option value="">全部级别</option>
      <option value="info">信息</option>
      <option value="warning">警告</option>
      <option value="error">错误</option>
    </SSelect>
    <SSelect v-else v-model="filters.status" aria-label="状态">
      <option value="">全部状态</option>
      <option value="running">运行中</option>
      <option value="waiting">等待答复</option>
      <option value="done">已完成</option>
      <option value="failed">失败</option>
      <option value="cancelled">已取消</option>
      <option value="interrupted">已中断</option>
    </SSelect>
    <SButton class="button" type="submit">筛选</SButton>
  </form>
  <SCard class="surface table-surface">
    <div class="table-scroll">
      <STable class="data-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>{{ kind === 'logs' ? '日志事件' : '调用函数' }}</th>
            <th>来源</th>
            <th>状态</th>
            <th>运行 ID</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in items" :key="row.id">
            <td>{{ formatDate('at' in row ? row.at : row.started) }}</td>
            <td class="mono">{{ 'event' in row ? row.event : row.tool_name }}</td>
            <td>{{ 'source' in row ? row.source : row.plugin_id }}</td>
            <td><UiBadge :status="'level' in row ? row.level : row.status" /></td>
            <td class="mono trace-run">{{ row.run_id || '—' }}</td>
            <td><SButton class="text-button" @click="detail = row">详情</SButton></td>
          </tr>
        </tbody>
      </STable>
    </div>
    <UiEmpty v-if="!items.length" />
    <div v-if="next" class="form-actions">
      <SButton class="button" :disabled="busy" @click="load(true)">加载更多</SButton>
    </div>
  </SCard>
  <UiModal :open="!!detail" title="追踪详情" wide @close="detail = null">
    <div v-if="detail?.run_id" class="page-toolbar">
      <RouterLink
        class="button"
        :to="{ path: kind === 'logs' ? '/tool-calls' : '/logs', query: { run_id: detail.run_id } }"
        @click="detail = null"
      >
        {{ kind === 'logs' ? '工具调用' : '追踪日志' }}
      </RouterLink>
    </div>
    <pre class="json-block">{{ JSON.stringify(payload, null, 2) }}</pre>
  </UiModal>
</template>
