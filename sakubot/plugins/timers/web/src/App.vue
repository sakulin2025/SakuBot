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
  timing: "interval",
  at: "",
  interval: 300,
  target: "main",
  target_id: "",
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
    rows.value = await host.api<Schedule[]>("schedules");
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
    timing: at ? "once" : "interval",
    at: at
      ? new Date(at.getTime() - at.getTimezoneOffset() * 60000)
          .toISOString()
          .slice(0, 16)
      : "",
    interval: row?.data.interval_seconds || 300,
    target: row?.data.target || "main",
    target_id: row?.data.target_id || "",
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
      at: draft.timing === "once" ? new Date(draft.at).toISOString() : "",
      interval_seconds:
        draft.timing === "interval" ? Number(draft.interval) : 0,
      target: draft.target,
      target_id: draft.target === "main" ? "" : draft.target_id,
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
  <div class="page-heading">
    <div class="heading-title">
      <span class="page-kicker">自动化</span>
      <h1>定时任务</h1>
      <span class="heading-count">{{ rows.length }}</span>
    </div>
    <SButton class="button primary" @click="edit()">
      <UiIcon name="plus" :size="16" />新增任务
    </SButton>
  </div>
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
              ><span class="cell-sub mono"
                >{{ row.data.target
                }}{{ row.data.target_id ? ":" + row.data.target_id : "" }}</span
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
      <div class="field">
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
          </SSelect>
        </div>
        <div class="field">
          <label for="timing">触发方式</label
          ><SSelect id="timing" v-model="draft.timing">
            <option value="interval">固定间隔</option>
            <option value="once">指定时间</option>
          </SSelect>
        </div>
      </div>
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
      <div v-else class="field">
        <label for="at">时间</label
        ><SInput id="at" v-model="draft.at" type="datetime-local" required />
      </div>
      <div class="field">
        <label for="target">目标会话</label
        ><SSelect id="target" v-model="draft.target">
          <option value="main">主对话 · main</option>
          <option value="private">私聊 · private</option>
          <option value="group">群聊 · group</option>
        </SSelect>
      </div>
      <div v-if="draft.target !== 'main'" class="field">
        <label for="target-id">{{
          draft.target === "private" ? "QQ 号" : "群号"
        }}</label>
        <SInput
          id="target-id"
          v-model="draft.target_id"
          inputmode="numeric"
          pattern="[1-9][0-9]{0,19}"
          required
        />
      </div>
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
