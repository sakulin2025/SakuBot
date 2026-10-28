<script setup lang="ts">
import {
  reactive,
  ref,
  onMounted,
  onUnmounted,
  usePluginHost,
  UiBadge,
} from "@sakubot/ui";
const host = usePluginHost();
const values = reactive({
  owner_id: "", backend: "napcat", napcat_ws: "", napcat_token: "", snowluma_ws: "", snowluma_token: "",
  reply_split_enabled: true, reply_split_regex: "。|", reply_remove_regex: "。",
  reply_trim: true, reply_merge_newlines: true,
  reply_interval_min: 3, reply_interval_max: 5,
  image_model_id: "", speech_recognition: "unimplemented",
});
const imageModels = ref<{ id: string; name: string }[]>([]);
const tokenConfigured = reactive({ napcat: false, snowluma: false });
const status = ref({
  online: false,
  self_id: "",
  nickname: "",
  error: "",
  retry_at: 0,
});
const busy = ref(false);
let timer: ReturnType<typeof setInterval> | undefined;
async function loadStatus() {
  try {
    status.value = await host.api<typeof status.value>("status");
  } catch {
    /* Keep last known status. */
  }
}
async function save() {
  busy.value = true;
  try {
    const data = await host.api<{ napcat_token_configured: boolean; snowluma_token_configured: boolean }>(
      "config",
      values,
    );
    values.napcat_token = "";
    values.snowluma_token = "";
    tokenConfigured.napcat = data.napcat_token_configured;
    tokenConfigured.snowluma = data.snowluma_token_configured;
    await loadStatus();
    host.refresh();
    host.toast("已保存");
  } catch (error) {
    host.toast(error instanceof Error ? error.message : "保存失败", true);
  } finally {
    busy.value = false;
  }
}
onMounted(async () => {
  try {
    const data = await host.api<{
      owner_id: string;
      backend: string;
      napcat_ws: string;
      napcat_token_configured: boolean;
      snowluma_ws: string;
      snowluma_token_configured: boolean;
      reply_split_enabled: boolean;
      reply_split_regex: string;
      reply_remove_regex: string;
      reply_trim: boolean;
      reply_merge_newlines: boolean;
      reply_interval_min: number;
      reply_interval_max: number;
      image_model_id: string;
      speech_recognition: string;
    }>("config");
    values.owner_id = data.owner_id;
    values.backend = data.backend;
    values.napcat_ws = data.napcat_ws;
    values.snowluma_ws = data.snowluma_ws;
    values.reply_split_enabled = data.reply_split_enabled;
    values.reply_split_regex = data.reply_split_regex;
    values.reply_remove_regex = data.reply_remove_regex;
    values.reply_trim = data.reply_trim;
    values.reply_merge_newlines = data.reply_merge_newlines;
    values.reply_interval_min = data.reply_interval_min;
    values.reply_interval_max = data.reply_interval_max;
    values.image_model_id = data.image_model_id;
    values.speech_recognition = data.speech_recognition;
    imageModels.value = await host.api<{ id: string; name: string }[]>("image-models");
    tokenConfigured.napcat = data.napcat_token_configured;
    tokenConfigured.snowluma = data.snowluma_token_configured;
    await loadStatus();
  } catch {
    host.toast("加载失败", true);
  }
  timer = setInterval(loadStatus, 3000);
});
onUnmounted(() => clearInterval(timer));
</script>
<template>
  <SPageHeader title="QQ"
    ><UiBadge :status="status.online ? 'online' : 'offline'"
  /></SPageHeader>
  <SForm @submit="save">
    <div class="settings-grid">
      <SCard title="连接"
        ><div class="form-body">
          <SFormItem label="协议端" for="qq-backend">
            <SSelect id="qq-backend" v-model="values.backend"><option value="napcat">NapCat</option><option value="snowluma">SnowLuma</option></SSelect>
          </SFormItem>
          <span class="field-state">适配目标：{{ values.backend === 'napcat' ? 'NapCat v4.18.41' : 'SnowLuma v2.2.1' }}</span>
          <template v-if="values.backend === 'napcat'">
          <SFormItem label="WebSocket 地址" for="napcat-ws"
            ><SInput id="napcat-ws" v-model="values.napcat_ws" required
          /></SFormItem>
          <SFormItem label="Access Token" for="napcat-token"
            ><template #label
              >Access Token
              <span v-if="tokenConfigured.napcat" class="field-state"
                >已设置</span
              ></template
            ><SInput
              id="napcat-token"
              v-model="values.napcat_token"
              type="password"
              autocomplete="new-password"
          /></SFormItem>
          </template>
          <template v-else>
            <SFormItem label="WebSocket 地址" for="snowluma-ws"><SInput id="snowluma-ws" v-model="values.snowluma_ws" required /></SFormItem>
            <SFormItem label="Access Token" for="snowluma-token"><template #label>Access Token <span v-if="tokenConfigured.snowluma" class="field-state">已设置</span></template><SInput id="snowluma-token" v-model="values.snowluma_token" type="password" autocomplete="new-password" /></SFormItem>
          </template>
          <div v-if="status.self_id" class="connection-identity">
            <strong>{{ status.nickname }}</strong
            ><span class="mono">{{ status.self_id }}</span>
          </div>
          <span v-if="status.error" class="form-error">{{ status.error }}</span>
        </div></SCard
      >
      <SCard title="主对话源"
        ><div class="form-body">
          <SFormItem label="主人 QQ" for="owner-id"
            ><SInput
              id="owner-id"
              v-model="values.owner_id"
              inputmode="numeric"
              pattern="[0-9]+"
              required
          /></SFormItem></div
      ></SCard>
      <SCard title="回应分段">
        <div class="form-body">
          <SFormItem label="自动分段">
            <SSwitch v-model="values.reply_split_enabled" label="自动分段" />
          </SFormItem>
          <SFormItem label="分割正则" for="reply-split-regex">
            <SInput id="reply-split-regex" v-model="values.reply_split_regex" :disabled="!values.reply_split_enabled" />
          </SFormItem>
          <SFormItem label="移除正则" for="reply-remove-regex">
            <SInput id="reply-remove-regex" v-model="values.reply_remove_regex" :disabled="!values.reply_split_enabled" />
          </SFormItem>
          <SFormItem label="分段后裁剪">
            <SSwitch v-model="values.reply_trim" label="分段后裁剪" :disabled="!values.reply_split_enabled" />
          </SFormItem>
          <SFormItem label="合并连续换行">
            <SSwitch v-model="values.reply_merge_newlines" label="合并连续换行" :disabled="!values.reply_split_enabled" />
          </SFormItem>
          <SFormItem label="最小间隔 · 秒" for="reply-interval-min">
            <SInput id="reply-interval-min" v-model.number="values.reply_interval_min" type="number" min="0" step="0.1" :disabled="!values.reply_split_enabled" required />
          </SFormItem>
          <SFormItem label="最大间隔 · 秒" for="reply-interval-max">
            <SInput id="reply-interval-max" v-model.number="values.reply_interval_max" type="number" :min="values.reply_interval_min" step="0.1" :disabled="!values.reply_split_enabled" required />
          </SFormItem>
        </div>
      </SCard>
      <SCard title="消息处理">
        <div class="form-body">
          <SFormItem label="图片解读模型" for="image-model">
            <SSelect id="image-model" v-model="values.image_model_id">
              <option value="">关闭</option>
              <option v-if="values.image_model_id && !imageModels.some(model => model.id === values.image_model_id)" :value="values.image_model_id">当前模型不可用</option>
              <option v-for="model in imageModels" :key="model.id" :value="model.id">{{ model.name }}</option>
            </SSelect>
          </SFormItem>
          <SFormItem label="语音识别" for="speech">
            <SSelect id="speech" disabled><option>未实现</option></SSelect>
          </SFormItem>
        </div>
      </SCard>
    </div>
    <div class="settings-save">
      <SButton type="submit" variant="primary" :loading="busy" icon="check"
        >保存配置</SButton
      >
    </div>
  </SForm>
</template>
