<script setup lang="ts">
import {
  ref,
  reactive,
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
const configuring = ref(false);
const uploading = ref(false);
const providers = ref<{ id: string; name: string }[]>([]);
const settings = reactive({ provider_id: '', embedding_model: '', auto_memory: true, recall_limit: 5, min_score: 0.3, ready: false, indexed: 0, total: 0 });
const fileInput = ref<HTMLInputElement | null>(null);
const deleting = ref<Memory | null>(null);
const draft = reactive({
  key: "",
  text: "",
  source: "dashboard",
});
async function load() {
  loading.value = true;
  try {
    rows.value = await host.api<Memory[]>("memories");
    Object.assign(settings, await host.api("settings"));
    providers.value = await host.api("providers");
  } catch {
    host.toast("加载失败", true);
  } finally {
    loading.value = false;
  }
}
async function search() {
  if (!query.value.trim()) return load();
  loading.value = true;
  try { rows.value = await host.api<Memory[]>("search", { query: query.value, limit: 20 }); }
  catch (error) { host.toast(error instanceof Error ? error.message : '检索失败', true); }
  finally { loading.value = false; }
}
async function saveSettings() {
  saving.value = true;
  try {
    const { provider_id, embedding_model, auto_memory, recall_limit, min_score } = settings;
    Object.assign(settings, await host.api('settings', { provider_id, embedding_model, auto_memory, recall_limit, min_score }));
    configuring.value = false;
    host.toast('已保存');
  } catch (error) { host.toast(error instanceof Error ? error.message : '保存失败', true); }
  finally { saving.value = false; }
}
async function upload(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  uploading.value = true;
  try {
    await host.upload('document?name=' + encodeURIComponent(file.name), file);
    await load();
    host.toast('已导入');
  } catch (error) { host.toast(error instanceof Error ? error.message : '导入失败', true); }
  finally { uploading.value = false; input.value = ''; }
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
    <SButton class="button" @click="configuring = true">设置</SButton>
    <SButton class="button" :disabled="!settings.ready || uploading" @click="fileInput?.click()">上传文档</SButton>
    <input ref="fileInput" type="file" accept=".txt,.md,.pdf,.docx" class="file-input" @change="upload" />
    <SButton class="button primary" :disabled="!settings.ready" @click="edit()">
      <UiIcon name="plus" :size="16" />新增记忆
    </SButton>
  </div>
  <SCard class="surface">
    <div class="table-toolbar">
      <form class="search-field" @submit.prevent="search">
        <UiIcon name="search" :size="17" /><SInput
          v-model="query"
          placeholder="语义搜索记忆"
          aria-label="搜索记忆"
        />
      </form>
      <SButton class="button" :disabled="!settings.ready || loading" @click="search">搜索</SButton>
      <UiBadge :status="settings.ready ? 'online' : 'offline'" :label="settings.ready ? `已索引 ${settings.indexed}/${settings.total}` : '待配置'" />
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
    <div v-if="rows.length" class="table-scroll">
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
          <tr v-for="row in rows" :key="row.key">
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
  <UiModal :open="configuring" title="记忆设置" @close="configuring = false">
    <form id="memory-settings" class="form-stack" @submit.prevent="saveSettings">
      <div class="field"><label>供应商</label><SSelect v-model="settings.provider_id"><option value="">请选择</option><option v-for="provider in providers" :key="provider.id" :value="provider.id">{{ provider.name }}</option></SSelect></div>
      <div class="field"><label>向量模型</label><SInput v-model="settings.embedding_model" placeholder="向量模型 ID" /></div>
      <div class="field"><label>自动记忆</label><SSwitch v-model="settings.auto_memory" /></div>
      <div class="field"><label>召回条数</label><SInput v-model.number="settings.recall_limit" type="number" min="1" max="20" required /></div>
      <div class="field"><label>最低相似度</label><SInput v-model.number="settings.min_score" type="number" min="-1" max="1" step="0.01" required /></div>
    </form>
    <template #footer><SButton class="button" @click="configuring = false">取消</SButton><SButton form="memory-settings" class="button primary" :disabled="saving">保存</SButton></template>
  </UiModal>
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
<style scoped>
.file-input { display: none; }
</style>
