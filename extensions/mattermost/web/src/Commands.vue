<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, usePluginHost, UiModal, formatDate } from '@sakubot/ui'

const host = usePluginHost()
const rows = ref<any[]>([]), scripts = ref<any[]>([]), teams = ref<any[]>([])
const loading = ref(false), busy = ref(false), editing = ref(false), error = ref('')
const settings = reactive({enabled: false, base_url: ''})
const savedSettings = ref(''), configuredUrl = ref(''), serverUrl = ref('')
const dirty = computed(() => !!savedSettings.value && savedSettings.value !== JSON.stringify(settings))
const callbackHost = computed(() => {
  try { return new URL(settings.base_url).hostname } catch { return 'sakubot' }
})
const callbackUrl = computed(() => settings.base_url.trim() ? settings.base_url.trim().replace(/\/+$/, '') + '/hooks/mattermost/slash' : '')
const canCreate = computed(() => !!configuredUrl.value && !dirty.value)
const confirm = ref<{action: string; row: any} | null>(null)
const params = ref('{}')
const form = reactive({ id: '', team_id: '', trigger: '', display_name: '', description: '', hint: '',
  script_id: '', user_id: '', channel_id: '', enabled: true })
const statusNames: Record<string, string> = {
  creating: '创建待确认', updating: '更新待确认', repairing: '待修复',
  deleting: '删除待确认', rotating_token: '令牌待确认', account_changed: '连接已变更',
}
function message(e: unknown) { return e instanceof Error ? e.message : '操作失败' }
function apply(data: any, force = false) {
  rows.value = data.commands
  scripts.value = data.scripts
  serverUrl.value = data.server_url
  configuredUrl.value = data.settings.base_url
  if (force || !savedSettings.value || !dirty.value) {
    Object.assign(settings, data.settings)
    savedSettings.value = JSON.stringify(settings)
  }
}
async function load() {
  if (loading.value) return
  loading.value = true
  try {
    const data = await host.api<any>('commands')
    apply(data)
  } catch (e) { host.toast(message(e), true) }
  finally { loading.value = false }
}
async function saveSettings() {
  if (busy.value || !dirty.value) return
  busy.value = true
  error.value = ''
  try {
    apply(await host.api<any>('command-settings', {...settings}), true)
    host.toast('已保存')
  } catch (e) { error.value = message(e); host.toast(error.value, true) }
  finally { busy.value = false }
}
async function open(row?: any) {
  Object.assign(form, { id: '', team_id: '', trigger: '', display_name: '', description: '', hint: '',
    script_id: '', user_id: '', channel_id: '', enabled: true })
  if (row) for (const key of Object.keys(form)) (form as any)[key] = row[key] ?? (form as any)[key]
  params.value = JSON.stringify(row?.params || {}, null, 2)
  error.value = ''
  editing.value = true
  try { teams.value = await host.api<any[]>('command-teams') }
  catch (e) { error.value = message(e) }
}
async function act(action: string, row: any, extra: Record<string, unknown> = {}) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    const data = await host.api<any>('commands', {action, id: row.id || undefined, ...extra})
    await load()
    if (data.complete === false) {
      editing.value = false
      throw new Error(data.error || '操作尚未完成，请修复登记')
    }
    host.toast(action === 'delete' ? '已删除' : '已保存')
    return true
  } catch (e) { error.value = message(e); host.toast(error.value, true); return false }
  finally { busy.value = false }
}
async function save() {
  let values: unknown
  try {
    values = JSON.parse(params.value)
    if (!values || typeof values !== 'object' || Array.isArray(values)) throw new Error('脚本参数须为 JSON 对象')
  } catch (e) { error.value = message(e); return }
  if (await act('save', form, {...form, id: form.id || undefined, params: values})) editing.value = false
}
async function accepted() {
  if (!confirm.value) return
  if (await act(confirm.value.action, confirm.value.row, {confirm: true})) confirm.value = null
}
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => { load(); timer = setInterval(load, 5000) })
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="command-overview">
    <SCard title="接收设置">
      <SForm id="mm-command-settings" class="command-settings" :disabled="busy" @submit="saveSettings">
        <SFormItem label="启用斜杠命令"><SSwitch v-model="settings.enabled" /></SFormItem>
        <SFormItem label="SakuBot 基础地址"><SInput v-model="settings.base_url" type="url" :required="settings.enabled"
          placeholder="http://sakubot:6190/ 或 https://sakubot.example.com/" aria-describedby="mm-slash-base-help" /></SFormItem>
        <p id="mm-slash-base-help" class="command-help">MatterMost 如何访问到本插件部署的 SakuBot？请输入访问 SakuBot 的基础地址，例如 <code>http://sakubot:6190/</code>（容器内）或 <code>https://sakubot.example.com/</code>（外部访问）。</p>
        <span v-if="error" class="command-error" role="alert">{{error}}</span>
      </SForm>
    </SCard>
    <SCard title="请求方向">
      <dl class="command-directions">
        <dt>SakuBot → Mattermost</dt><dd><span>服务器地址</span><code>{{serverUrl || '未配置'}}</code></dd>
        <dt>Mattermost → SakuBot</dt><dd><span>命令请求地址 · 自动生成</span><code>{{callbackUrl || '请填写上方 SakuBot 基础地址'}}</code></dd>
      </dl>
    </SCard>
  </div>
  <SCard title="Mattermost 配置">
    <template #actions><a href="https://docs.mattermost.com/developers/integrate/slash-commands/custom" target="_blank" rel="noopener noreferrer">官方文档 ↗</a></template>
    <ol class="command-steps">
      <li><strong>开启自定义斜杠命令</strong><p>在 Mattermost「系统控制台 → 集成 → 集成管理」中开启「自定义斜杠命令」。</p></li>
      <li><strong>配置账号与团队</strong><p>将机器人加入目标团队，确保当前访问令牌所属账号具有该团队的 <code>manage_slash_commands</code> 权限。若服务器限制仅管理员管理集成，需由管理员调整相应角色或集成设置。</p></li>
      <li><strong>允许访问 SakuBot</strong><p>若请求地址使用容器名、局域网或本机地址，在「系统控制台 → 环境 → 开发者 → 允许不受信任的内部连接」中加入 <code>{{callbackHost}}</code>。对应配置为 <code>ServiceSettings.AllowedUntrustedInternalConnections</code>；已有条目用空格分隔，保留原配置。</p></li>
      <li><strong>创建并使用命令</strong><p>在下方新增命令，或让智能体创建命令并绑定已保存的脚本。无需去 Mattermost 手动创建，也无需复制令牌；插件会自动登记名称、描述、参数提示和请求地址。在所属团队输入 <code>/</code> 即可查看自动补全。</p></li>
    </ol>
    <p class="command-footnote">仅处理本插件管理的命令。收到命令后执行绑定脚本；需要模型判断时由脚本主动唤醒智能体。修改基础地址后，对已有命令点击“同步 / 修复”。</p>
  </SCard>
  <SCard title="已声明命令" :loading="loading && !rows.length">
    <template #actions><STag :label="`${rows.length} 条`" /></template>
    <div class="command-table">
      <STable :rows="rows" :columns="[{key:'trigger',label:'命令'},{key:'hint',label:'补全参数'},{key:'team_id',label:'团队'},
        {key:'script_id',label:'动作'},{key:'status',label:'状态'},{key:'updated',label:'更新于'},{key:'actions',label:'操作'}]">
        <template #cell-trigger="{row}"><strong>/{{ row.trigger }}</strong><span v-if="row.display_name" class="command-name">{{row.display_name}}</span><span class="command-desc">{{ row.description }}</span></template>
        <template #cell-hint="{row}"><code>{{row.hint || '—'}}</code></template>
        <template #cell-team_id="{row}"><span class="mono">{{ row.team_id }}</span></template>
        <template #cell-script_id="{row}">{{ row.binding?.target_kind === 'wake' ? '唤醒主智能体' : scripts.find(s => s.id === row.script_id)?.name || row.script_id || '未绑定' }}</template>
        <template #cell-status="{row}">
          <STag :status="row.callback_outdated ? 'unavailable' : row.active ? 'enabled' : row.status === 'ready' ? 'disabled' : 'unavailable'"
            :label="statusNames[row.status] || (row.callback_outdated ? '请求地址待同步' : row.active ? '已启用' : row.enabled ? '不可用' : '已停用')" :title="row.error || row.binding?.reason" />
          <span v-if="row.error" class="command-error">{{ row.error }}</span>
        </template>
        <template #cell-updated="{row}">{{ formatDate(row.updated) }}</template>
        <template #cell-actions="{row}">
          <div class="row-actions">
            <SButton class="icon-button" title="编辑" aria-label="编辑" icon="edit" :disabled="busy || dirty || row.status !== 'ready'" @click="open(row)" />
            <SButton class="icon-button" :title="row.enabled ? '停用' : '启用'" :aria-label="row.enabled ? '停用' : '启用'"
              :icon="row.enabled ? 'pause' : 'power'" :disabled="busy || row.status !== 'ready'" @click="act(row.enabled ? 'disable' : 'enable', row)" />
            <SButton class="icon-button" title="同步 / 修复" aria-label="同步 / 修复" icon="refresh" :disabled="busy || dirty" @click="act('repair', row)" />
            <SButton class="icon-button" title="重置令牌" aria-label="重置令牌" icon="key" :disabled="busy || row.status !== 'ready'" @click="confirm = {action:'rotate_token',row}" />
            <SButton class="icon-button" title="删除" aria-label="删除" icon="delete" :disabled="busy" @click="confirm = {action:'delete',row}" />
          </div>
        </template>
      </STable>
    </div>
  </SCard>
  <Teleport to="body"><div class="floating-actions">
    <SButton icon="refresh" :loading="loading" @click="load">刷新</SButton>
    <SButton icon="plus" :disabled="busy || !canCreate" :title="canCreate ? '新增命令' : '先保存 SakuBot 基础地址'" @click="open()">新增命令</SButton>
    <SButton type="submit" form="mm-command-settings" icon="check" :variant="dirty ? 'primary' : 'default'" :disabled="!dirty" :loading="busy">保存配置</SButton>
  </div></Teleport>
  <UiModal :open="editing" :title="form.id ? '编辑指令' : '新增指令'" @close="!busy && (editing = false)">
    <SForm id="mm-command" :disabled="busy" @submit="save">
      <SFormItem label="团队">
        <SSelect v-model="form.team_id" :disabled="!!form.id" required>
          <option value="" disabled>选择团队</option>
          <option v-if="form.team_id && !teams.some(t => t.id === form.team_id)" :value="form.team_id">{{form.team_id}}</option>
          <option v-for="team in teams" :key="team.id" :value="team.id">{{team.display_name || team.name}}</option>
        </SSelect>
      </SFormItem>
      <SFormItem label="指令名称"><SInput v-model="form.trigger" placeholder="例如 calories，不带 /" pattern="[A-Za-z0-9_-]{1,64}" maxlength="64" required /></SFormItem>
      <SFormItem label="显示名称"><SInput v-model="form.display_name" placeholder="例如 今日热量" maxlength="64" /></SFormItem>
      <SFormItem label="自动补全描述"><SInput v-model="form.description" placeholder="例如 查询当日热量统计" maxlength="256" /></SFormItem>
      <SFormItem label="参数提示"><SInput v-model="form.hint" placeholder="例如 [日期]" maxlength="128" /></SFormItem>
      <SFormItem label="脚本"><SSelect v-model="form.script_id"><option value="">保留事件动作</option>
        <option v-for="script in scripts" :key="script.id" :value="script.id">{{script.name}}</option>
      </SSelect></SFormItem>
      <SFormItem v-if="form.script_id" label="脚本固定参数"><STextarea v-model="params" rows="3" placeholder='例如 {"days": 1}' /></SFormItem>
      <SFormItem label="限定用户 ID"><SInput v-model="form.user_id" placeholder="留空不限用户" pattern="[a-z0-9]{26}" /></SFormItem>
      <SFormItem label="限定频道 ID"><SInput v-model="form.channel_id" placeholder="留空不限频道" pattern="[a-z0-9]{26}" /></SFormItem>
      <SFormItem label="启用"><SSwitch v-model="form.enabled" /></SFormItem>
      <span v-if="error" class="command-error" role="alert">{{error}}</span>
    </SForm>
    <template #footer><SButton :disabled="busy" @click="editing = false">取消</SButton><SButton type="submit" form="mm-command" variant="primary" :loading="busy">保存</SButton></template>
  </UiModal>
  <UiModal :open="!!confirm" :title="confirm?.action === 'delete' ? '删除指令' : '重置指令令牌'" @close="!busy && (confirm = null)">
    <strong>/{{confirm?.row.trigger}}</strong>
    <span v-if="error" class="command-error" role="alert">{{error}}</span>
    <template #footer><SButton :disabled="busy" @click="confirm = null">取消</SButton><SButton variant="danger" :loading="busy" @click="accepted">确认{{confirm?.action === 'delete' ? '删除' : '重置'}}</SButton></template>
  </UiModal>
</template>

<style scoped>
.command-overview { display: grid; gap: 18px; }
.command-settings { padding: 22px; max-width: 820px; margin: 0 auto; }
.command-help, .command-footnote { color: var(--muted); font-size: 12px; line-height: 1.8; }
.command-help { margin: 0; }
.command-footnote { margin: 0; padding: 0 22px 22px; }
.command-directions { display: grid; grid-template-columns: minmax(160px, auto) minmax(0, 1fr); gap: 16px 24px; padding: 22px; margin: 0; }
.command-directions dt { font-weight: 600; font-size: 13px; color: var(--ink); }
.command-directions dd { margin: 0; display: grid; gap: 6px; overflow-wrap: anywhere; }
.command-directions dd span { color: var(--muted); font-size: 12px; }
.command-steps { padding: 0 22px; margin: 0; list-style: none; counter-reset: command-step; }
.command-steps li { position: relative; padding: 18px 0 18px 38px; border-bottom: 1px solid var(--border); counter-increment: command-step; }
.command-steps li::before { content: counter(command-step); position: absolute; left: 0; top: 18px; width: 24px; height: 24px; display: grid; place-items: center; border-radius: 8px; color: var(--accent); background: var(--surface-alt); font-size: 12px; font-weight: 600; }
.command-steps li:last-child { border-bottom: 0; }
.command-steps strong { font-size: 13px; color: var(--ink); }
.command-steps p { margin: 6px 0 0; color: var(--muted); line-height: 1.8; font-size: 12px; overflow-wrap: anywhere; }
.command-overview code, .command-steps code { color: var(--ink); font-size: 12px; overflow-wrap: anywhere; }
.command-table { overflow-x: auto; }
.command-name { display: block; margin-top: 5px; color: var(--ink); font-size: 12px; }
.command-desc { display: block; margin-top: 5px; max-width: 240px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.command-error { display: block; color: var(--negative); font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; max-width: 320px; }
.row-actions { display: flex; align-items: center; gap: 3px; }
@media (max-width: 650px) { .command-settings { padding: 18px; } .command-directions { grid-template-columns: 1fr; gap: 8px; padding: 18px; } .command-directions dt:not(:first-child) { margin-top: 12px; } .command-steps { padding: 0 18px; } .command-footnote { padding: 0 18px 18px; } }
</style>
