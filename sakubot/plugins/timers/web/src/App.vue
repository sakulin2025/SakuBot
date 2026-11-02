<script setup lang="ts">
import {
  ref,
  reactive,
  computed,
  onMounted,
  UiIcon,
  UiBadge,
  UiModal,
  UiEmpty,
  usePluginHost,
  formatDate,
} from "@sakubot/ui";
import type { Schedule } from "@sakubot/ui";
const host = usePluginHost();
const rows = ref<Schedule[]>([]);
const scripts = ref<any[]>([]);
const query = ref("");
const editing = ref(false);
const deleting = ref<Schedule | null>(null);
const loading = ref(false);
const saving = ref(false);
const draft = reactive({
  id: "",
  name: "",
  content: "",
  mode: "wake",
  script_id: "",
  script_params: "{}",
  timing: "interval",
  at: "",
  interval: 300,
  daily_time: "09:00",
  timezone: "Asia/Shanghai",
  send_result_to_source: true,
  enabled: true,
  include_context: false,
});
const filtered = computed(() =>
  rows.value.filter((row) =>
    (row.data.name + row.data.content).includes(query.value),
  ),
);
async function load() {
  loading.value = true;
  try {
    const [tasks, programs] = await Promise.all([
      host.api<Schedule[]>("schedules"),
      host.api<any[]>("script-options"),
    ]);
    rows.value = tasks;
    scripts.value = programs;
  } catch {
    host.toast("加载失败", true);
  } finally {
    loading.value = false;
  }
}
function edit(row?: Schedule) {
  const at = row?.data.at ? new Date(row.data.at) : null;
  Object.assign(draft, {
    id: row?.id || "",
    name: row?.data.name || "",
    content: row?.data.content || "",
    mode: row?.data.mode || "wake",
    script_id: row?.data.script_id || "",
    script_params: JSON.stringify(row?.data.script_params || {}, null, 2),
    timing: at ? "once" : row?.data.daily_time ? "daily" : "interval",
    at: at
      ? new Date(at.getTime() - at.getTimezoneOffset() * 60000)
          .toISOString()
          .slice(0, 16)
      : "",
    interval: row?.data.interval_seconds || 300,
    daily_time: row?.data.daily_time || "09:00",
    timezone: row?.data.timezone || "Asia/Shanghai",
    send_result_to_source: row?.data.send_result_to_source ?? true,
    enabled: row?.data.enabled ?? true,
    include_context: row?.data.include_context || false,
  });
  editing.value = true;
}
async function save() {
  saving.value = true;
  try {
    await host.api("schedules", {
      action: "save",
      id: draft.id,
      name: draft.name,
      content: draft.content,
      mode: draft.mode,
      script_id: draft.script_id,
      script_params:
        draft.mode === "script" ? JSON.parse(draft.script_params) : {},
      at: draft.timing === "once" ? new Date(draft.at).toISOString() : "",
      interval_seconds:
        draft.timing === "interval" ? Number(draft.interval) : 0,
      daily_time: draft.timing === "daily" ? draft.daily_time : "",
      timezone: draft.timezone,
      send_result_to_source: draft.send_result_to_source,
      enabled: draft.enabled,
      include_context: draft.include_context,
    });
    editing.value = false;
    await load();
    host.toast("已保存");
  } catch {
    host.toast("保存失败", true);
  } finally {
    saving.value = false;
  }
}
async function remove() {
  if (!deleting.value) return;
  saving.value = true;
  try {
    await host.api("schedules", { action: "delete", id: deleting.value.id });
    deleting.value = null;
    await load();
    host.toast("已删除");
  } catch {
    host.toast("删除失败", true);
  } finally {
    saving.value = false;
  }
}
onMounted(load);
</script>
<template>
  <Teleport to="body"
    ><div class="floating-actions">
      <SButton class="button primary" @click="edit()">
        <UiIcon name="plus" :size="16" />新增任务
      </SButton>
    </div></Teleport
  >
  <SCard class="surface">
    <div class="table-toolbar">
      <div class="search-field">
        <UiIcon name="search" :size="17" /><SInput
          v-model="query"
          placeholder="搜索任务"
          aria-label="搜索任务"
        />
      </div>
      <span class="toolbar-spacer"></span
      ><SButton
        class="icon-button"
        aria-label="刷新"
        :disabled="loading"
        @click="load"
      >
        <UiIcon name="refresh" :class="{ spinning: loading }" :size="17" />
      </SButton>
    </div>
    <div v-if="filtered.length" class="table-scroll">
      <STable class="data-table">
        <thead>
          <tr>
            <th>任务</th>
            <th>事件类型</th>
            <th>下次触发</th>
            <th>状态</th>
            <th class="align-right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in filtered" :key="row.id">
            <td>
              <strong>{{ row.data.name }}</strong
              ><span v-if="row.data.legacy_target" class="cell-sub"
                >旧目标：{{ row.data.legacy_target }} · 待重新设置</span
              >
            </td>
            <td><UiBadge :status="row.data.mode" /></td>
            <td class="nowrap">
              {{ row.data.enabled ? formatDate(row.next_at) : "—" }}
            </td>
            <td>
              <UiBadge :status="row.data.enabled ? 'enabled' : 'disabled'" />
            </td>
            <td>
              <div class="row-actions">
                <SButton
                  class="icon-button"
                  aria-label="编辑"
                  @click="edit(row)"
                >
                  <UiIcon name="edit" :size="16" /></SButton
                ><SButton
                  class="icon-button danger-text"
                  aria-label="删除"
                  @click="deleting = row"
                >
                  <UiIcon name="trash" :size="16" />
                </SButton>
              </div>
            </td>
          </tr>
        </tbody>
      </STable>
    </div>
    <UiEmpty v-else />
  </SCard>
  <UiModal :open="editing" title="定时任务" @close="editing = false"
    ><form id="schedule-form" class="form-stack" @submit.prevent="save">
      <div class="field">
        <label for="name">名称</label
        ><SInput id="name" v-model="draft.name" required />
      </div>
      <div v-if="draft.mode !== 'script'" class="field">
        <label for="content">内容</label
        ><STextarea
          id="content"
          v-model="draft.content"
          rows="5"
          required
        ></STextarea>
      </div>
      <div class="form-row">
        <div class="field">
          <label for="mode">事件类型</label
          ><SSelect id="mode" v-model="draft.mode">
            <option value="wake">唤醒 Agent</option>
            <option value="context">上下文</option>
            <option value="notify">直接通知</option>
            <option value="script">执行脚本</option>
          </SSelect>
        </div>
        <div class="field">
          <label for="timing">触发方式</label
          ><SSelect id="timing" v-model="draft.timing">
            <option value="interval">固定间隔</option>
            <option value="daily">每天</option>
            <option value="once">指定时间</option>
          </SSelect>
        </div>
      </div>
      <template v-if="draft.mode === 'script'"
        ><div class="field">
          <label>脚本</label
          ><SSelect v-model="draft.script_id" required
            ><option value="">选择脚本</option>
            <option v-for="item in scripts" :key="item.id" :value="item.id">
              {{ item.name }}
            </option></SSelect
          >
        </div>
        <div class="field">
          <label>脚本参数 · JSON</label
          ><STextarea v-model="draft.script_params" rows="4" /></div
      ></template>
      <div v-if="draft.timing === 'interval'" class="field">
        <label for="interval">间隔 · 秒</label
        ><SInput
          id="interval"
          v-model.number="draft.interval"
          type="number"
          min="30"
          max="31536000"
          required
        />
      </div>
      <div v-else-if="draft.timing === 'once'" class="field">
        <label for="at">时间</label>
        <SInput id="at" v-model="draft.at" type="datetime-local" required />
      </div>
      <div v-else class="form-row">
        <div class="field">
          <label for="daily-time">每天</label
          ><SInput
            id="daily-time"
            v-model="draft.daily_time"
            type="time"
            required
          />
        </div>
        <div class="field">
          <label for="timezone">时区</label
          ><SInput id="timezone" v-model="draft.timezone" required />
        </div>
      </div>
      <label
        v-if="draft.mode === 'wake' || draft.mode === 'notify'"
        class="checkbox-field"
        ><SCheckbox
          v-model="draft.send_result_to_source"
        />发送到主对话源</label
      >
      <div class="form-row">
        <label class="checkbox-field"
          ><SCheckbox v-model="draft.enabled" />启用</label
        ><label v-if="draft.mode === 'notify'" class="checkbox-field"
          ><SCheckbox v-model="draft.include_context" />加入上下文</label
        >
      </div>
    </form>
    <template #footer
      ><SButton class="button" @click="editing = false">取消</SButton
      ><SButton form="schedule-form" class="button primary" :disabled="saving">
        保存
      </SButton></template
    ></UiModal
  >
  <UiModal :open="!!deleting" title="删除任务" @close="deleting = null"
    ><div class="delete-target">
      <UiIcon name="trash" /><strong>{{ deleting?.data.name }}</strong>
    </div>
    <template #footer
      ><SButton class="button" @click="deleting = null">取消</SButton
      ><SButton class="button danger" :disabled="saving" @click="remove">
        删除
      </SButton></template
    ></UiModal
  >
</template>
