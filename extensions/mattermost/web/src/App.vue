<script setup lang="ts">
import Commands from './Commands.vue';
import {
  reactive,
  ref,
  computed,
  watch,
  onMounted,
  onUnmounted,
  usePluginHost,
  UiBadge,
  formatDate,
} from "@sakubot/ui";

const host = usePluginHost();
const values = reactive({
  base_url: "",
  token: "",
  channel_ids: [] as string[],
  image_model_id: "",
  reply_split_enabled: true,
  reply_split_regex: "。|",
  reply_remove_regex: "。",
  reply_trim: true,
  reply_merge_newlines: true,
  reply_interval_min: 3,
  reply_interval_max: 5,
});
const tab = ref("connection");
const imageModels = ref<{ id: string; name: string }[]>([]);
type Settings = typeof values & {
  token_configured: boolean;
};
const status = ref({
  online: false,
  error: "",
  retry_at: 0,
  bot_id: "",
  channel_ids: [] as string[],
});
const logs = ref<
  {
    id: number;
    at: number;
    level: string;
    event: string;
    data: Record<string, unknown>;
  }[]
>([]);
const configured = ref(false);
function applySettings(data: Settings) {
  const { token_configured, ...fields } = data;
  Object.assign(values, fields);
  values.token = "";
  configured.value = token_configured;
}
const busy = ref(false);
const loading = ref(true);
const saveError = ref("");
const reconnecting = ref(false);
const saved = ref("");
const dirty = computed(
  () =>
    !!saved.value &&
    JSON.stringify(values) !== saved.value,
);
const labels: Record<string, string> = {
  'mattermost.command.save': '指令已保存',
  'mattermost.command.repair': '指令已修复',
  'mattermost.command.delete': '指令已删除',
  'mattermost.command.rotate_token': '指令令牌已重置',
  'mattermost.slash.received': '收到 Slash 指令',
  "mattermost.config.saved": "配置已保存",
  "mattermost.reconnect.requested": "请求重新连接",
  "mattermost.connected": "连接成功",
  "mattermost.disconnected": "连接断开",
  "mattermost.catch_up": "消息补收",
  "mattermost.message.received": "收到消息",
  "mattermost.message.sent": "消息已发送",
  "mattermost.message.failed": "消息发送失败",
};
const fieldLabels: Record<string, string> = {
  bot_id: "机器人 ID",
  channel_ids: "生效频道",
  channel_id: "会话 ID",
  post_id: "消息 ID",
  files: "附件",
  posts: "消息数",
  type: "类型",
  error: "错误",
  retry_seconds: "重连间隔 · 秒",
};
let timer: ReturnType<typeof setInterval> | undefined;
let refreshing = false;
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    const [next, entries] = await Promise.all([
      host.api<typeof status.value>("status"),
      host.api<typeof logs.value>("logs"),
    ]);
    const changed =
      next.online !== status.value.online || next.error !== status.value.error;
    status.value = next;
    logs.value = entries;
    if (changed) host.refresh();
  } catch {
    /* 保留最近一次状态 */
  } finally {
    refreshing = false;
  }
}
async function save() {
  if (busy.value || !dirty.value) return;
  busy.value = true;
  saveError.value = "";
  try {
    const result = await host.api<Settings>("config", {
      ...values,
    });
    applySettings(result);
    saved.value = JSON.stringify(values);
    await refresh();
    host.refresh();
    host.toast("已保存");
  } catch (error) {
    saveError.value = error instanceof Error ? error.message : "保存失败";
    host.toast(saveError.value, true);
  } finally {
    busy.value = false;
  }
}
async function reconnect() {
  reconnecting.value = true;
  try {
    await host.api("reconnect", {});
    await refresh();
    host.toast("正在连接");
  } catch (error) {
    host.toast(error instanceof Error ? error.message : "连接失败", true);
  } finally {
    reconnecting.value = false;
  }
}
onMounted(async () => {
  try {
    const data = await host.api<Settings>("config");
    applySettings(data);
    saved.value = JSON.stringify(values);
    imageModels.value =
      await host.api<typeof imageModels.value>("image-models");
    await refresh();
  } catch {
    saveError.value = "加载失败，请刷新页面";
    host.toast(saveError.value, true);
  } finally {
    loading.value = false;
  }
  timer = setInterval(refresh, 2500);
});
onUnmounted(() => clearInterval(timer));
watch(tab, async (next, previous) => {
  if (next !== 'connection' || previous !== 'commands' || dirty.value || busy.value) return;
  try {
    applySettings(await host.api<Settings>('config'));
    saved.value = JSON.stringify(values);
  } catch (error) { host.toast(error instanceof Error ? error.message : '加载失败', true); }
});
</script>

<template>
  <STabs
    v-model="tab"
    :items="[
      { value: 'connection', label: '连接' },
      { value: 'status', label: '连接状态' },
      { value: 'commands', label: '斜杠命令' },
      { value: 'logs', label: '连接日志' },
    ]"
  />
  <div class="mattermost-page" :class="{'wide-page': tab === 'commands'}">
    <SForm
      v-show="tab === 'connection'"
      id="mattermost-config"
      :disabled="busy"
      @submit="save"
    >
      <SCard title="连接" :loading="loading">
        <template #actions
          ><UiBadge :status="status.online ? 'online' : 'offline'"
        /></template>
        <div class="form-body">
          <SFormItem label="服务器地址" for="mm-base"
            ><SInput
              id="mm-base"
              v-model="values.base_url"
              placeholder="https://chat.example.com"
              required
          /></SFormItem>
          <SFormItem label="机器人访问令牌" for="mm-token">
            <template #label
              >机器人访问令牌
              <span v-if="configured" class="field-state"
                >已设置</span
              ></template
            >
            <SInput
              id="mm-token"
              v-model="values.token"
              type="password"
              autocomplete="new-password"
              :required="!configured"
              placeholder="填写 Bot Token"
            />
          </SFormItem>
          <SFormItem label="生效频道列表">
            <div class="channel-list">
              <div v-for="(_, index) in values.channel_ids" :key="index" class="channel-row">
                <SInput v-model="values.channel_ids[index]" :aria-label="`频道 ID ${index + 1}`" placeholder="26 位频道 ID" pattern="[a-z0-9]{26}" required />
                <SButton type="button" icon="trash" title="移除频道" @click="values.channel_ids.splice(index, 1)" />
              </div>
              <SButton type="button" icon="plus" :disabled="values.channel_ids.length >= 100" @click="values.channel_ids.push('')">新增频道</SButton>
            </div>
          </SFormItem>
          <span v-if="saveError" class="save-error" role="alert">{{
            saveError
          }}</span>
          <span
            v-else-if="status.error && configured"
            class="connection-error"
            >{{ status.error }}</span
          >
          <div class="connection-actions">
            <SButton
              type="button"
              :disabled="!configured"
              :loading="reconnecting"
              @click="reconnect"
              >重新连接</SButton
            >
          </div>
        </div>
      </SCard>
      <SCard title="回应分段" class="settings-card">
        <div class="form-body">
          <SFormItem label="自动分段"
            ><SSwitch v-model="values.reply_split_enabled" label="自动分段"
          /></SFormItem>
          <SFormItem label="分割正则" for="mm-split"
            ><SInput
              id="mm-split"
              v-model="values.reply_split_regex"
              :disabled="!values.reply_split_enabled"
          /></SFormItem>
          <SFormItem label="移除正则" for="mm-remove"
            ><SInput
              id="mm-remove"
              v-model="values.reply_remove_regex"
              :disabled="!values.reply_split_enabled"
          /></SFormItem>
          <SFormItem label="分段后裁剪"
            ><SSwitch
              v-model="values.reply_trim"
              label="分段后裁剪"
              :disabled="!values.reply_split_enabled"
          /></SFormItem>
          <SFormItem label="合并连续换行"
            ><SSwitch
              v-model="values.reply_merge_newlines"
              label="合并连续换行"
              :disabled="!values.reply_split_enabled"
          /></SFormItem>
          <SFormItem label="最小间隔 · 秒" for="mm-min"
            ><SInput
              id="mm-min"
              v-model.number="values.reply_interval_min"
              type="number"
              min="0"
              step="0.1"
              :disabled="!values.reply_split_enabled"
              required
          /></SFormItem>
          <SFormItem label="最大间隔 · 秒" for="mm-max"
            ><SInput
              id="mm-max"
              v-model.number="values.reply_interval_max"
              type="number"
              :min="values.reply_interval_min"
              step="0.1"
              :disabled="!values.reply_split_enabled"
              required
          /></SFormItem>
        </div>
      </SCard>
      <SCard title="消息处理" class="settings-card">
        <div class="form-body">
          <SFormItem label="图片解读模型" for="mm-image-model">
            <SSelect id="mm-image-model" v-model="values.image_model_id">
              <option value="">关闭</option>
              <option
                v-if="
                  values.image_model_id &&
                  !imageModels.some(
                    (model) => model.id === values.image_model_id,
                  )
                "
                :value="values.image_model_id"
              >
                当前模型不可用
              </option>
              <option
                v-for="model in imageModels"
                :key="model.id"
                :value="model.id"
              >
                {{ model.name }}
              </option>
            </SSelect>
          </SFormItem>
        </div>
      </SCard>
    </SForm>
    <SCard v-if="tab === 'status'" title="连接状态">
      <div class="status-grid">
        <span>机器人 ID</span
        ><span class="mono">{{ status.bot_id || "—" }}</span>
        <span>生效频道</span>
        <div class="channel-list"><span v-for="channel in status.channel_ids" :key="channel" class="mono">{{ channel }}</span><span v-if="!status.channel_ids.length">—</span></div>
        <span>下次重连</span
        ><span>{{ status.retry_at ? formatDate(status.retry_at) : "—" }}</span>
      </div>
    </SCard>
    <Commands v-if="tab === 'commands'" />
    <SCard v-if="tab === 'logs'" title="连接日志">
      <div v-if="logs.length" class="logs">
        <div v-for="entry in logs" :key="entry.id" class="log-item">
          <div class="log-head">
            <strong>{{ labels[entry.event] || entry.event }}</strong
            ><span class="field-state">{{ formatDate(entry.at) }}</span>
          </div>
          <div v-if="Object.keys(entry.data).length" class="log-data">
            <span v-for="(value, key) in entry.data" :key="key"
              >{{ fieldLabels[String(key)] || key }}：{{ value }}</span
            >
          </div>
        </div>
      </div>
      <div v-else class="empty-logs">暂无日志</div>
    </SCard>
  </div>
  <Teleport v-if="tab === 'connection'" to="body"
    ><div class="floating-actions">
      <SButton
        type="submit"
        form="mattermost-config"
        :variant="dirty ? 'primary' : 'default'"
        :disabled="!dirty"
        :loading="busy"
        icon="check"
        >保存配置</SButton
      >
    </div></Teleport
  >
</template>

<style scoped>
.mattermost-page {
  width: 100%;
  max-width: 820px;
  margin: 0 auto;
  display: grid;
  gap: 18px;
  padding-bottom: 90px;
}
.channel-list { display: grid; gap: 10px; width: 100%; }
.channel-row { display: flex; align-items: center; gap: 8px; }
.channel-row > :first-child { flex: 1; min-width: 0; }
.settings-card {
  margin-top: 18px;
}
.mattermost-page.wide-page { max-width: none; }
.connection-actions {
  display: flex;
  justify-content: flex-end;
}
.status-grid {
  display: grid;
  grid-template-columns: 130px minmax(0, 1fr);
  gap: 14px;
  padding: 22px 25px;
  overflow-wrap: anywhere;
}
.status-grid > span:nth-child(odd) {
  color: var(--muted);
}
.logs {
  display: grid;
  gap: 0;
  max-height: 420px;
  overflow: auto;
  padding: 4px 25px;
}
.empty-logs {
  color: var(--muted);
  padding: 22px 25px;
  font-size: 13px;
}
.save-error,
.connection-error {
  color: var(--negative);
  font-size: 13px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.log-item {
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}
.log-item:last-child {
  border-bottom: 0;
}
.log-head {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 8px;
}
.log-data {
  margin-top: 7px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  color: var(--muted);
  font-size: 12px;
  overflow-wrap: anywhere;
}
@media (max-width: 700px) {
  .mattermost-page {
    gap: 14px;
  }
  .status-grid {
    grid-template-columns: minmax(90px, 110px) minmax(0, 1fr);
    padding: 18px;
  }
  .logs {
    padding: 4px 18px;
  }
  .empty-logs {
    padding: 18px;
  }
}
</style>
