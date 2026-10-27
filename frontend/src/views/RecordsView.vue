<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, reactive } from 'vue'
import { useRoute } from 'vue-router'
import { api, formatDate, parseJson } from '../api'
import { useConsole } from '../stores/console'
import UiIcon from '../components/UiIcon.vue'
import UiBadge from '../components/UiBadge.vue'
import UiModal from '../components/UiModal.vue'
import UiEmpty from '../components/UiEmpty.vue'
import type { Run, Delivery } from '../types'
const props = defineProps<{ kind: string; embedded?: boolean }>()
const store = useConsole()
const records = ref<(Run | Delivery)[]>([])
const query = ref('')
const detail = ref<Record<string, unknown> | null>(null)
const filtered = computed(() => records.value.filter((r) => JSON.stringify(r).includes(query.value)))
async function load() {
  try {
    records.value = await api<(Run | Delivery)[]>(props.kind)
  } catch {
    store.toast('加载失败', true)
  }
}
async function inspect(row: Run | Delivery) {
  try {
    detail.value =
      props.kind === 'runs'
        ? await api<Record<string, unknown>>('runs/' + encodeURIComponent(row.id))
        : (row as unknown as Record<string, unknown>)
  } catch {
    store.toast('加载失败', true)
  }
}
onMounted(load)
watch(
  () => props.kind,
  () => {
    detail.value = null
    load()
  },
)
</script>
<template>
  <div class="page-heading">
    <div v-if="!embedded" class="heading-title">
      <span class="page-kicker">系统</span>
      <h1>{{ kind === 'runs' ? '运行记录' : '消息投递' }}</h1>
    </div>
    <SButton class="button" @click="load">刷新</SButton>
  </div>
  <div class="page-toolbar">
    <div class="search-field">
      <UiIcon name="search" :size="17" />
      <SInput v-model="query" :aria-label="kind === 'runs' ? '搜索 Agent 运行' : '搜索消息投递'" :placeholder="kind === 'runs' ? '搜索 Agent 运行' : '搜索消息投递'" />
    </div>
  </div>
  <SCard class="surface table-surface">
    <div class="table-scroll">
      <STable class="data-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>ID</th>
            <th>状态</th>
            <th>{{ kind === 'runs' ? '触发事件 ID' : '目标会话' }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in filtered" :key="row.id">
            <td>{{ formatDate('started' in row ? row.started : row.at) }}</td>
            <td class="mono">{{ row.id }}</td>
            <td><UiBadge :status="row.status" /></td>
            <td>{{ 'event_id' in row ? row.event_id : row.target }}</td>
            <td><SButton class="text-button" @click="inspect(row)">详情</SButton></td>
          </tr>
        </tbody>
      </STable>
    </div>
    <UiEmpty v-if="!filtered.length" />
  </SCard>
  <UiModal :open="!!detail" :title="kind === 'runs' ? 'Agent 运行详情' : '消息投递详情'" wide @close="detail = null">
    <div v-if="kind === 'runs'" class="page-toolbar">
      <RouterLink
        class="button"
        :to="{ path: '/tool-calls', query: { run_id: String(detail?.id) } }"
        @click="detail = null"
      >
        工具调用
      </RouterLink>
      <RouterLink
        class="button"
        :to="{ path: '/logs', query: { run_id: String(detail?.id) } }"
        @click="detail = null"
      >
        追踪日志
      </RouterLink>
    </div>
    <pre class="json-block">{{
      JSON.stringify(
        detail
          ? {
              ...detail,
              trace: parseJson(detail.trace),
              params: parseJson(detail.params),
              result: parseJson(detail.result),
            }
          : null,
        null,
        2,
      )
    }}</pre>
  </UiModal>
</template>
