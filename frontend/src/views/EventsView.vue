<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api, formatDate, parseJson } from '../api'
import { useConsole } from '../stores/console'
import type { EventRecord } from '../types'
import UiIcon from '../components/UiIcon.vue'
import UiBadge from '../components/UiBadge.vue'
import UiModal from '../components/UiModal.vue'
import UiEmpty from '../components/UiEmpty.vue'
defineProps<{ embedded?: boolean }>()
const store = useConsole()
const events = ref<EventRecord[]>([])
const busy = ref(false)
const query = ref('')
const filter = ref('')
const kind = ref('all')
const cursor = ref(0)
const nextCursor = ref<number | null>(null)
const history = ref<number[]>([])
const creating = ref(false)
const submitting = ref(false)
const selected = ref<EventRecord | null>(null)
const draft = reactive({ kind: 'wake', text: '', target: '', include_context: false })
const visible = computed(() =>
  events.value.filter((event) => kind.value === 'all' || event.kind === kind.value),
)
async function load() {
  busy.value = true
  try {
    const params = new URLSearchParams({
      before: String(cursor.value),
      limit: '30',
      query: query.value,
      status: filter.value,
      kind: kind.value === 'all' ? '' : kind.value,
    })
    const result = await api<{ items: EventRecord[]; next_before: number | null }>('events?' + params)
    events.value = result.items
    nextCursor.value = result.next_before
  } catch {
    store.toast('加载失败', true)
  } finally {
    busy.value = false
  }
}
function search() {
  cursor.value = 0
  history.value = []
  load()
}
function selectKind(value: string) {
  kind.value = value
  search()
}
function create() {
  Object.assign(draft, {
    kind: 'wake',
    text: '',
    target: store.status?.main_session || '',
    include_context: false,
  })
  creating.value = true
}
async function submit() {
  submitting.value = true
  try {
    await api('events', { body: draft })
    creating.value = false
    search()
    store.toast('已创建')
  } catch {
    store.toast('创建失败', true)
  } finally {
    submitting.value = false
  }
}
async function cancel(event: EventRecord) {
  try {
    const result = await api<{ cancelled: boolean }>('events/' + event.id + '/cancel', { body: {} })
    await load()
    store.toast(result.cancelled ? '已取消' : '状态已更新')
  } catch {
    store.toast('操作失败', true)
  }
}
function older() {
  if (nextCursor.value) {
    history.value.push(cursor.value)
    cursor.value = nextCursor.value
    load()
  }
}
function newer() {
  cursor.value = history.value.pop() || 0
  load()
}
onMounted(load)
</script>
<template>
  <div class="page-heading">
    <div v-if="!embedded" class="heading-title">
      <span class="page-kicker">工作台</span>
      <h1>事件中心</h1>
    </div>
    <SButton class="button primary" @click="create">
      <UiIcon name="plus" :size="17" />
      创建事件
    </SButton>
  </div>
  <SCard class="surface">
    <div class="tab-bar">
      <SButton
        v-for="tab in [
          { value: 'all', label: '全部事件' },
          { value: 'wake', label: '唤醒 Agent' },
          { value: 'context', label: '上下文' },
          { value: 'notify', label: '直接通知' },
        ]"
        :key="tab.value"
        class="tab"
        :class="{ active: kind === tab.value }"
        @click="selectKind(tab.value)"
      >
        {{ tab.label }}
      </SButton>

      <span class="tab-spacer"></span>
      <span class="badge neutral">{{ store.pending }} 待处理</span>
    </div>
    <form class="table-toolbar" @submit.prevent="search">
      <div class="search-field">
        <UiIcon name="search" :size="17" />
        <SInput v-model="query" aria-label="搜索事件" placeholder="搜索事件" />
      </div>
      <SSelect v-model="filter" aria-label="事件状态" class="filter-select" @change="search">
        <option value="">全部状态</option>
        <option value="pending">待处理</option>
        <option value="running">进行中</option>
        <option value="done">已完成</option>
        <option value="failed">失败</option>
        <option value="interrupted">已中断</option>
        <option value="recorded">已保存</option>
      </SSelect>
      <SButton class="icon-button" type="button" aria-label="刷新事件" :disabled="busy" @click="load">
        <UiIcon name="refresh" :class="{ spinning: busy }" :size="17" />
      </SButton>
    </form>
    <div v-if="busy && !events.length" class="loading-state">
      <UiIcon name="loading" class="spinning" :size="24" />
    </div>
    <div v-else-if="visible.length" class="event-list">
      <article v-for="event in visible" :key="event.id" class="event-card">
        <div class="event-marker">
          <UiIcon :name="event.kind === 'wake' ? 'events' : 'memory'" :size="18" />
        </div>
        <div class="event-content">
          <div class="event-head">
            <strong>{{ event.label || event.source }}</strong>
            <span v-if="event.actor" class="mono subtle">{{ event.actor }}</span>
            <UiBadge :status="event.kind" />
            <span class="event-date">{{ formatDate(event.at) }}</span>
          </div>
          <p class="event-text">{{ event.text.slice(0, 380) }}{{ event.text.length > 380 ? '…' : '' }}</p>
          <div class="event-footer">
            <span class="mono">#{{ event.id }}</span>
            <span>{{ event.target }}</span>
            <div class="event-actions">
              <UiBadge :status="event.status" />
              <SButton
                v-if="event.status === 'pending'"
                class="text-button danger-text"
                @click="cancel(event)"
              >
                取消
              </SButton>
              <SButton class="text-button" @click="selected = event">
                详情
                <UiIcon name="right" :size="13" />
              </SButton>
            </div>
          </div>
        </div>
      </article>
    </div>
    <UiEmpty v-else />
    <div class="pagination">
      <span>{{ visible.length }} 条</span>
      <div>
        <SButton class="icon-button" aria-label="较新事件" :disabled="!history.length || busy" @click="newer">
          <UiIcon name="left" :size="17" />
        </SButton>
        <SButton
          class="icon-button"
          aria-label="较早事件"
          :disabled="!nextCursor || events.length < 30 || busy"
          @click="older"
        >
          <UiIcon name="right" :size="17" />
        </SButton>
      </div>
    </div>
  </SCard>
  <UiModal :open="creating" title="创建事件" @close="creating = false">
    <form id="event-form" class="form-stack" @submit.prevent="submit">
      <div class="field">
        <label for="event-kind">事件类型</label>
        <SSelect id="event-kind" v-model="draft.kind">
          <option value="wake">唤醒 Agent</option>
          <option value="context">上下文</option>
          <option value="notify">直接通知</option>
        </SSelect>
      </div>
      <div class="field">
        <label for="event-text">内容</label>
        <STextarea id="event-text" v-model="draft.text" rows="6" required></STextarea>
      </div>
      <div class="field">
        <label for="event-target">目标会话</label>
        <SInput id="event-target" v-model="draft.target" required />
      </div>
      <label v-if="draft.kind === 'notify'" class="checkbox-field">
        <SCheckbox v-model="draft.include_context" />
        加入上下文
      </label>
    </form>
    <template #footer>
      <SButton class="button" @click="creating = false">取消</SButton>
      <SButton form="event-form" class="button primary" :disabled="submitting">创建</SButton>
    </template>
  </UiModal>
  <UiModal :open="!!selected" :title="'事件 #' + (selected?.id || '')" wide @close="selected = null">
    <div v-if="selected" class="detail-stack">
      <div class="detail-meta">
        <UiBadge :status="selected.kind" />
        <UiBadge :status="selected.status" />
        <span class="mono">{{ selected.target }}</span>
      </div>
      <pre class="detail-text">{{ selected.text }}</pre>
      <details>
        <summary>元数据</summary>
        <pre class="json-block">{{ JSON.stringify(parseJson(selected.meta), null, 2) }}</pre>
      </details>
      <div v-if="selected.error" class="record-error">{{ selected.error }}</div>
    </div>
  </UiModal>
</template>
