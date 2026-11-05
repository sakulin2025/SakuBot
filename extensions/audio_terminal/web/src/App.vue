<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, usePluginHost } from '@sakubot/ui'
const host = usePluginHost()
const state = ref<any>({ connected: false, items: [], events: [] })
const selected = ref(''), busy = ref(false), error = ref(''), loading = ref(false)
const action = ref('volume'), volume = ref(40), module = ref('knock'), mode = ref('vad'), session = ref(false)
const file = ref<File | null>(null), filter = ref(''), detail = ref<any>(null)
let timer: ReturnType<typeof setTimeout> | undefined, closed = false
const device = computed<any>(() => state.value.items.find((row:any) => row.device_id === selected.value))
const online = computed(() => state.value.connected && device.value?.online === true)
const modules = computed(() => (device.value?.hello?.capabilities?.wake_modules || []).map((value:string) => ({value,label:({knock:'双击敲桌',keyword:'唤醒词',disabled:'关闭'} as any)[value] || value})))
const events = computed(() => state.value.events.filter((row:any) => row.event.startsWith(filter.value)))
const status = computed(() => device.value?.status || {})
const time = (value:number) => value ? new Date(value).toLocaleTimeString('zh-CN', {hour12:false}) : '--'
async function load() {
  if (loading.value || closed) return
  loading.value = true
  const identity = selected.value
  try {
    const value:any = await host.api('state' + (identity ? '?device=' + encodeURIComponent(identity) : ''))
    if (identity !== selected.value || closed) return
    state.value = value; error.value = ''
    if (!selected.value && value.items.length) selected.value = value.items[0].device_id
  } catch (e:any) { error.value = e.message }
  finally { loading.value = false }
}
async function run(callback:() => Promise<unknown>, message:string) {
  if (busy.value) return
  busy.value = true
  try { await callback(); host.toast(message); await load() }
  catch (e:any) { host.toast(e.message, true) }
  finally { busy.value = false }
}
function command(name:string, parameters:any = {}) {
  return host.api('control', {device:selected.value, action:name, parameters})
}
function apply() {
  const params = action.value === 'volume' ? {volume:Number(volume.value)} : action.value === 'wake' ? {module:module.value} : {mode:mode.value, ...(mode.value === 'session' ? {session_open:session.value} : {})}
  return run(() => command(action.value, params), '已应用')
}
async function poll() {
  await load()
  if (!closed) timer = setTimeout(poll, 2500)
}
watch(selected, () => { state.value.events = []; void load() })
onMounted(() => { void poll() })
onUnmounted(() => { closed = true; clearTimeout(timer) })
</script>

<template>
  <SPageHeader title="音频终端">
    <STag :status="state.connected ? 'online' : 'offline'" :label="state.connected ? '服务已连接' : '服务未连接'" />
    <SButton icon="settings" @click="host.navigate('/plugins')">插件设置</SButton>
    <SButton icon="refresh" :loading="busy" @click="run(() => host.api('refresh', {}), '已刷新')">刷新设备</SButton>
  </SPageHeader>
  <p v-if="error || state.error" class="error">{{ error || state.error }}</p>
  <div class="toolbar">
    <SSelect v-model="selected" :options="state.items.map((row:any) => ({value:row.device_id,label:row.device_id + (row.online === true ? ' · 在线' : row.online === false ? ' · 离线' : ' · 未知')}))" placeholder="选择设备" />
    <STag v-if="device" :status="online ? 'online' : 'offline'" :label="online ? '设备在线' : device.online === null ? '状态未知' : '设备离线'" />
    <STag v-if="device" :status="device.events_connected ? 'online' : 'pending'" :label="!state.subscribe_events ? '事件订阅已关闭' : device.events_connected ? '事件已连接' : '事件重连中'" />
  </div>
  <SEmpty v-if="!device" label="暂无设备" />
  <template v-else>
    <div class="panels">
      <SCard title="设备状态">
        <template #actions><SButton size="small" :disabled="!online" :loading="busy" @click="run(() => command('status'), '状态已刷新')">查询状态</SButton></template>
        <dl>
          <dt>固件</dt><dd>{{ status.firmware_version || device.hello?.firmware || '--' }}</dd>
          <dt>唤醒模块</dt><dd>{{ status.wake_module || '--' }}</dd>
          <dt>上传策略</dt><dd>{{ status.upload_mode || '--' }}</dd>
          <dt>音量</dt><dd>{{ status.volume == null ? '--' : status.volume + '%' }}</dd>
          <dt>播放</dt><dd>{{ status.playing ? '播放中 · ' + status.playback_id : '空闲' }}</dd>
          <dt>运行时长</dt><dd>{{ status.uptime_ms == null ? '--' : Math.floor(status.uptime_ms / 60000) + ' 分钟' }}</dd>
          <dt>状态更新时间</dt><dd>{{ time(device.status_at) }}</dd>
        </dl>
        <p v-if="device.error || device.events_error" class="error padded">{{ device.error || device.events_error }}</p>
      </SCard>
      <SCard title="设备控制">
        <form class="controls" @submit.prevent="apply">
          <SSelect v-model="action" :options="[{value:'volume',label:'音量'},{value:'wake',label:'唤醒模块'},{value:'upload',label:'上传策略'}]" aria-label="操作" />
          <SInput v-if="action === 'volume'" v-model.number="volume" type="number" min="0" max="100" required aria-label="音量" />
          <SSelect v-else-if="action === 'wake'" v-model="module" :options="modules" aria-label="唤醒模块" />
          <SSelect v-else v-model="mode" :options="[{value:'vad',label:'VAD 语音'},{value:'continuous',label:'连续上传'},{value:'session',label:'会话上传'},{value:'off',label:'关闭上传'}]" aria-label="上传策略" />
          <SCheckbox v-if="action === 'upload' && mode === 'session'" v-model="session">会话打开</SCheckbox>
          <SButton type="submit" variant="primary" :disabled="!online" :loading="busy">应用</SButton>
        </form>
        <div class="controls">
          <SButton :disabled="!online" :loading="busy" @click="run(() => command('save'), '已保存到设备')">保存配置</SButton>
          <SButton :disabled="!online" :loading="busy" @click="run(() => command('stop'), '已停止播放')">停止播放</SButton>
        </div>
        <form class="controls file-row" @submit.prevent="file && run(() => host.upload('play/' + encodeURIComponent(selected), file!), '播放已接受')">
          <input type="file" accept=".wav,audio/wav" aria-label="WAV 文件" @change="file = ($event.target as HTMLInputElement).files?.[0] || null">
          <SButton type="submit" :disabled="!online || !file" :loading="busy">播放 WAV</SButton>
        </form>
      </SCard>
    </div>
  </template>
  <SCard title="设备事件" class="event-card">
    <template #actions><SSelect v-model="filter" :options="[{value:'',label:'全部'},{value:'wake.',label:'唤醒'},{value:'input.',label:'按键'},{value:'playback.',label:'播放'},{value:'device.',label:'连接'},{value:'audio.',label:'音频'}]" aria-label="事件筛选" /></template>
    <STable :rows="events" row-key="id" :columns="[{key:'received_at',label:'时间'},{key:'event',label:'事件'},{key:'device_id',label:'设备'},{key:'detail',label:'数据'}]" empty-text="暂无事件">
      <template #cell-received_at="{row}">{{ time(row.received_at) }}</template>
      <template #cell-detail="{row}"><SButton size="small" @click="detail = row">查看</SButton></template>
    </STable>
  </SCard>
  <SDialog :open="!!detail" title="事件数据" @close="detail = null"><pre>{{ JSON.stringify(detail, null, 2) }}</pre></SDialog>
</template>

<style scoped>
.toolbar,.controls{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.toolbar{margin:20px 0}.toolbar :deep(.s-select){min-width:260px}.panels{display:grid;grid-template-columns:1fr 1.2fr;gap:20px}.controls{padding:18px 22px}.controls+.controls{padding-top:0}.controls :deep(input[type=number]){width:110px}dl{display:grid;grid-template-columns:110px 1fr;gap:13px;padding:4px 22px 14px;font-size:13px}dt{color:var(--muted)}dd{margin:0;overflow-wrap:anywhere}.error{color:var(--danger,#b44343);font-size:13px}.padded{padding:0 22px 16px}.event-card{margin-top:20px}.file-row input{min-width:0;max-width:100%;font-size:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}@media(max-width:800px){.panels{grid-template-columns:1fr}.toolbar{align-items:stretch}.controls{gap:10px}}
</style>
