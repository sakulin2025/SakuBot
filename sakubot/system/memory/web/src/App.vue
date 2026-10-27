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
import type { Memory } from "@sakubot/ui";
const host = usePluginHost();
const rows = ref<Memory[]>([]);
const query = ref("");
const loading = ref(false);
const saving = ref(false);
const editing = ref(false);
const deleting = ref<Memory | null>(null);
const draft = reactive({
  key: "",
  text: "",
  source: "dashboard",
});
const filtered = computed(() =>
  rows.value.filter((row) => (row.key + row.text).includes(query.value)),
);
async function load() {
  loading.value = true;
  try {
    rows.value = await host.api<Memory[]>("memories");
  } catch {
    host.toast("加载失败", true);
  } finally {
    loading.value = false;
  }
}
function edit(row?: Memory) {
  Object.assign(draft, row || { key: "", text: "", source: "dashboard" });
  editing.value = true;
}
async function save() {
  saving.value = true;
  try {
    await host.api("memories", {
      key: draft.key,
      text: draft.text,
      source: draft.source,
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
    await host.api("memories", { key: deleting.value.key, delete: true });
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
      <span class="page-kicker">长期记忆</span>
      <h1>记忆</h1>
      <span class="heading-count">{{ rows.length }}</span>
    </div>
    <SButton class="button primary" @click="edit()">
      <UiIcon name="plus" :size="16" />新增记忆
    </SButton>
  </div>
  <SCard class="surface">
    <div class="table-toolbar">
      <div class="search-field">
        <UiIcon name="search" :size="17" /><SInput
          v-model="query"
          placeholder="搜索记忆"
          aria-label="搜索记忆"
        />
      </div>
      <span class="toolbar-spacer"></span
      ><SButton
        class="icon-button"
        :disabled="loading"
        aria-label="刷新"
        @click="load"
      >
        <UiIcon name="refresh" :class="{ spinning: loading }" :size="17" />
      </SButton>
    </div>
    <div v-if="filtered.length" class="table-scroll">
      <STable class="data-table">
        <thead>
          <tr>
            <th>名称</th>
            <th>内容</th>
            <th>更新时间</th>
            <th class="align-right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in filtered" :key="row.key">
            <td>
              <strong>{{ row.key }}</strong>
            </td>
            <td class="content-cell">{{ row.text.slice(0, 120) }}</td>
            <td class="nowrap">{{ formatDate(row.updated) }}</td>
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
  <UiModal :open="editing" title="记忆" @close="editing = false"
    ><form id="memory-form" class="form-stack" @submit.prevent="save">
      <div class="field">
        <label for="key">名称</label
        ><SInput id="key" v-model="draft.key" maxlength="200" required />
      </div>
      <div class="field">
        <label for="text">内容</label
        ><STextarea
          id="text"
          v-model="draft.text"
          rows="8"
          required
        ></STextarea>
      </div>
      <div class="form-row">
        <div class="field">
          <label for="source">来源</label
          ><SInput id="source" v-model="draft.source" />
        </div>
      </div>
    </form>
    <template #footer
      ><SButton class="button" @click="editing = false">取消</SButton
      ><SButton form="memory-form" class="button primary" :disabled="saving">
        保存
      </SButton></template
    ></UiModal
  >
  <UiModal :open="!!deleting" title="删除记忆" @close="deleting = null"
    ><div class="delete-target">
      <UiIcon name="trash" /><strong>{{ deleting?.key }}</strong>
    </div>
    <template #footer
      ><SButton class="button" @click="deleting = null">取消</SButton
      ><SButton class="button danger" :disabled="saving" @click="remove">
        删除
      </SButton></template
    ></UiModal
  >
</template>
