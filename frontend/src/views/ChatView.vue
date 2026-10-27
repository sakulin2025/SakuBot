<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { api, ApiError, formatDate } from '../api'
import { useConsole } from '../stores/console'
import UiIcon from '../components/UiIcon.vue'
import MessageContent from '../components/MessageContent.vue'
interface Message {
  id: number
  uid: string
  at: number
  source: string
  label: string
  text: string
  status: string
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
  showProcess = ref(true),
  loading = ref(false),
  olderBusy = ref(false)
const before = ref<number | null>(null),
  hasMore = ref(false),
  running = ref<Snapshot['running']>(null)
const feed = ref<HTMLElement>(),
  follow = ref(true)
let socket: WebSocket | undefined,
  reconnect: ReturnType<typeof setTimeout> | undefined,
  poll: ReturnType<typeof setInterval> | undefined,
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
const activityNames: Record<string, string> = {
  'agent.started': 'Agent 开始运行',
  'model.request': '模型请求',
  'model.completed': '模型响应完成',
  'tool.started': '工具调用',
  'tool.completed': '工具调用完成',
  'tool.failed': '工具调用失败',
  'agent.completed': 'Agent 运行完成',
  'agent.failed': 'Agent 运行失败',
  'agent.interrupted': 'Agent 运行中断',
  'context.compressed': '上下文压缩',
  'team.request.waiting': '团队等待答复',
  'team.request.answered': '已答复',
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
    tools.value = []
    steps.value = []
    const row = messages.value.find((row) => row.id === packet.event_id)
    if (row) row.status = 'running'
    void scroll()
  } else if (packet.type === 'run.completed') runDone(packet.run_id, 'done')
  else if (packet.type === 'run.failed') runDone(packet.run_id, 'failed', packet.error)
  else if (packet.type === 'model.started')
    steps.value.push({
      request_id: packet.request_id,
      run_id: packet.run_id,
      step: packet.step,
      content: '',
      status: 'running',
    })
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
    if (step) step.status = packet.type === 'model.completed' ? 'done' : 'failed'
  } else if (packet.type === 'activity') {
    activity.value.push(packet.activity)
    activity.value = activity.value.slice(-100)
  } else if (packet.type === 'tool.started')
    tools.value.push({
      key: packet.run_id + ':' + packet.call_id,
      name: packet.name,
      status: 'running',
      arguments: packet.arguments,
      agent_id: packet.agent_id,
    })
  else if (packet.type === 'tool.completed' || packet.type === 'tool.failed') {
    const tool = tools.value.find((tool) => tool.key === packet.run_id + ':' + packet.call_id)
    if (tool) {
      tool.status = packet.type === 'tool.completed' ? 'done' : 'failed'
      tool.output = packet.output
      tool.error = packet.error
    }
  }
}
function connect() {
  if (disposed) return
  socketState.value = 'connecting'
  wsToken = sessionStorage.getItem('sakubot-token') || ''
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
    if (event.code === 4401 && wsToken === (sessionStorage.getItem('sakubot-token') || '')) {
      window.dispatchEvent(new Event('sakubot-unauthorized'))
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
function key(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault()
    void send()
  }
}
async function toggle(value: boolean) {
  try {
    await store.setMainEnabled(value)
  } catch {
    store.toast('更新失败', true)
  }
}
onMounted(() => {
  connect()
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
  socket?.close()
})
</script>
<template>
  <div class="chat-page">
    <SPageHeader title="主对话">
      <STag
        :status="socketState === 'online' ? 'online' : 'pending'"
        :label="socketState === 'online' ? '实时已连接' : '重连中'"
      />
      <STag
        :status="running ? 'running' : store.config?.enabled ? 'enabled' : 'disabled'"
        :label="running ? '运行中' : store.config?.enabled ? '待命' : '已暂停'"
      />
      <SSwitch
        :model-value="!!store.config?.enabled"
        label="主 Agent"
        :loading="store.saving"
        :disabled="!store.agents.find((agent) => agent.id === 'main')?.ready && !store.config?.enabled"
        @change="toggle"
      />
      <SButton
        :variant="showProcess ? 'primary' : 'default'"
        :aria-pressed="showProcess"
        @click="showProcess = !showProcess"
        icon="activity"
      >
        运行过程
      </SButton>
    </SPageHeader>
    <div class="chat-layout" :class="{ 'with-process': showProcess }">
      <SCard class="chat-main">
        <div ref="feed" class="chat-feed" @scroll="trackScroll">
          <div class="chat-history">
            <SButton v-if="hasMore" variant="text" :loading="olderBusy" @click="older">更早消息</SButton>
          </div>
          <template v-for="message in messages" :key="message.uid">
            <details v-if="message.role === 'event'" class="chat-event">
              <summary>
                <UiIcon name="events" :size="13" />
                <span>{{ message.label || message.source }}</span>
                <time>{{ formatDate(message.at) }}</time>
              </summary>
              <pre>{{ message.text }}</pre>
            </details>
            <article v-else class="chat-message" :class="message.role">
              <div class="chat-message-meta">
                <strong>{{ message.role === 'assistant' ? 'SakuBot' : message.label || '主人' }}</strong>
                <span>
                  {{ message.meta.source_label || (message.source === 'web-chat' ? '网页' : message.source) }}
                </span>
                <time>{{ formatDate(message.at) }}</time>
                <STag
                  v-if="
                    message.role === 'user' &&
                    ['pending', 'running', 'failed', 'interrupted'].includes(message.status)
                  "
                  :status="message.status"
                />
              </div>
              <div class="chat-bubble">
                <MessageContent :text="message.text" :parts="message.meta.parts" />
              </div>
            </article>
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
        <div class="chat-composer">
          <span v-if="error" class="form-error" role="alert">{{ error }}</span>
          <STextarea
            v-model="text"
            rows="3"
            maxlength="100000"
            placeholder="发送消息"
            aria-label="发送消息"
            @keydown="key"
          />
          <div class="chat-compose-actions">
            <RouterLink
              v-if="!store.agents.find((agent) => agent.id === 'main')?.ready"
              to="/model"
              class="text-button"
            >
              模型
            </RouterLink>
            <SButton variant="primary" icon="send" :disabled="!canSend || !text.trim()" @click="send">
              发送
            </SButton>
          </div>
        </div>
      </SCard>
      <SCard v-if="showProcess" class="chat-process" title="实时运行过程">
        <div class="chat-process-content">
          <details v-for="tool in tools" :key="tool.key" class="chat-tool" open>
            <summary>
              <UiIcon name="plugins" :size="14" />
              <strong>{{ tool.name }}</strong>
              <STag :status="tool.status" />
            </summary>
            <span class="mono chat-agent">{{ tool.agent_id }}</span>
            <pre>{{ pretty(tool.arguments) }}</pre>
            <pre v-if="tool.output">{{ pretty(tool.output) }}</pre>
            <span v-if="tool.error" class="form-error">{{ tool.error }}</span>
          </details>
          <details v-for="step in steps" :key="step.request_id" class="chat-tool">
            <summary>
              <UiIcon name="model" :size="14" />
              <strong>模型 · {{ step.step }}</strong>
              <STag :status="step.status" />
            </summary>
            <pre>{{ step.content }}</pre>
          </details>
          <div v-for="(item, index) in [...activity].reverse()" :key="item.id || index" class="chat-activity">
            <span class="activity-pin" />
            <div>
              <strong>{{ activityNames[item.event] || item.event }}</strong>
              <span v-if="item.data?.function" class="mono">{{ item.data.function }}</span>
              <span v-if="item.data?.error" class="form-error">{{ item.data.error }}</span>
              <time>{{ formatDate(item.at) }}</time>
            </div>
          </div>
          <SEmpty v-if="!activity.length && !tools.length" label="暂无运行过程" icon="activity" />
        </div>
      </SCard>
    </div>
  </div>
</template>
<style scoped>
.chat-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 18px;
  height: calc(100dvh - 182px);
  min-height: 480px;
}
.chat-layout.with-process {
  grid-template-columns: minmax(0, 1fr) 310px;
}
.chat-main {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}
.chat-feed {
  flex: 1;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 12px 26px 26px;
  scrollbar-width: thin;
  scrollbar-color: #ddd7ee transparent;
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
  background: #f5f3fa;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 13px;
  line-height: 1.85;
}
.user .chat-bubble {
  background: #eee9fc;
  border-radius: 14px 3px 14px 14px;
  color: #554876;
}
.assistant .chat-bubble {
  background: #f8f7fb;
  border: 1px solid #efeaf5;
}
.chat-event {
  margin: 10px 0;
  color: var(--muted);
  font-size: 11px;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  background: #fdfcfe;
}
.chat-event summary {
  display: flex;
  align-items: center;
  gap: 7px;
  cursor: pointer;
}
.chat-event time {
  margin-left: auto;
}
.chat-event pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 250px;
  overflow: auto;
  font: 11px/1.7 var(--mono);
}
.chat-composer {
  padding: 15px 18px;
  border-top: 1px solid var(--border);
  background: #fdfcfe;
}
.chat-composer textarea {
  width: 100%;
  min-height: 75px;
  max-height: 220px;
  resize: vertical;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.7;
  background: #fff;
}
.chat-compose-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  align-items: center;
  margin-top: 10px;
}
.chat-process {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}
.chat-process-content {
  padding: 16px;
  overflow-y: auto;
  scrollbar-width: thin;
}
.chat-tool {
  border: 1px solid var(--border);
  border-radius: 9px;
  padding: 10px;
  margin-bottom: 12px;
}
.chat-tool summary {
  display: flex;
  gap: 7px;
  align-items: center;
  cursor: pointer;
  font-size: 11px;
  min-width: 0;
}
.chat-tool summary strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.chat-tool pre {
  font: 10px/1.7 var(--mono);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 260px;
  overflow: auto;
  background: #f8f7fb;
  padding: 9px;
  border-radius: 5px;
}
.chat-agent {
  font-size: 10px;
  color: var(--muted);
  display: block;
  margin-top: 7px;
}
.chat-activity {
  display: flex;
  gap: 9px;
  padding: 9px 0;
  border-bottom: 1px solid #f3f0f8;
}
.activity-pin {
  width: 5px;
  height: 5px;
  flex-shrink: 0;
  background: #b5a9dc;
  border-radius: 50%;
  margin-top: 7px;
}
.chat-activity > div {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.chat-activity strong {
  font-size: 11px;
  font-weight: 500;
}
.chat-activity span,
.chat-activity time {
  font-size: 10px;
  color: var(--muted);
  overflow-wrap: anywhere;
}
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
  background: #f8f7fb;
  border-radius: 12px;
}
.chat-typing i {
  width: 5px;
  height: 5px;
  background: #b2a4d8;
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
@media (max-width: 1100px) {
  .chat-layout.with-process {
    grid-template-columns: minmax(0, 1fr) 260px;
  }
}
@media (max-width: 760px) {
  .chat-layout {
    height: calc(100dvh - 170px);
    min-height: 380px;
  }
  .chat-layout.with-process {
    grid-template-columns: minmax(0, 1fr);
  }
  .chat-process {
    max-height: 400px;
  }
  .chat-layout.with-process {
    height: auto;
  }
  .chat-layout.with-process .chat-main {
    height: calc(100dvh - 170px);
  }
  .chat-feed {
    padding: 10px 15px;
  }
  .chat-bubble {
    max-width: 96%;
  }
}
</style>
