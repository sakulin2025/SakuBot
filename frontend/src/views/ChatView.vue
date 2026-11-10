<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { api, ApiError, formatDate } from '../api'
import { useConsole } from '../stores/console'
import UiIcon from '../components/UiIcon.vue'
import UiModal from '../components/UiModal.vue'
import MessageContent from '../components/MessageContent.vue'
import ChatInput from '../components/ChatInput.vue'
import { buildTimeline } from '../chat/timeline'
import { sessionToken, unauthorized } from '../credentials'
interface Message {
  id: number
  uid: string
  at: number
  source: string
  label: string
  text: string
  status: string
  kind?: string
  wake_stage?: string
  role: 'user' | 'assistant' | 'event'
  meta: Record<string, unknown>
  target: string
}
interface ModelStep {
  request_id: string
  run_id: string
  step: number
  content: string
  status: string
}
interface Activity {
  id?: number
  at: number
  source?: string
  event: string
  run_id: string
  data: Record<string, unknown>
}
interface Pending {
  id: string
  text: string
  status: 'sending' | 'failed'
  error?: string
  sent_at?: number
}
interface ProcessEntry {
  key: string
  kind: 'model' | 'tool' | 'compression'
  at: number
  status: string
  finished?: number | null
  step?: number
  name?: string
  arguments?: unknown
  output?: unknown
  error?: string
}
interface ProcessRun { id: string; event_id: number; status: string; entries: ProcessEntry[] }
interface Snapshot {
  context_revision: number
  context_cutoff: number
  messages: Message[]
  before: number | null
  has_more: boolean
  live: ModelStep[]
  activity: Activity[]
  running: { id: string; event_id: number; started: number } | null
  sequence: number
  processes: ProcessRun[]
  tools?: {
    key: string
    name: string
    status: string
    arguments?: unknown
    output?: unknown
    error?: string
    agent_id: string
  }[]
}
const store = useConsole()
const messages = ref<Message[]>([]),
  steps = ref<ModelStep[]>([]),
  activity = ref<Activity[]>([]),
  pending = ref<Pending[]>([])
const tools = ref<
  {
    key: string
    name: string
    status: string
    arguments?: unknown
    output?: unknown
    error?: string
    agent_id: string
  }[]
>([])
const text = ref(''),
  error = ref(''),
  socketState = ref('connecting'),
  loading = ref(false),
  olderBusy = ref(false)
const before = ref<number | null>(null),
  hasMore = ref(false),
  running = ref<Snapshot['running']>(null)
const feed = ref<HTMLElement>(),
  follow = ref(true)
const composerHeight = ref(52)
const processes = ref<ProcessRun[]>([])
const clock = ref(Date.now() / 1000)
function toolDuration(entry: ProcessEntry) {
  const end = entry.finished ?? (entry.status === 'running' || entry.status === 'waiting' ? clock.value : null)
  if (end == null || end - entry.at <= 10) return ''
  const seconds = Math.floor(end - entry.at)
  const hours = Math.floor(seconds / 3600), minutes = Math.floor(seconds % 3600 / 60)
  return (hours ? `${hours} 小时 ` : '') + (minutes ? `${minutes} 分 ` : '') + `${seconds % 60} 秒`
}
const selectedTool = ref<{ runId: string; key: string } | null>(null)
const stopping = ref(false)
function wakeStage(message: Message) {
  return ({ queued: '排队中', waiting: '待吸收', merged: '已合并 · 尚未提交', submitted: '已提交模型', done: '已完成', failed: '失败', interrupted: '已中断' } as Record<string, string>)[message.wake_stage || ''] || ''
}
const selectedEntry = computed(() => {
  const selection = selectedTool.value
  return selection ? processes.value.find(run => run.id === selection.runId)?.entries.find(entry => entry.key === selection.key) : undefined
})
const timeline = computed(() => buildTimeline(messages.value, processes.value))
const expandedTools = ref<Record<string, boolean>>({})
function visibleTools(key: string, entries: ProcessEntry[]) {
  return expandedTools.value[key] ? entries : entries.slice(-3)
}
function processEntry(runId: string, entry: ProcessEntry) {
  const run = processes.value.find(item => item.id === runId)
  if (!run) return
  const index = run.entries.findIndex(item => item.key === entry.key)
  if (index < 0) run.entries.push(entry)
  else run.entries[index] = { ...run.entries[index], ...entry }
  run.entries.sort((a, b) => a.at - b.at)
  void scroll()
}
let socket: WebSocket | undefined,
  reconnect: ReturnType<typeof setTimeout> | undefined,
  poll: ReturnType<typeof setInterval> | undefined,
  clockTimer: ReturnType<typeof setInterval> | undefined,
  disposed = false,
  attempt = 0,
  sequence = 0,
  wsToken = '',
  contextRevision = -1,
  contextCutoff = 0
const activeSteps = computed(() =>
  steps.value.filter((step) => step.run_id === running.value?.id && step.content),
)
const ghost = computed(() => activeSteps.value.at(-1))
const canSend = computed(
  () => store.config?.enabled && !!store.agents.find((agent) => agent.id === 'main')?.ready,
)
const retryMessage = ref<Message | null>(null)
const retryBusy = ref(false)
const retryError = ref('')
async function retryWake() {
  if (!retryMessage.value || retryBusy.value) return
  retryBusy.value = true
  retryError.value = ''
  try {
    const result = await api<{ message: Message }>('chat/retry', { body: { event_id: retryMessage.value.id } })
    merge(result.message)
    retryMessage.value = null
  } catch (err) {
    retryError.value = err instanceof Error ? err.message : '重试失败'
  } finally { retryBusy.value = false }
}
const rollbackMessage = ref<Message | null>(null)
const rollbackBusy = ref(false)
const rollbackError = ref('')
async function rollbackChat() {
  if (!rollbackMessage.value || rollbackBusy.value) return
  rollbackBusy.value = true
  rollbackError.value = ''
  try {
    const data = await api<Snapshot>('chat/rollback', { body: {
      event_id: rollbackMessage.value.id, revision: contextRevision, confirmation: '回退',
    } })
    snapshot(data, true, true)
    rollbackMessage.value = null
  } catch (err) {
    rollbackError.value = err instanceof Error ? err.message : '回退失败'
  } finally { rollbackBusy.value = false }
}
function pretty(value: unknown) {
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2)
}
async function scroll() {
  await nextTick()
  if (follow.value && feed.value) feed.value.scrollTop = feed.value.scrollHeight
}
function trackScroll() {
  if (feed.value)
    follow.value = feed.value.scrollHeight - feed.value.scrollTop - feed.value.clientHeight < 100
}
function clearPage(revision: number, cutoff: number) {
  if (revision <= contextRevision) return
  contextRevision = revision
  contextCutoff = cutoff
  messages.value = []
  steps.value = []
  activity.value = []
  tools.value = []
  processes.value = []
  expandedTools.value = {}
  selectedTool.value = null
  pending.value = []
  running.value = null
  before.value = null
  hasMore.value = false
  error.value = ''
  follow.value = true
}
function merge(row: Message) {
  if (row.id <= contextCutoff) return
  const index = messages.value.findIndex((item) => item.id === row.id)
  if (index < 0) messages.value.push(row)
  else messages.value[index] = row
  messages.value.sort((a, b) => a.id - b.id)
  pending.value = pending.value.filter((item) => 'web-chat:' + item.id !== row.uid)
  void scroll()
}
function snapshot(data: Snapshot, replace = true, authoritative = false) {
  if (data.context_revision < contextRevision) return
  clearPage(data.context_revision, data.context_cutoff)
  if (replace) {
    const stale = !authoritative && data.sequence < sequence
    const combined = new Map<number, Message>()
    for (const row of stale ? [...data.messages, ...messages.value] : [...messages.value, ...data.messages])
      combined.set(row.id, row)
    messages.value = [...combined.values()].filter((row) => row.id > contextCutoff)
    if (!stale) {
      steps.value = data.live
      activity.value = data.activity
      running.value = data.running
      tools.value = data.tools || []
    }
  } else
    for (const row of data.messages) {
      if (!messages.value.some((item) => item.id === row.id)) messages.value.push(row)
    }
  messages.value.sort((a, b) => a.id - b.id)
  if (!replace || authoritative || data.sequence >= sequence) {
    for (const run of data.processes || []) {
      const index = processes.value.findIndex(item => item.id === run.id)
      if (index < 0) processes.value.push(run)
      else processes.value[index] = run
    }
  }
  pending.value = pending.value.filter(
    (item) => !messages.value.some((row) => row.uid === 'web-chat:' + item.id),
  )
  if (!replace || before.value === null) {
    before.value = data.before
    hasMore.value = data.has_more
  }
  sequence = authoritative ? data.sequence : Math.max(sequence, data.sequence)
  void scroll()
}
async function refresh() {
  loading.value = true
  try {
    snapshot(await api<Snapshot>('chat'))
    error.value = ''
  } catch {
    error.value = '加载失败'
  } finally {
    loading.value = false
  }
}
async function older() {
  if (!before.value) return
  olderBusy.value = true
  const height = feed.value?.scrollHeight || 0
  const top = feed.value?.scrollTop || 0
  try {
    snapshot(await api<Snapshot>('chat?before=' + before.value), false)
    await nextTick()
    if (feed.value) feed.value.scrollTop = top + feed.value.scrollHeight - height
  } catch {
    error.value = '加载失败'
  } finally {
    olderBusy.value = false
  }
}
function runDone(id: string, status: string, message?: string) {
  const eventId = running.value?.id === id ? running.value.event_id : null
  if (eventId) {
    const row = messages.value.find((row) => row.id === eventId)
    if (row) row.status = status
  }
  if (running.value?.id === id) running.value = null
  const process = processes.value.find(item => item.id === id)
  if (process) process.status = status
  for (const step of steps.value.filter((step) => step.run_id === id)) step.status = status
  if (message) error.value = message
  void scroll()
}
function receive(packet: Record<string, any>) {
  if (packet.type === 'snapshot') {
    snapshot(packet as unknown as Snapshot, true, true)
    socketState.value = 'online'
    attempt = 0
    return
  }
  if (packet.type === 'resync') {
    void refresh()
    return
  }
  if (packet.type === 'ping') return
  if (packet.sequence && packet.sequence <= sequence) return
  if (packet.sequence) sequence = packet.sequence
  if (packet.type === 'context.cleared') clearPage(packet.revision, packet.cutoff)
  else if (packet.type === 'message') merge(packet.message)
  else if (packet.type === 'ack') merge(packet.message)
  else if (packet.type === 'send.error') {
    const item = pending.value.find((item) => item.id === packet.client_id)
    if (item) {
      item.status = 'failed'
      item.error = packet.error
    }
  } else if (packet.type === 'plugin.state') void store.refreshStatus()
  else if (packet.type === 'run.started') {
    running.value = { id: packet.run_id, event_id: packet.event_id, started: packet.at }
    if (!processes.value.some(item => item.id === packet.run_id)) processes.value.push({ id: packet.run_id, event_id: packet.event_id, status: 'running', entries: [] })
    tools.value = []
    steps.value = []
    const row = messages.value.find((row) => row.id === packet.event_id)
    if (row) row.status = 'running'
    void scroll()
  } else if (packet.type === 'run.completed') runDone(packet.run_id, 'done')
  else if (packet.type === 'run.failed') runDone(packet.run_id, 'failed', packet.error)
  else if (packet.type === 'model.started') {
    processEntry(packet.run_id, { key: 'model:' + packet.step, kind: 'model', at: packet.at, step: packet.step, status: 'running' })
    steps.value = steps.value.filter(step => step.request_id !== packet.request_id)
    steps.value.push({
      request_id: packet.request_id,
      run_id: packet.run_id,
      step: packet.step,
      content: '',
      status: 'running',
    })
  }
  else if (packet.type === 'model.delta') {
    let step = steps.value.find((step) => step.request_id === packet.request_id)
    if (!step) {
      step = { request_id: packet.request_id, run_id: packet.run_id, step: 1, content: '', status: 'running' }
      steps.value.push(step)
    }
    step.content = (step.content + packet.text).slice(-200000)
    void scroll()
  } else if (packet.type === 'model.completed' || packet.type === 'model.failed') {
    const step = steps.value.find((step) => step.request_id === packet.request_id)
    if (step) {
      step.status = packet.type === 'model.completed' ? 'done' : 'failed'
      const entry = processes.value.find(item => item.id === packet.run_id)?.entries.find(item => item.key === 'model:' + step.step)
      if (entry) entry.status = step.status
    }
  } else if (packet.type === 'activity') {
    activity.value.push(packet.activity)
    activity.value = activity.value.slice(-100)

  } else if (packet.type === 'compression.started') {
    processEntry(packet.run_id, { key: 'compression:' + packet.compression_id, kind: 'compression', at: packet.at, status: 'running' })
  } else if (packet.type === 'compression.completed' || packet.type === 'compression.failed') {
    const entry = processes.value.find(item => item.id === packet.run_id)?.entries.find(item => item.key === 'compression:' + packet.compression_id)
    if (entry) { entry.status = packet.type === 'compression.completed' ? 'done' : 'failed'; entry.finished = packet.at; entry.error = packet.error }
  } else if (packet.type === 'tool.started') {
    processEntry(packet.run_id, { key: 'tool:' + packet.call_id, kind: 'tool', at: packet.at, name: packet.name, status: 'running', arguments: packet.arguments })
    tools.value.push({
      key: packet.run_id + ':' + packet.call_id,
      name: packet.name,
      status: 'running',
      arguments: packet.arguments,
      agent_id: packet.agent_id,
    })
  }
  else if (packet.type === 'tool.completed' || packet.type === 'tool.failed') {
    const tool = tools.value.find((tool) => tool.key === packet.run_id + ':' + packet.call_id)
    if (tool) {
      tool.status = packet.type === 'tool.completed' ? 'done' : 'failed'
      tool.output = packet.output
      tool.error = packet.error
    }
    const entry = processes.value.find(item => item.id === packet.run_id)?.entries.find(item => item.key === 'tool:' + packet.call_id)
    if (entry) { entry.status = packet.type === 'tool.completed' ? 'done' : 'failed'; entry.finished = packet.at; entry.output = packet.output; entry.error = packet.error }
    void scroll()
  }
}
function connect() {
  if (disposed) return
  socketState.value = 'connecting'
  wsToken = sessionToken()
  const current = new WebSocket(
    (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/api/chat/live',
  )
  socket = current
  current.onopen = () => current.send(JSON.stringify({ token: wsToken }))
  current.onmessage = (event) => {
    if (socket !== current) return
    try {
      receive(JSON.parse(event.data))
    } catch {
      error.value = '实时数据读取失败'
    }
  }
  current.onclose = (event) => {
    if (disposed || socket !== current) return
    socketState.value = 'offline'
    if (event.code === 4401 && wsToken === sessionToken()) {
      unauthorized(wsToken)
      reconnect = setTimeout(connect, 1000)
      return
    }
    reconnect = setTimeout(connect, Math.min(10000, 1000 * 2 ** Math.min(attempt++, 4)))
  }
  current.onerror = () => current.close()
}
async function dispatch(item: Pending) {
  item.status = 'sending'
  item.error = ''
  item.sent_at = Date.now()
  try {
    if (socket?.readyState === WebSocket.OPEN && socketState.value === 'online')
      socket.send(JSON.stringify({ type: 'send', text: item.text, client_id: item.id }))
    else {
      const result = await api<{ message: Message }>('chat', {
        body: { text: item.text, client_id: item.id },
      })
      merge(result.message)
    }
  } catch (exc) {
    item.status = 'failed'
    item.error = exc instanceof ApiError && exc.status === 400 ? '发送失败' : '连接失败'
  }
  void scroll()
}
async function send() {
  if (!canSend.value || !text.value.trim()) return
  const item: Pending = {
    id:
      crypto.randomUUID?.() ??
      Array.from(crypto.getRandomValues(new Uint8Array(16)), (value) =>
        value.toString(16).padStart(2, '0'),
      ).join(''),
    text: text.value,
    status: 'sending',
  }
  pending.value.push(item)
  text.value = ''
  follow.value = true
  await dispatch(item)
}
async function stopRun() {
  const runId = running.value?.id
  if (!runId || stopping.value) return
  stopping.value = true
  try {
    await api('chat/stop', { body: { run_id: runId } })
    await refresh()
  } catch (exc) {
    store.toast(exc instanceof Error ? exc.message : '停止失败', true)
  } finally {
    stopping.value = false
  }
}
onMounted(() => {
  connect()
  clockTimer = setInterval(() => { clock.value = Date.now() / 1000 }, 1000)
  poll = setInterval(() => {
    for (const item of pending.value) {
      if (item.status === 'sending' && item.sent_at && Date.now() - item.sent_at > 30000) {
        item.status = 'failed'
        item.error = '未确认发送'
      }
    }
    if (!document.hidden && socketState.value !== 'online') void refresh()
  }, 5000)
})
onUnmounted(() => {
  disposed = true
  clearTimeout(reconnect)
  clearInterval(poll)
  clearInterval(clockTimer)
  socket?.close()
})
</script>
<template>
  <div class="chat-page">
    <div class="chat-layout">
      <SCard class="chat-main" :style="{ '--composer-height': `${composerHeight}px` }">
        <div ref="feed" class="chat-feed" @scroll="trackScroll">
          <div class="chat-history">
            <SButton v-if="hasMore" variant="text" :loading="olderBusy" @click="older">更早消息</SButton>
          </div>
          <template v-for="item in timeline" :key="item.key">
          <template v-if="item.kind === 'message'">
          <template v-for="message in [item.message]" :key="message.uid">
            <div v-if="message.role === 'event'" class="chat-event">
              <div class="chat-event-head">
                <UiIcon name="events" :size="13" />
                <span>{{ message.label || message.source }}</span>
                <time>{{ formatDate(message.at) }}</time>
                <SButton v-if="message.kind === 'wake' && message.status === 'failed'" variant="text" :disabled="store.config?.enabled === false" @click="retryError = ''; retryMessage = message">重试</SButton>
                <SButton v-if="message.kind === 'wake'" variant="text" :disabled="!!running" title="回退到此消息之前" @click="rollbackError = ''; rollbackMessage = message">回退</SButton>
              </div>
              <pre>{{ message.text }}</pre>
            </div>
            <article v-else class="chat-message" :class="message.role">
              <div class="chat-message-meta">
                <strong>{{ message.role === 'assistant' ? 'SakuBot' : message.label || '主人' }}</strong>
                <span>
                  {{ message.meta.source_label || (message.source === 'web-chat' ? '网页' : message.source) }}
                </span>
                <time>{{ formatDate(message.at) }}</time>
                <SButton v-if="message.kind === 'wake' && message.status === 'failed'" variant="text" :disabled="store.config?.enabled === false" @click="retryError = ''; retryMessage = message">重试</SButton>
                <SButton v-if="message.kind === 'wake'" variant="text" :disabled="!!running" title="回退到此消息之前" @click="rollbackError = ''; rollbackMessage = message">回退</SButton>
                <STag
                  v-if="
                    message.role === 'user' &&
                    ['pending', 'running', 'failed', 'interrupted'].includes(message.status)
                  "
                  :status="message.status"
                  :label="wakeStage(message)"
                />
              </div>
              <div class="chat-bubble">
                <MessageContent :text="message.text" :parts="message.meta.parts" />
              </div>
            </article>
          </template>
          </template>
          <section v-else-if="item.kind === 'tools'" class="chat-run">
            <div class="chat-tools-header">
              <strong>工具调用</strong>
              <SButton v-if="item.entries.length > 3" variant="text" :aria-expanded="!!expandedTools[item.key]" @click="expandedTools[item.key] = !expandedTools[item.key]">
                {{ expandedTools[item.key] ? '收起' : `展开全部（${item.entries.length}）` }}
              </SButton>
            </div>
            <button v-for="entry in visibleTools(item.key, item.entries)" :key="entry.key" type="button" class="chat-run-entry chat-run-button" @click="selectedTool = { runId: item.runId, key: entry.key }">
              <span class="chat-run-head">
                <UiIcon name="plugins" :size="14" />
                <strong :class="{ 'tool-running': entry.status === 'running' || entry.status === 'waiting' }">{{ entry.name }}</strong>
                <STag v-if="entry.status === 'failed' || entry.status === 'interrupted'" :status="entry.status" />
                <span v-if="toolDuration(entry)" class="tool-duration">{{ toolDuration(entry) }}</span>
              </span>
            </button>
          </section>
          <div v-else class="chat-run chat-run-entry compression">
            <div class="chat-run-head">
              <UiIcon name="memory" :size="14" />
              <strong :class="{ 'tool-running': item.entry.status === 'running' }">{{ item.entry.status === 'running' ? '正在压缩上下文' : item.entry.status === 'failed' ? '上下文压缩失败' : '上下文压缩完成' }}</strong>
              <STag v-if="item.entry.status === 'failed'" status="failed" />
            </div>
          </div>
          </template>
          <article v-for="item in pending" :key="item.id" class="chat-message user">
            <div class="chat-message-meta">
              <strong>主人</strong>
              <STag
                :status="item.status === 'failed' ? 'failed' : 'pending'"
                :label="item.status === 'failed' ? '发送失败' : '发送中'"
              />
              <SButton v-if="item.status === 'failed'" variant="text" @click="dispatch(item)">重试</SButton>
            </div>
            <div class="chat-bubble">{{ item.text }}</div>
            <span v-if="item.error" class="form-error">{{ item.error }}</span>
          </article>
          <article
            v-if="
              running &&
              !messages.some((message) => message.role === 'assistant' && message.meta.run_id === running?.id)
            "
            class="chat-message assistant"
          >
            <div class="chat-message-meta">
              <strong>SakuBot</strong>
              <span class="chat-live-dot" />
              <span>生成中</span>
            </div>
            <div v-if="ghost" class="chat-bubble streaming">{{ ghost.content }}</div>
            <div v-else class="chat-typing">
              <i />
              <i />
              <i />
            </div>
          </article>
          <SEmpty v-if="!messages.length && !pending.length && !running" label="暂无消息" icon="chat" />
        </div>
        <ChatInput v-model="text" class="chat-composer" :disabled="!canSend" :inactive="store.config?.enabled === false" :running="!!running" :stopping="stopping" @send="send" @stop="stopRun" @resize="composerHeight = $event">
          <span v-if="error" class="form-error" role="alert">{{ error }}</span>
            <RouterLink
              v-if="!store.agents.find((agent) => agent.id === 'main')?.ready"
              to="/model"
              class="text-button"
            >
              模型
            </RouterLink>
        </ChatInput>
      </SCard>
    </div>
    <UiModal :open="!!retryMessage" title="重试失败的请求" @close="!retryBusy && (retryMessage = null)">
      <p v-if="retryError" class="form-error">{{ retryError }}</p>
      <template #footer>
        <SButton :disabled="retryBusy" @click="retryMessage = null">取消</SButton>
        <SButton :loading="retryBusy" @click="retryWake">确认重试</SButton>
      </template>
    </UiModal>
    <UiModal :open="!!rollbackMessage" title="确认回退主对话" @close="!rollbackBusy && (rollbackMessage = null)">
      <p>将此消息及之后的内容移出主上下文和聊天窗口，运行日志保留。已执行的工具操作不会撤销。</p>
      <pre>{{ rollbackMessage?.text }}</pre>
      <p v-if="rollbackError" class="form-error">{{ rollbackError }}</p>
      <SButton :disabled="rollbackBusy" @click="rollbackMessage = null">取消</SButton>
      <SButton :loading="rollbackBusy" @click="rollbackChat">确认回退</SButton>
    </UiModal>
    <UiModal :open="!!selectedTool" :title="selectedEntry?.name || '工具调用'" wide @close="selectedTool = null">
      <div v-if="selectedEntry" class="tool-detail">
        <STag v-if="selectedEntry.status === 'failed' || selectedEntry.status === 'interrupted'" :status="selectedEntry.status" />
        <div v-if="selectedEntry.arguments !== undefined"><strong>参数</strong><pre>{{ pretty(selectedEntry.arguments) }}</pre></div>
        <div v-if="selectedEntry.output"><strong>结果</strong><pre>{{ pretty(selectedEntry.output) }}</pre></div>
        <span v-if="selectedEntry.error" class="form-error">{{ selectedEntry.error }}</span>
      </div>
    </UiModal>
  </div>
</template>
<style scoped>
.chat-page { height: 100%; min-height: 0; }
.chat-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 18px;
  height: 100%;
  min-height: 0;
}
.chat-main {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  border-radius: 0;
}
.chat-feed {
  flex: 1;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 12px 26px calc(var(--composer-height) + 42px);
  scrollbar-width: thin;
  scrollbar-color: var(--palette-bg-ddd7ee) transparent;
}
.chat-history {
  text-align: center;
  margin-bottom: 12px;
}
.chat-message {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  margin: 18px 0;
  gap: 7px;
}
.chat-message.user {
  align-items: flex-end;
}
.chat-message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 10px;
  color: var(--muted);
}
.chat-message-meta strong {
  font-weight: 550;
  color: var(--ink);
}
.chat-message-meta .badge {
  font-size: 9px;
  min-height: 17px;
  padding: 0 4px;
}
.chat-bubble {
  max-width: 90%;
  padding: 12px 16px;
  border-radius: 3px 14px 14px;
  background: var(--palette-bg-f5f3fa);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 13px;
  line-height: 1.85;
}
.user .chat-bubble {
  background: var(--palette-bg-eee9fc);
  border-radius: 14px 3px 14px 14px;
  color: var(--palette-text-554876);
}
.assistant .chat-bubble {
  background: var(--palette-bg-f8f7fb);
  border: 1px solid var(--palette-border-efeaf5);
}
.chat-event {
  margin: 10px 0;
  color: var(--muted);
  font-size: 11px;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  background: var(--palette-bg-fdfcfe);
}
.chat-event-head {
  display: flex;
  align-items: center;
  gap: 7px;
}
.chat-event time {
  margin-left: auto;
}
.chat-event pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font: 11px/1.7 var(--mono);
}
.chat-composer {
  position: absolute;
  bottom: 18px;
  left: 26px;
  right: 26px;
  z-index: 1;
}
.chat-run {
  margin: 10px 0 16px 13px;
  padding-left: 16px;
  border-left: 2px solid var(--palette-border-e7e0f4);
  max-width: min(90%, 900px);
}
.chat-tools-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 6px; font-size: 11px; color: var(--muted); }
.chat-run-entry {
  padding: 3px 0;
  margin: 4px 0;
}
.chat-run-head { display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: 11px; }
.chat-run-button { display: block; max-width: 100%; text-align: left; font: inherit; cursor: pointer; border: 0; background: none; }
.chat-run-button:hover strong { color: var(--accent); }
.chat-run-button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.chat-run-head strong { color: var(--ink); font-weight: 550; overflow-wrap: anywhere; }
.chat-run-head .tool-running { background: linear-gradient(110deg, var(--ink) 20%, var(--palette-bg-ae7ee9) 45%, var(--palette-bg-f1d8ff) 50%, var(--palette-bg-ae7ee9) 55%, var(--ink) 80%); background-size: 220% 100%; background-clip: text; -webkit-background-clip: text; color: transparent; animation: tool-glow 2s linear infinite, tool-sway 1.8s ease-in-out infinite; }
.tool-duration { white-space: nowrap; }
@keyframes tool-glow { to { background-position: -220% 0; } }
@keyframes tool-sway { 50% { transform: translateX(2px); } }
@media (prefers-reduced-motion: reduce) { .chat-run-head .tool-running { animation: none; background: none; color: var(--accent); } }
.tool-detail { display: grid; gap: 14px; }
.tool-detail strong { font-size: 12px; }
.tool-detail pre { font: 12px/1.65 var(--mono); white-space: pre-wrap; overflow-wrap: anywhere; max-height: 45vh; overflow: auto; background: var(--palette-bg-f4f2f8); padding: 12px; border-radius: 6px; margin: 8px 0 0; }
.chat-live-dot {
  width: 5px;
  height: 5px;
  background: var(--accent);
  border-radius: 50%;
  animation: chat-pulse 1.3s infinite;
}
.chat-typing {
  display: flex;
  gap: 5px;
  padding: 14px 16px;
  background: var(--palette-bg-f8f7fb);
  border-radius: 12px;
}
.chat-typing i {
  width: 5px;
  height: 5px;
  background: var(--palette-bg-b2a4d8);
  border-radius: 50%;
  animation: chat-pulse 1s infinite;
}
.chat-typing i:nth-child(2) {
  animation-delay: 0.15s;
}
.chat-typing i:nth-child(3) {
  animation-delay: 0.3s;
}
@keyframes chat-pulse {
  50% {
    opacity: 0.3;
  }
}
@media (max-width: 760px) {
  .chat-feed {
    padding: 10px 15px calc(var(--composer-height) + 32px);
  }
  .chat-composer { left: 15px; right: 15px; bottom: 12px; }
  .chat-bubble {
    max-width: 96%;
  }
}

 :global(html[data-theme="dark"]) .chat-bubble, :global(html[data-theme="dark"]) .assistant .chat-bubble, :global(html[data-theme="dark"]) .chat-typing { background: var(--palette-dark-bg-2c2937); color: var(--ink); border-color: var(--border); }
:global(html[data-theme="dark"]) .user .chat-bubble { background: var(--palette-dark-bg-3a3152); color: var(--palette-dark-text-e8dfff); }
:global(html[data-theme="dark"]) .chat-event { background: var(--surface-alt); border-color: var(--border); }
:global(html[data-theme="dark"]) .chat-run { border-color: var(--palette-dark-border-4c425e); }
:global(html[data-theme="dark"]) .tool-detail pre { background: var(--surface-alt); color: var(--ink); }
</style>
