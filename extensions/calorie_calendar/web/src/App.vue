<script setup lang="ts">
import { ref, reactive, computed, onMounted, usePluginHost, UiIcon, UiModal } from '@sakubot/ui'

type Kind = 'intake' | 'expenditure'
type Entry = { id: string; day: string; kind: Kind; label: string; kcal: number; estimated: boolean; note: string; source: string }
type Day = { day: string; intake: number; expenditure: number; balance: number; count: number; confirmed: boolean; entries: Entry[] }
type Totals = { days: number; intake: number; expenditure: number; balance: number }
type Calendar = { month: string; today: string; days: Omit<Day, 'entries'>[]; month_total: Totals; all_total: Totals }
const host = usePluginHost()
const calendar = ref<Calendar | null>(null)
const current = ref<Day | null>(null)
const month = ref('')
const selected = ref('')
const loading = ref(true)
const busy = ref(false)
const entryOpen = ref(false)
const deleting = ref<Entry | null>(null)
const error = ref('')
const special: Record<Kind, string[]> = { intake: ['早餐', '午餐', '晚餐'], expenditure: ['基础代谢', '活动消耗'] }
const draft = reactive({ id: '', date: '', kind: 'intake' as Kind, label: '早餐', custom: '', kcal: '' as string | number, estimated: false, note: '', source: '' })
const cells = computed(() => {
  if (!month.value) return []
  const [year, value] = month.value.split('-').map(Number)
  const start = (new Date(year, value - 1, 1).getDay() + 6) % 7
  const length = new Date(year, value, 0).getDate()
  const count = Math.ceil((start + length) / 7) * 7
  const records = new Map((calendar.value?.days || []).map(day => [day.day, day]))
  return Array.from({ length: count }, (_, index) => {
    const number = index - start + 1
    if (number < 1 || number > length) return null
    const day = month.value + '-' + String(number).padStart(2, '0')
    return { day, number, data: records.get(day) }
  })
})
const isCustom = computed(() => draft.label === '__custom__')
const number = (value: number) => new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value)
let dayRequest = 0
async function loadMonth(value: string) {
  loading.value = true
  try {
    const result = await host.api<Calendar>('calendar' + (value ? '?month=' + encodeURIComponent(value) : ''))
    month.value = result.month
    calendar.value = result
    if (!selected.value || !selected.value.startsWith(result.month)) selected.value = result.today.startsWith(result.month) ? result.today : result.month + '-01'
    await loadDay(selected.value)
  } catch (e) { host.toast(e instanceof Error ? e.message : '加载失败', true) }
  finally { loading.value = false }
}
async function loadDay(day: string) {
  if (selected.value !== day) current.value = null
  selected.value = day
  const request = ++dayRequest
  try {
    const result = await host.api<Day>('day?date=' + encodeURIComponent(day))
    if (request === dayRequest) current.value = result
  } catch (e) { if (request === dayRequest) host.toast(e instanceof Error ? e.message : '加载失败', true) }
}
function moveMonth(delta: number) {
  const [year, value] = month.value.split('-').map(Number)
  const d = new Date(year, value - 1 + delta, 1)
  loadMonth(d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0'))
}
function edit(entry?: Entry, kind: Kind = 'intake') {
  const entryKind = entry?.kind || kind
  const label = entry?.label || special[entryKind][0]
  const custom = !special[entryKind].includes(label)
  Object.assign(draft, { id: entry?.id || '', date: entry?.day || selected.value, kind: entryKind,
    label: custom ? '__custom__' : label, custom: custom ? label : '', kcal: entry?.kcal ?? '',
    estimated: entry?.estimated ?? false, note: entry?.note || '', source: entry?.source || '' })
  error.value = ''
  entryOpen.value = true
}
function changeKind(kind: string) {
  draft.kind = kind as Kind
  draft.label = special[draft.kind][0]
  draft.custom = ''
}
async function save() {
  busy.value = true
  error.value = ''
  try {
    const payload = { id: draft.id, date: draft.date, kind: draft.kind, label: isCustom.value ? draft.custom.trim() : draft.label,
      kcal: Number(draft.kcal), estimated: draft.estimated, note: draft.note, source: draft.source }
    if (draft.kcal === '' || !payload.label) { error.value = '请填写标签和热量'; return }
    await host.api('entry', payload)
    entryOpen.value = false
    selected.value = draft.date
    await loadMonth(draft.date.slice(0, 7))
    host.toast('已保存')
  } catch (e) { error.value = e instanceof Error ? e.message : '保存失败' }
  finally { busy.value = false }
}
async function remove() {
  if (!deleting.value) return
  busy.value = true
  try {
    await host.api('entry/' + encodeURIComponent(deleting.value.id), undefined, 'DELETE')
    deleting.value = null
    await loadMonth(month.value)
    host.toast('已删除')
  } catch (e) { host.toast(e instanceof Error ? e.message : '删除失败', true) }
  finally { busy.value = false }
}
async function confirmDay() {
  if (!current.value || busy.value) return
  busy.value = true
  try {
    await host.api('confirm', { date: selected.value, confirmed: !current.value.confirmed })
    await loadMonth(month.value)
    host.toast(current.value?.confirmed ? '已确认' : '已取消确认')
  } catch (e) { host.toast(e instanceof Error ? e.message : '操作失败', true) }
  finally { busy.value = false }
}
onMounted(() => loadMonth(''))
</script>

<template>
  <div class="calorie-page">
    <div v-if="calendar" class="totals-strip">
      <div class="total-group"><span>本月已确认 · {{ calendar.month_total.days }} 天</span><strong>摄入 {{ number(calendar.month_total.intake) }} <small>kcal</small></strong><strong>消耗 {{ number(calendar.month_total.expenditure) }} <small>kcal</small></strong><strong>收支 {{ number(calendar.month_total.balance) }} <small>kcal</small></strong></div>
      <div class="total-group"><span>累计已确认 · {{ calendar.all_total.days }} 天</span><strong>摄入 {{ number(calendar.all_total.intake) }} <small>kcal</small></strong><strong>消耗 {{ number(calendar.all_total.expenditure) }} <small>kcal</small></strong><strong>收支 {{ number(calendar.all_total.balance) }} <small>kcal</small></strong></div>
    </div>
    <div class="layout">
      <SCard class="calendar-card" :loading="loading">
        <div class="calendar-head"><div class="month-controls"><SButton class="icon-button" aria-label="上个月" @click="moveMonth(-1)"><UiIcon name="left" :size="17" /></SButton><strong>{{ month }}</strong><SButton class="icon-button" aria-label="下个月" @click="moveMonth(1)"><UiIcon name="right" :size="17" /></SButton></div><SButton size="small" @click="loadMonth('')">今天</SButton></div>
        <div class="calendar-grid weekdays"><span v-for="day in ['一','二','三','四','五','六','日']" :key="day">{{ day }}</span></div>
        <div class="calendar-grid days">
          <template v-for="(cell, index) in cells" :key="cell?.day || 'blank-' + index">
            <button v-if="cell" type="button" class="day-cell" :class="{ selected: selected === cell.day, today: calendar?.today === cell.day, confirmed: cell.data?.confirmed }" @click="loadDay(cell.day)">
              <span class="day-head"><span>{{ cell.number }}</span><span v-if="cell.data?.confirmed" class="confirmed-dot"></span></span>
              <span v-if="cell.data" class="day-values"><span>摄 {{ number(cell.data.intake) }} kcal</span><span>耗 {{ number(cell.data.expenditure) }} kcal</span></span>
            </button><span v-else class="day-cell blank"></span>
          </template>
        </div>
      </SCard>
      <SCard class="day-card">
        <div class="day-top"><div><strong>{{ selected }}</strong><span v-if="current" class="day-status" :class="{ done: current.confirmed }">{{ current.confirmed ? '已确认' : '待确认' }}</span></div><SButton size="small" :disabled="(!current?.count && !current?.confirmed) || busy" @click="confirmDay">{{ current?.confirmed ? '取消确认' : '确认当天' }}</SButton></div>
        <div v-if="current" class="day-body">
          <div class="day-summary"><div><span>摄入</span><strong>{{ number(current.intake) }}</strong></div><div><span>消耗</span><strong>{{ number(current.expenditure) }}</strong></div><div><span>收支</span><strong>{{ number(current.balance) }}</strong></div><small>kcal</small></div>
          <div v-for="kind in (['intake', 'expenditure'] as Kind[])" :key="kind" class="entry-group">
            <div class="group-head"><strong>{{ kind === 'intake' ? '摄入' : '消耗' }}</strong><SButton class="icon-button" :aria-label="kind === 'intake' ? '新增摄入' : '新增消耗'" @click="edit(undefined, kind)"><UiIcon name="plus" :size="17" /></SButton></div>
            <div v-if="!current.entries.some(e => e.kind === kind)" class="empty">暂无记录</div>
            <div v-for="entry in current.entries.filter(e => e.kind === kind)" :key="entry.id" class="entry-row">
              <div class="entry-info"><div><strong>{{ entry.label }}</strong><span v-if="entry.estimated" class="estimate-tag">估算</span></div><span v-if="entry.note" class="entry-detail">{{ entry.note }}</span><span v-if="entry.source" class="entry-source">{{ entry.source }}</span></div>
              <strong class="entry-kcal">{{ number(entry.kcal) }} <small>kcal</small></strong>
              <SButton class="icon-button" aria-label="编辑" @click="edit(entry)"><UiIcon name="edit" :size="15" /></SButton><SButton class="icon-button" aria-label="删除" @click="deleting = entry"><UiIcon name="trash" :size="15" /></SButton>
            </div>
          </div>
        </div>
      </SCard>
    </div>
  </div>
  <UiModal :open="entryOpen" :title="draft.id ? '编辑记录' : '新增记录'" @close="!busy && (entryOpen = false)">
    <form id="calorie-entry" class="form-stack" @submit.prevent="save">
      <div class="field"><label>日期</label><SInput v-model="draft.date" type="date" required /></div>
      <div class="field"><label>类型</label><SSelect :model-value="draft.kind" @update:model-value="changeKind"><option value="intake">摄入</option><option value="expenditure">消耗</option></SSelect></div>
      <div class="field"><label>标签</label><SSelect v-model="draft.label"><option v-for="name in special[draft.kind]" :key="name" :value="name">{{ name }}</option><option value="__custom__">自定义</option></SSelect></div>
      <div v-if="isCustom" class="field"><label>自定义标签</label><SInput v-model="draft.custom" maxlength="60" placeholder="例如：加餐、饮料" required /></div>
      <div class="field"><label>热量 · kcal</label><SInput v-model.number="draft.kcal" type="number" min="0" max="100000" step="0.01" placeholder="填写大卡" required /></div>
      <label class="checkbox-field"><SCheckbox v-model="draft.estimated" />估算值</label>
      <div class="field"><label>详情描述</label><STextarea v-model="draft.note" rows="3" maxlength="4000" placeholder="具体食物、份量或计算依据" /></div>
      <div class="field"><label>来源</label><SInput v-model="draft.source" maxlength="500" placeholder="例如：用户提供、营养表、设备" /></div>
      <span v-if="error" class="form-error">{{ error }}</span>
    </form>
    <template #footer><SButton :disabled="busy" @click="entryOpen = false">取消</SButton><SButton form="calorie-entry" type="submit" variant="primary" :loading="busy">保存</SButton></template>
  </UiModal>
  <UiModal :open="!!deleting" title="删除记录" @close="!busy && (deleting = null)"><strong>{{ deleting?.label }}</strong><template #footer><SButton :disabled="busy" @click="deleting = null">取消</SButton><SButton variant="danger" :loading="busy" @click="remove">删除</SButton></template></UiModal>
</template>

<style scoped>
.calorie-page { max-width: 1440px; margin: 0 auto; display: grid; gap: 18px; }
.totals-strip { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.total-group { display: flex; gap: 10px 20px; align-items: baseline; flex-wrap: wrap; padding: 16px 19px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; }
.total-group > span { flex-basis: 100%; color: var(--muted); font-size: 12px; }
.total-group strong { font-size: 13px; font-weight: 600; } small { color: var(--muted); font-size: 10px; font-weight: 400; }
.layout { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(340px, 1fr); gap: 18px; align-items: start; }
.calendar-card { padding: 20px; } .calendar-head, .month-controls, .day-top, .group-head, .entry-row, .day-head { display: flex; align-items: center; }
.calendar-head, .day-top, .group-head { justify-content: space-between; gap: 10px; } .month-controls { gap: 12px; } .month-controls strong { min-width: 75px; text-align: center; font-size: 16px; }
.calendar-grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 5px; } .weekdays { margin: 18px 0 8px; color: var(--muted); font-size: 12px; text-align: center; }
.day-cell { min-width: 0; min-height: 78px; padding: 9px; text-align: left; background: var(--surface-alt); color: var(--ink); border: 1px solid transparent; border-radius: 9px; cursor: pointer; transition: border-color .16s, background .16s, transform .16s; }
.day-cell:hover { border-color: var(--accent); } .day-cell.selected { border-color: var(--accent); box-shadow: var(--s-ring); } .day-cell.today .day-head > span:first-child { color: var(--accent); font-weight: 700; } .day-cell.blank { background: transparent; cursor: default; }
.day-head { justify-content: space-between; font-size: 13px; } .confirmed-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--positive); } .day-values { display: grid; gap: 3px; margin-top: 8px; color: var(--muted); font-size: 10px; overflow: hidden; white-space: nowrap; }
.day-top { padding: 20px; border-bottom: 1px solid var(--border); } .day-top > div { display: flex; align-items: center; flex-wrap: wrap; gap: 9px; } .day-status, .estimate-tag { color: var(--muted); background: var(--surface-alt); border-radius: 6px; padding: 3px 6px; font-size: 10px; } .day-status.done { color: var(--positive); }
.day-body { padding: 18px 20px 22px; } .day-summary { display: flex; align-items: end; gap: 18px; flex-wrap: wrap; padding: 14px; border-radius: 10px; background: var(--surface-alt); } .day-summary > div { display: grid; gap: 5px; } .day-summary span { color: var(--muted); font-size: 11px; } .day-summary strong { font-size: 17px; }
.entry-group { margin-top: 20px; } .group-head { margin-bottom: 5px; } .entry-row { gap: 7px; padding: 10px 0; border-bottom: 1px solid var(--border); } .entry-row:last-child { border: 0; } .entry-info { flex: 1; min-width: 0; } .entry-info > div { display: flex; align-items: center; gap: 7px; } .entry-detail, .entry-source { display: block; color: var(--muted); font-size: 11px; white-space: pre-wrap; overflow-wrap: anywhere; margin-top: 5px; } .entry-kcal { white-space: nowrap; font-size: 13px; } .empty { padding: 15px 0; color: var(--muted); font-size: 12px; }
@media (max-width: 1050px) { .layout { grid-template-columns: 1fr; } } @media (max-width: 650px) { .totals-strip { grid-template-columns: 1fr; } .calendar-card { padding: 12px; } .calendar-grid { gap: 3px; } .day-cell { min-height: 58px; padding: 5px; } .day-values { font-size: 9px; } .day-top, .day-body { padding: 16px; } }
</style>
