<script setup lang="ts">
import {
  ref,
  reactive,
  onMounted,
  onUnmounted,
  usePluginHost,
  formatDate,
  UiIcon,
  UiBadge,
  UiModal,
  UiEmpty,
} from "@sakubot/ui";
const host = usePluginHost();
const tab = ref("operations"),
  data = ref<any>(null),
  error = ref(""),
  busy = ref(false);
const selected = ref<any>(null),
  creating = ref(false),
  restartOpen = ref(false),
  confirmation = ref<any>(null);
const draft = reactive({ id: "", label: "", with_page: true });
const restart = reactive({
  reason: "",
  progress: "",
  resume: "",
  send_result_to_source: true,
});
const project = ref<any>(null),
  editor = ref<any>(null),
  editorDirty = ref(false),
  newPath = ref("");
const statuses: Record<string, string> = {
  queued: "等待执行",
  running: "执行中",
  done: "已完成",
  failed: "失败",
  interrupted: "已中断",
  cancelled: "已取消",
  restarting: "重启中",
};
let timer: ReturnType<typeof setInterval> | undefined;
async function load() {
  try {
    data.value = await host.api("status");
    if (selected.value?.action) {
      const fresh = data.value.operations.find(
        (r: any) => r.id === selected.value.id,
      );
      if (fresh) selected.value = { ...fresh, _tab: selected.value._tab };
    }
  } catch (e: any) {
    error.value = e.message;
  }
}
async function perform(fn: () => Promise<any>) {
  busy.value = true;
  error.value = "";
  try {
    const result = await fn();
    await load();
    return result;
  } catch (e: any) {
    error.value = e.message;
    return null;
  } finally {
    busy.value = false;
  }
}
async function submit(action: string, payload: any) {
  return perform(async () => {
    const receipt = await host.api<any>("operations", { action, payload });
    host.toast("已加入操作队列");
    return receipt;
  });
}
async function create() {
  const result = await perform(() =>
    host.api("projects", { action: "create", ...draft }),
  );
  if (result) {
    creating.value = false;
    project.value = result;
    draft.id = "";
    draft.label = "";
  }
}
async function inspect(id: string) {
  const result = await perform(() =>
    host.api("projects", { action: "inspect", id }),
  );
  if (result) {
    project.value = result;
    editor.value = null;
    editorDirty.value = false;
  }
}
async function readFile(path: string) {
  if (editorDirty.value) {
    error.value = "请先保存当前文件";
    return;
  }
  const result = await perform(() =>
    host.api("projects", { action: "read", id: project.value.id, path }),
  );
  if (result) {
    editor.value = result;
    editorDirty.value = false;
  }
}
async function writeFile() {
  const result = await perform(() =>
    host.api("projects", {
      action: "write",
      id: project.value.id,
      ...editor.value,
    }),
  );
  if (result) {
    editor.value = result;
    editorDirty.value = false;
    project.value = await host.api("projects", {
      action: "inspect",
      id: project.value.id,
    });
  }
}
function addFile() {
  if (editorDirty.value) {
    error.value = "请先保存当前文件";
    return;
  }
  if (!newPath.value.trim()) return;
  editor.value = {
    path: newPath.value.trim(),
    content: "",
    file_version: undefined,
  };
  newPath.value = "";
  editorDirty.value = true;
}
async function checkPublish() {
  if (editorDirty.value) {
    error.value = "请先保存当前文件";
    return;
  }
  const checked = await perform(() =>
    host.api("projects", { action: "check", id: project.value.id }),
  );
  if (checked)
    confirmation.value = {
      action: "project.publish",
      payload: { id: project.value.id, version: checked.version },
      title: "发布插件",
      checked,
    };
}
async function confirm() {
  const current = confirmation.value;
  if (await submit(current.action, current.payload)) confirmation.value = null;
}
async function versions(row: any) {
  const result = await perform(() =>
    host.api("projects", { action: "versions", id: row.name }),
  );
  if (result)
    selected.value = { type: "versions", id: row.name, items: result };
}
async function reboot() {
  if (await submit("system.restart", { ...restart })) restartOpen.value = false;
}
async function cancel(id: string) {
  await perform(() =>
    host.coreApi("system-operations/" + id, undefined, "DELETE"),
  );
}
onMounted(() => {
  load();
  timer = setInterval(load, 3000);
});
onUnmounted(() => clearInterval(timer));
</script>
<template>
  <STabs
    v-model="tab"
    :items="[
      { value: 'operations', label: '管理操作' },
      { value: 'plugins', label: '插件' },
      { value: 'projects', label: '开发项目' },
    ]"
  />
  <UiBadge v-if="error" status="error" :label="error" />
  <template v-if="data">
    <SCard v-if="tab === 'operations'" class="surface">
      <div class="metrics">
        <span>SakuBot {{ data.version }}</span
        ><span>Python {{ data.python }}</span
        ><span>{{ data.platform }}</span
        ><UiBadge
          :status="data.running ? 'running' : 'info'"
          :label="data.running ? '主智能体运行中' : '主智能体空闲'"
        />
      </div>
      <div class="table-scroll">
        <STable class="data-table"
          ><thead>
            <tr>
              <th>操作</th>
              <th>状态</th>
              <th>提交时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in data.operations" :key="row.id">
              <td>{{ row.action }}</td>
              <td>
                <UiBadge
                  :status="row.status"
                  :label="statuses[row.status] || row.status"
                />
              </td>
              <td>{{ formatDate(row.created) }}</td>
              <td>
                <SButton
                  variant="text"
                  @click="selected = { ...row, _tab: 'result' }"
                  >详情</SButton
                ><SButton
                  v-if="row.status === 'queued'"
                  variant="text"
                  @click="cancel(row.id)"
                  >取消</SButton
                >
              </td>
            </tr>
          </tbody></STable
        ><UiEmpty v-if="!data.operations.length" />
      </div>
    </SCard>
    <SCard v-else-if="tab === 'plugins'" class="surface"
      ><div class="table-scroll">
        <STable class="data-table"
          ><thead>
            <tr>
              <th>插件</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in data.plugins" :key="row.name">
              <td>
                {{ row.label }} <small>{{ row.name }}</small>
              </td>
              <td>
                <UiBadge
                  :status="row.loaded ? 'enabled' : 'disabled'"
                  :label="row.loaded ? '已加载' : '未加载'"
                />
              </td>
              <td class="row-actions">
                <SButton
                  v-if="!row.required"
                  variant="text"
                  @click="
                    confirmation = {
                      action: 'plugin.toggle',
                      payload: { id: row.name, enabled: !row.loaded },
                      title: row.loaded ? '停用插件' : '启用插件',
                    }
                  "
                  >{{ row.loaded ? "停用" : "启用" }}</SButton
                >
                <SButton
                  v-if="row.loaded && !row.required"
                  variant="text"
                  @click="
                    confirmation = {
                      action: 'plugin.reload',
                      payload: { id: row.name },
                      title: '重载插件',
                    }
                  "
                  >重载</SButton
                >
                <SButton
                  v-if="!row.builtin"
                  variant="text"
                  @click="
                    perform(() =>
                      host.api('projects', {
                        action: 'checkout',
                        id: row.name,
                      }),
                    )
                  "
                  >签出</SButton
                >
                <SButton
                  v-if="!row.builtin"
                  variant="text"
                  @click="versions(row)"
                  >版本</SButton
                >
              </td>
            </tr>
          </tbody></STable
        >
      </div></SCard
    >
    <SCard v-else class="surface"
      ><div class="table-scroll">
        <STable class="data-table"
          ><thead>
            <tr>
              <th>项目</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in data.projects" :key="row.id">
              <td>{{ row.id }}</td>
              <td>
                <SButton variant="text" @click="inspect(row.id)">编辑</SButton>
              </td>
            </tr>
          </tbody></STable
        ><UiEmpty v-if="!data.projects.length" /></div
    ></SCard>
  </template>
  <Teleport to="body"
    ><div class="floating-actions">
      <SButton class="icon-button" title="刷新" aria-label="刷新" @click="load"
        ><UiIcon name="refresh" /></SButton
      ><SButton
        v-if="tab === 'projects'"
        variant="primary"
        @click="creating = true"
        >新增项目</SButton
      ><SButton
        v-if="tab === 'operations'"
        :disabled="!data?.restart_supported"
        variant="danger"
        @click="restartOpen = true"
        >重启系统</SButton
      >
    </div></Teleport
  >
  <UiModal :open="creating" title="新增开发项目" @close="creating = false"
    ><SForm @submit.prevent="create"
      ><SFormItem label="插件 ID"
        ><SInput
          v-model="draft.id"
          placeholder="example_plugin"
          required
          pattern="[a-z][a-z0-9_]{0,40}" /></SFormItem
      ><SFormItem label="名称"
        ><SInput v-model="draft.label" placeholder="插件名称" /></SFormItem
      ><SCheckbox v-model="draft.with_page">管理页面</SCheckbox
      ><SButton type="submit" variant="primary" :loading="busy"
        >创建</SButton
      ></SForm
    ></UiModal
  >
  <UiModal
    :open="!!project"
    :title="project?.id || '开发项目'"
    wide
    @close="editorDirty ? (error = '请先保存当前文件') : (project = null)"
    ><template v-if="project"
      ><div class="project-actions">
        <SInput v-model="newPath" placeholder="新增文件相对路径" /><SButton
          @click="addFile"
          >新增文件</SButton
        ><SButton
          :disabled="busy || editorDirty"
          @click="submit('project.build', { id: project.id })"
          >构建页面</SButton
        ><SButton
          variant="primary"
          :disabled="busy || editorDirty"
          @click="checkPublish"
          >发布</SButton
        >
      </div>
      <div class="editor-layout">
        <nav class="file-list">
          <SButton
            v-for="file in project.files"
            :key="file"
            variant="text"
            @click="readFile(file)"
            >{{ file }}</SButton
          >
        </nav>
        <div v-if="editor" class="code-editor">
          <label>{{ editor.path }}</label
          ><STextarea
            v-model="editor.content"
            :rows="20"
            spellcheck="false"
            @update:model-value="editorDirty = true"
          /><SButton
            :variant="editorDirty ? 'primary' : 'default'"
            :loading="busy"
            @click="writeFile"
            >保存</SButton
          >
        </div>
      </div></template
    ></UiModal
  >
  <UiModal
    :open="!!selected"
    :title="selected?.type === 'versions' ? '历史版本' : '操作详情'"
    wide
    @close="selected = null"
    ><template v-if="selected?.type === 'versions'"
      ><div v-for="row in selected.items" :key="row.id" class="version-row">
        <code>{{ row.id }}</code
        ><SButton
          variant="text"
          @click="
            confirmation = {
              action: 'project.rollback',
              payload: { id: selected.id, revision: row.id },
              title: '回滚插件',
            }
          "
          >回滚</SButton
        >
      </div>
      <UiEmpty v-if="!selected.items.length" /></template
    ><template v-else-if="selected"
      ><dl>
        <dt>ID</dt>
        <dd>{{ selected.id }}</dd>
        <dt>状态</dt>
        <dd>{{ statuses[selected.status] }}</dd>
        <dt v-if="selected.error">错误</dt>
        <dd v-if="selected.error">{{ selected.error }}</dd>
      </dl>
      <STabs
        v-model="selected._tab"
        :items="[
          { value: 'result', label: '结果' },
          { value: 'logs', label: '日志' },
          { value: 'params', label: '参数' },
        ]"
      />
      <pre>{{
        selected._tab === "logs"
          ? selected.logs
          : JSON.stringify(
              selected._tab === "params" ? selected.payload : selected.result,
              null,
              2,
            )
      }}</pre>
    </template></UiModal
  >
  <UiModal
    :open="!!confirmation"
    :title="confirmation?.title || '确认操作'"
    @close="confirmation = null"
    ><template v-if="confirmation"
      ><code>{{ confirmation.payload.id }}</code
      ><template v-if="confirmation.checked"
        ><UiBadge
          v-if="confirmation.checked.page_build_required"
          status="error"
          label="页面未构建" />
        <div
          v-for="dep in confirmation.checked.dependencies"
          :key="dep.requirement"
        >
          {{ dep.requirement }}
          <UiBadge
            :status="dep.satisfied ? 'done' : 'error'"
            :label="dep.installed || '未安装'"
          /></div></template></template
    ><template #footer
      ><SButton @click="confirmation = null">取消</SButton
      ><SButton variant="primary" :loading="busy" @click="confirm"
        >确认</SButton
      ></template
    ></UiModal
  >
  <UiModal :open="restartOpen" title="重启系统" @close="restartOpen = false"
    ><SForm @submit.prevent="reboot"
      ><SFormItem label="原因"
        ><SInput
          v-model="restart.reason"
          placeholder="重启原因"
          required /></SFormItem
      ><SFormItem label="当前进度"
        ><STextarea
          v-model="restart.progress"
          placeholder="已完成与待处理事项" /></SFormItem
      ><SFormItem label="重启后目标"
        ><STextarea v-model="restart.resume" placeholder="可选" /></SFormItem
      ><SCheckbox v-model="restart.send_result_to_source"
        >报告主对话源</SCheckbox
      ><SButton type="submit" variant="danger" :loading="busy"
        >确认重启</SButton
      ></SForm
    ></UiModal
  >
</template>
<style scoped>
.metrics,
.project-actions,
.version-row {
  display: flex;
  gap: 14px;
  align-items: center;
  flex-wrap: wrap;
}
.metrics {
  padding: 16px;
  border-bottom: 1px solid var(--border);
}
.project-actions {
  margin-bottom: 18px;
}
.project-actions :deep(.s-input) {
  flex: 1;
  min-width: 150px;
}
.editor-layout {
  display: grid;
  grid-template-columns: 190px minmax(0, 1fr);
  gap: 18px;
}
.file-list {
  display: flex;
  flex-direction: column;
  max-height: 55vh;
  overflow: auto;
}
.file-list button {
  text-align: left;
  justify-content: flex-start;
  overflow-wrap: anywhere;
}
.code-editor {
  display: grid;
  gap: 12px;
  min-width: 0;
}
.code-editor :deep(textarea) {
  font-family: monospace;
  min-height: 40vh;
}
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 50vh;
  overflow: auto;
  padding: 16px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 10px;
}
small {
  color: var(--muted);
}
dd {
  margin: 4px 0 14px;
  overflow-wrap: anywhere;
}
.version-row {
  justify-content: space-between;
  border-bottom: 1px solid var(--border);
  padding: 12px 0;
}
@media (max-width: 640px) {
  .editor-layout {
    grid-template-columns: 1fr;
  }
  .file-list {
    max-height: 130px;
  }
}
</style>
