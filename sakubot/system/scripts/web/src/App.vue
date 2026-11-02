<script setup lang="ts">
import {
  ref,
  reactive,
  computed,
  onMounted,
  onUnmounted,
  usePluginHost,
  UiIcon,
  UiModal,
  formatDate,
} from "@sakubot/ui";
import Parameters from "./Parameters.vue";
const host = usePluginHost();
const tab = ref("programs"),
  loading = ref(false),
  busy = ref(false),
  query = ref(""),
  error = ref("");
const catalog = ref<any>({ scripts: [], bindings: [], sources: [], runs: [] });
const editing = ref(false),
  bindingOpen = ref(false),
  runOpen = ref(false),
  detailOpen = ref(false);
const removing = ref<{ kind: string; id: string; name: string } | null>(null);
const sourceParamsText = ref("{}");
const detail = ref<any>(null),
  versions = ref<any[]>([]),
  options = ref<any>({});
const emptySchema = {
  type: "object",
  properties: {},
  additionalProperties: false,
};
const script = reactive({
  id: "",
  name: "",
  description: "",
  code: 'async def main(ctx):\n    ctx.log("执行完成")\n    return {"ok": True}\n',
  parameters: JSON.stringify(emptySchema, null, 2),
  expected_version: "",
  timeout: 120,
  enabled: true,
  concurrency: "merge",
  on_failure: "none",
  failure_threshold: 1,
  cooldown_seconds: 3600,
  send_result_to_source: true,
});
const binding = reactive({
  id: "",
  name: "",
  script_id: "",
  source: "",
  source_params: {} as any,
  params: {} as any,
  enabled: true,
  on_failure: "none",
  failure_threshold: 1,
  cooldown_seconds: 3600,
  send_result_to_source: true,
});
const manual = reactive({ id: "", params: {} as any });
function matches(pattern: string, value: string) {
  const escaped = pattern
    .split("*")
    .map((part) => part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join(".*");
  return new RegExp("^" + escaped + "$").test(value);
}
const source = computed(
  () =>
    catalog.value.sources.find((s: any) => s.id === binding.source) ||
    catalog.value.sources.find(
      (s: any) => s.id.includes("*") && matches(s.id, binding.source),
    ),
);
const bindingScript = computed(() =>
  catalog.value.scripts.find((s: any) => s.id === binding.script_id),
);
const manualScript = computed(() =>
  catalog.value.scripts.find((s: any) => s.id === manual.id),
);
const rows = computed(() =>
  (
    (
      ({
        programs: catalog.value.scripts,
        bindings: catalog.value.bindings,
        runs: catalog.value.runs,
      }) as Record<string, any[]>
    )[tab.value] || []
  ).filter((x: any) =>
    JSON.stringify(x).toLowerCase().includes(query.value.toLowerCase()),
  ),
);
const labels: Record<string, string> = {
  queued: "排队中",
  running: "运行中",
  done: "完成",
  failed: "失败",
  interrupted: "中断",
  cancelled: "已取消",
};
function failure(e: unknown) {
  return e instanceof Error ? e.message : "操作失败";
}
async function api(operation: string, args: any) {
  return host.api<any>("manage", { operation, ...args });
}
async function load() {
  loading.value = true;
  try {
    catalog.value = await host.api("catalog");
  } catch (e) {
    host.toast(failure(e), true);
  } finally {
    loading.value = false;
  }
}
function defaults(schema: any) {
  return Object.fromEntries(
    Object.entries(schema?.properties || {})
      .filter(([, v]: any) => v.default !== undefined)
      .map(([k, v]: any) => [k, v.default]),
  );
}
async function edit(row?: any) {
  error.value = "";
  versions.value = [];
  try {
    const value = row
      ? await api("script", { action: "get", id: row.id })
      : null;
    Object.assign(script, {
      id: value?.id || "",
      name: value?.name || "",
      description: value?.description || "",
      code:
        value?.code ||
        'async def main(ctx):\n    ctx.log("执行完成")\n    return {"ok": True}\n',
      parameters: JSON.stringify(value?.parameters || emptySchema, null, 2),
      expected_version: value?.version || "",
      timeout: value?.timeout || 120,
      enabled: value?.enabled ?? true,
      concurrency: value?.concurrency || "merge",
      on_failure: value?.on_failure || "none",
      failure_threshold: value?.failure_threshold || 1,
      cooldown_seconds: value?.cooldown_seconds || 3600,
      send_result_to_source: value?.send_result_to_source ?? true,
    });
    if (value)
      versions.value = await api("script", {
        action: "revisions",
        id: value.id,
      });
    editing.value = true;
  } catch (e) {
    host.toast(failure(e), true);
  }
}
async function version(value: string) {
  if (!value) return;
  try {
    const result = await api("script", {
      action: "get",
      id: script.id,
      version: value,
    });
    script.code = result.code;
  } catch (e) {
    host.toast(failure(e), true);
  }
}
async function saveScript() {
  busy.value = true;
  error.value = "";
  try {
    await api("script", {
      action: "save",
      ...script,
      parameters: JSON.parse(script.parameters),
    });
    editing.value = false;
    await load();
    host.toast("已保存");
  } catch (e) {
    error.value = failure(e);
  } finally {
    busy.value = false;
  }
}
async function toggle(row: any, value: boolean) {
  try {
    const current = await api("script", { action: "get", id: row.id });
    await api("script", {
      action: "save",
      ...current,
      enabled: value,
      expected_version: current.version,
    });
    await load();
  } catch (e) {
    host.toast(failure(e), true);
  }
}
async function editBinding(row?: any) {
  error.value = "";
  Object.assign(binding, {
    id: row?.id || "",
    name: row?.name || "",
    script_id: row?.script_id || catalog.value.scripts[0]?.id || "",
    source: row?.source || catalog.value.sources[0]?.id || "",
    source_params: row ? { ...row.source_params } : {},
    params: row ? { ...row.params } : {},
    enabled: row?.enabled ?? true,
    on_failure: row?.on_failure || "none",
    failure_threshold: row?.failure_threshold || 1,
    cooldown_seconds: row?.cooldown_seconds || 3600,
    send_result_to_source: row?.send_result_to_source ?? true,
  });
  if (!row) {
    binding.source_params = defaults(source.value?.parameters);
    binding.params = defaults(bindingScript.value?.parameters);
  }
  sourceParamsText.value = JSON.stringify(binding.source_params, null, 2);
  bindingOpen.value = true;
  await loadOptions();
}
async function loadOptions() {
  options.value = {};
  if (!binding.source) return;
  const key = binding.source;
  try {
    const result = await api("binding", { action: "options", source: key });
    if (binding.source === key) options.value = result;
  } catch (e) {
    error.value = failure(e);
  }
}
function changeSource(value: any) {
  binding.source = String(value);
  binding.source_params = defaults(source.value?.parameters);
  void loadOptions();
}
function changeScript(value: any) {
  binding.script_id = String(value);
  binding.params = defaults(bindingScript.value?.parameters);
}
async function saveBinding() {
  busy.value = true;
  error.value = "";
  try {
    if (!source.value)
      binding.source_params = JSON.parse(sourceParamsText.value);
    await api("binding", { action: "save", ...binding });
    bindingOpen.value = false;
    await load();
    host.toast("已保存");
  } catch (e) {
    error.value = failure(e);
  } finally {
    busy.value = false;
  }
}
function run(row: any) {
  manual.id = row.id;
  manual.params = defaults(row.parameters);
  error.value = "";
  runOpen.value = true;
}
async function execute() {
  busy.value = true;
  error.value = "";
  try {
    await api("run", manual);
    runOpen.value = false;
    tab.value = "runs";
    await load();
    host.toast("已排队");
  } catch (e) {
    error.value = failure(e);
  } finally {
    busy.value = false;
  }
}
async function inspect(row: any) {
  try {
    detail.value = await api("execution", { action: "get", id: row.id });
    detailOpen.value = true;
  } catch (e) {
    host.toast(failure(e), true);
  }
}
async function stop(row: any) {
  busy.value = true;
  try {
    await api("execution", { action: "stop", id: row.id });
    await load();
    if (detail.value?.id === row.id) await inspect(row);
  } catch (e) {
    host.toast(failure(e), true);
  } finally {
    busy.value = false;
  }
}
async function remove() {
  if (!removing.value) return;
  busy.value = true;
  try {
    const row = removing.value;
    await api(row.kind === "script" ? "script" : "binding", {
      action: "delete",
      id: row.id,
      confirm: true,
    });
    removing.value = null;
    await load();
    host.toast("已删除");
  } catch (e) {
    host.toast(failure(e), true);
  } finally {
    busy.value = false;
  }
}
let timer: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
  void load();
  timer = setInterval(() => {
    if (tab.value === "runs" && !busy.value) {
      void load();
      if (detailOpen.value && detail.value?.status === "running")
        void inspect(detail.value);
    }
  }, 4000);
});
onUnmounted(() => clearInterval(timer));
</script>
<template>
  <div class="scripts-page">
    <STabs
      v-model="tab"
      :items="[
        { value: 'programs', label: '程序' },
        { value: 'bindings', label: '触发绑定' },
        { value: 'runs', label: '执行记录' },
      ]"
    />
    <SCard
      ><div class="table-toolbar">
        <SInput v-model="query" placeholder="搜索脚本、绑定或执行" /><SButton
          class="icon-button"
          aria-label="刷新"
          :disabled="loading"
          @click="load"
          ><UiIcon name="refresh" :size="17"
        /></SButton>
      </div>
      <div class="table-scroll">
        <STable
          ><thead>
            <tr v-if="tab === 'programs'">
              <th>脚本</th>
              <th>版本</th>
              <th>并发策略</th>
              <th>启用</th>
              <th>操作</th>
            </tr>
            <tr v-else-if="tab === 'bindings'">
              <th>绑定</th>
              <th>脚本</th>
              <th>触发源</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
            <tr v-else>
              <th>脚本</th>
              <th>时间</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.id">
              <template v-if="tab === 'programs'"
                ><td>{{ row.name }}</td>
                <td class="mono">{{ row.version.slice(0, 8) }}</td>
                <td>
                  {{
                    ({ queue: "排队", merge: "合并", skip: "跳过" } as any)[
                      row.concurrency
                    ]
                  }}
                </td>
                <td>
                  <SSwitch
                    :model-value="row.enabled"
                    @update:model-value="toggle(row, $event)"
                  />
                </td>
                <td>
                  <div class="row-actions">
                    <SButton
                      class="icon-button"
                      aria-label="运行"
                      @click="run(row)"
                      ><UiIcon name="play" :size="16" /></SButton
                    ><SButton
                      class="icon-button"
                      aria-label="编辑"
                      @click="edit(row)"
                      ><UiIcon name="edit" :size="16" /></SButton
                    ><SButton
                      class="icon-button"
                      aria-label="删除"
                      @click="
                        removing = {
                          kind: 'script',
                          id: row.id,
                          name: row.name,
                        }
                      "
                      ><UiIcon name="trash" :size="16"
                    /></SButton>
                  </div></td
              ></template>
              <template v-else-if="tab === 'bindings'"
                ><td>{{ row.name }}</td>
                <td>
                  {{
                    catalog.scripts.find((s: any) => s.id === row.script_id)
                      ?.name || row.script_id
                  }}
                </td>
                <td>
                  {{
                    catalog.sources.find((s: any) => s.id === row.source)
                      ?.name || row.source
                  }}
                </td>
                <td>
                  <STag
                    :label="row.enabled && !row.declared ? '未声明' : undefined"
                    :status="
                      !row.enabled
                        ? 'disabled'
                        : row.available
                          ? 'enabled'
                          : 'unavailable'
                    "
                  />
                </td>
                <td>
                  <div class="row-actions">
                    <SButton
                      class="icon-button"
                      aria-label="编辑"
                      @click="editBinding(row)"
                      ><UiIcon name="edit" :size="16" /></SButton
                    ><SButton
                      class="icon-button"
                      aria-label="删除"
                      @click="
                        removing = {
                          kind: 'binding',
                          id: row.id,
                          name: row.name,
                        }
                      "
                      ><UiIcon name="trash" :size="16"
                    /></SButton>
                  </div></td
              ></template>
              <template v-else
                ><td>
                  {{
                    catalog.scripts.find((s: any) => s.id === row.script_id)
                      ?.name || row.script_id
                  }}
                </td>
                <td>{{ formatDate(row.started || row.queued) }}</td>
                <td>
                  <STag
                    :label="labels[row.status] || row.status"
                    :status="row.status"
                  />
                </td>
                <td>
                  <div class="row-actions">
                    <SButton
                      class="icon-button"
                      aria-label="详情"
                      @click="inspect(row)"
                      ><UiIcon name="eye" :size="16" /></SButton
                    ><SButton
                      v-if="['queued', 'running'].includes(row.status)"
                      class="icon-button"
                      aria-label="停止"
                      @click="stop(row)"
                      ><UiIcon name="stop" :size="16"
                    /></SButton>
                  </div></td
              ></template>
            </tr>
            <tr v-if="!rows.length">
              <td colspan="5" class="empty">暂无记录</td>
            </tr>
          </tbody></STable
        >
      </div></SCard
    >
    <Teleport to="body"
      ><div class="floating-actions">
        <SButton v-if="tab === 'programs'" variant="primary" @click="edit()"
          ><UiIcon name="plus" :size="16" />新增脚本</SButton
        ><SButton
          v-if="tab === 'bindings'"
          variant="primary"
          :disabled="!catalog.scripts.length"
          @click="editBinding()"
          ><UiIcon name="plus" :size="16" />新增绑定</SButton
        >
      </div></Teleport
    >
    <UiModal :open="editing" title="脚本" @close="!busy && (editing = false)"
      ><form id="script-editor" class="form-stack" @submit.prevent="saveScript">
        <div class="field">
          <label>名称</label
          ><SInput
            v-model="script.name"
            maxlength="100"
            required
            placeholder="脚本名称"
          />
        </div>
        <div class="field">
          <label>描述</label
          ><SInput
            v-model="script.description"
            placeholder="脚本用途"
            maxlength="4000"
          />
        </div>
        <div v-if="versions.length" class="field">
          <label>历史版本</label
          ><SSelect model-value="" @update:model-value="version(String($event))"
            ><option value="">当前版本</option>
            <option v-for="v in versions" :key="v.version" :value="v.version">
              {{ v.version.slice(0, 8) }} · {{ formatDate(v.at) }}
            </option></SSelect
          >
        </div>
        <div class="field">
          <label>Python</label
          ><STextarea
            v-model="script.code"
            class="code-editor"
            rows="15"
            spellcheck="false"
            required
          />
        </div>
        <div class="field">
          <label>参数 Schema</label
          ><STextarea
            v-model="script.parameters"
            class="code-editor"
            rows="5"
            spellcheck="false"
          />
        </div>
        <div class="form-row">
          <div class="field">
            <label>超时 · 秒</label
            ><SInput
              v-model.number="script.timeout"
              type="number"
              min="1"
              max="86400"
              required
            />
          </div>
          <div class="field">
            <label>忙碌时</label
            ><SSelect v-model="script.concurrency"
              ><option value="merge">合并为最新事件</option>
              <option value="queue">加入队列</option>
              <option value="skip">跳过</option></SSelect
            >
          </div>
        </div>
        <div class="field">
          <label>失败处理</label
          ><SSelect v-model="script.on_failure"
            ><option value="none">仅记录</option>
            <option value="wake">唤醒主智能体</option>
            <option value="notify">直接通知</option></SSelect
          >
        </div>
        <div v-if="script.on_failure !== 'none'" class="form-row">
          <div class="field">
            <label>连续失败次数</label
            ><SInput
              v-model.number="script.failure_threshold"
              type="number"
              min="1"
              max="100"
            />
          </div>
          <div class="field">
            <label>冷却 · 秒</label
            ><SInput
              v-model.number="script.cooldown_seconds"
              type="number"
              min="30"
            />
          </div>
        </div>
        <label v-if="script.on_failure !== 'none'" class="checkbox-field"
          ><SCheckbox
            v-model="script.send_result_to_source"
          />发送到主对话源</label
        ><label class="checkbox-field"
          ><SCheckbox v-model="script.enabled" />启用触发</label
        ><span v-if="error" class="form-error">{{ error }}</span>
      </form>
      <template #footer
        ><SButton :disabled="busy" @click="editing = false">取消</SButton
        ><SButton
          form="script-editor"
          type="submit"
          variant="primary"
          :loading="busy"
          >保存</SButton
        ></template
      ></UiModal
    >
    <UiModal
      :open="bindingOpen"
      title="触发绑定"
      @close="!busy && (bindingOpen = false)"
      ><form
        id="binding-editor"
        class="form-stack"
        @submit.prevent="saveBinding"
      >
        <div class="field">
          <label>名称</label
          ><SInput v-model="binding.name" required placeholder="绑定名称" />
        </div>
        <div class="field">
          <label>脚本</label
          ><SSelect
            :model-value="binding.script_id"
            @update:model-value="changeScript"
            ><option v-for="s in catalog.scripts" :key="s.id" :value="s.id">
              {{ s.name }}
            </option></SSelect
          >
        </div>
        <div class="field">
          <label>触发源</label
          ><SSelect
            :model-value="binding.source"
            @update:model-value="changeSource"
            ><option v-for="s in catalog.sources" :key="s.id" :value="s.id">
              {{ s.name }} · {{ s.plugin_id }}
            </option></SSelect
          >
        </div>
        <div class="field">
          <label>来源 ID</label
          ><SInput
            v-model="binding.source"
            placeholder="例如 mattermost.slash.*"
            required
            @change="loadOptions"
          />
        </div>
        <div v-if="!source" class="field">
          <label>来源参数 · JSON</label
          ><STextarea v-model="sourceParamsText" rows="3" />
        </div>
        <Parameters
          :schema="source?.parameters"
          v-model="binding.source_params"
          :options="options"
        /><Parameters
          :schema="bindingScript?.parameters"
          v-model="binding.params"
        />
        <div class="field">
          <label>失败处理</label
          ><SSelect v-model="binding.on_failure"
            ><option value="none">仅记录</option>
            <option value="wake">唤醒主智能体</option>
            <option value="notify">直接通知</option></SSelect
          >
        </div>
        <div v-if="binding.on_failure !== 'none'" class="form-row">
          <div class="field">
            <label>连续失败次数</label
            ><SInput
              v-model.number="binding.failure_threshold"
              type="number"
              min="1"
              max="100"
            />
          </div>
          <div class="field">
            <label>冷却 · 秒</label
            ><SInput
              v-model.number="binding.cooldown_seconds"
              type="number"
              min="30"
            />
          </div>
        </div>
        <label v-if="binding.on_failure !== 'none'" class="checkbox-field"
          ><SCheckbox
            v-model="binding.send_result_to_source"
          />发送到主对话源</label
        ><label class="checkbox-field"
          ><SCheckbox v-model="binding.enabled" />启用</label
        ><span v-if="error" class="form-error">{{ error }}</span>
      </form>
      <template #footer
        ><SButton :disabled="busy" @click="bindingOpen = false">取消</SButton
        ><SButton
          form="binding-editor"
          type="submit"
          variant="primary"
          :loading="busy"
          >保存</SButton
        ></template
      ></UiModal
    >
    <UiModal
      :open="runOpen"
      title="运行脚本"
      @close="!busy && (runOpen = false)"
      ><form id="run-script" class="form-stack" @submit.prevent="execute">
        <Parameters
          :schema="manualScript?.parameters"
          v-model="manual.params"
        /><span v-if="error" class="form-error">{{ error }}</span>
      </form>
      <template #footer
        ><SButton :disabled="busy" @click="runOpen = false">取消</SButton
        ><SButton
          form="run-script"
          type="submit"
          variant="primary"
          :loading="busy"
          >运行</SButton
        ></template
      ></UiModal
    >
    <UiModal :open="detailOpen" title="执行详情" @close="detailOpen = false"
      ><div v-if="detail" class="form-stack">
        <div class="detail-head">
          <STag :label="labels[detail.status]" :status="detail.status" /><span
            class="mono"
            >{{ detail.version?.slice(0, 8) }}</span
          ><span>{{ formatDate(detail.started || detail.queued) }}</span>
        </div>
        <div v-if="detail.error" class="form-error">{{ detail.error }}</div>
        <details>
          <summary>触发与参数</summary>
          <pre>{{ JSON.stringify(detail.input, null, 2) }}</pre>
        </details>
        <div class="field">
          <label>日志</label>
          <pre class="execution-log">{{ detail.logs || "—" }}</pre>
        </div>
        <details v-for="tool in detail.tool_calls" :key="tool.id">
          <summary>
            {{ tool.plugin_id }}.{{ tool.tool_name }} · {{ tool.status }}
          </summary>
          <pre>{{ tool.arguments }}</pre>
          <pre>{{ tool.error || tool.output }}</pre>
        </details>
        <div class="field">
          <label>返回结果</label>
          <pre>{{ JSON.stringify(detail.output, null, 2) }}</pre>
        </div>
      </div></UiModal
    >
    <UiModal :open="!!removing" title="删除" @close="!busy && (removing = null)"
      ><strong>{{ removing?.name }}</strong
      ><template #footer
        ><SButton :disabled="busy" @click="removing = null">取消</SButton
        ><SButton variant="danger" :loading="busy" @click="remove"
          >确认删除</SButton
        ></template
      ></UiModal
    >
  </div>
</template>
<style scoped>
.scripts-page {
  display: grid;
  gap: 18px;
  max-width: 1440px;
  margin: auto;
}
.table-toolbar {
  display: flex;
  gap: 12px;
  padding: 16px;
}
.table-toolbar > .s-input {
  max-width: 360px;
}
.row-actions,
.detail-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  background: var(--surface-alt);
  color: var(--ink);
  padding: 14px;
  border-radius: 10px;
  max-height: 480px;
  overflow: auto;
  font-size: 12px;
}
.code-editor {
  font-family: var(--font-mono, monospace);
  tab-size: 4;
}
.execution-log {
  min-height: 100px;
}
.empty {
  text-align: center;
  color: var(--muted);
  padding: 28px;
}
details {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
}
summary {
  cursor: pointer;
}
.mono {
  font-family: monospace;
}
</style>
