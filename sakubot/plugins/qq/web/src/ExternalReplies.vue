<script setup lang="ts">
import {
  ref,
  reactive,
  onMounted,
  computed,
  watch,
  UiIcon,
  UiBadge,
  UiModal,
  UiEmpty,
  usePluginHost,
} from "@sakubot/ui";
interface Template {
  id: string;
  name: string;
  type: "group" | "private";
  triggers: string[];
  mention_owner_only: boolean;
  keyword_owner_only: boolean;
  keywords: string[];
  judge_probability: number;
  judge_messages: number;
  judge_start: string;
  judge_end: string;
  context_mode: string;
  context_messages: number;
  summary_messages: number;
  response_prompt: string;
}
interface Binding {
  id: string;
  session_id: string;
  template_id: string;
  enabled: boolean;
}
const triggerLabels: Record<string, string> = {
  always: "总是唤醒",
  mention: "被 @",
  keyword: "提及内容",
  agent: "Agent 判断",
};
const contextLabels: Record<string, string> = {
  session: "会话 ID",
  messages: "消息记录",
  summary: "Agent 总结",
};
const host = usePluginHost();
const tab = ref("sessions");
const enabled = ref(true);
const stateBusy = ref(false);
const requirementsOpen = ref(false);
const requirements = reactive({ prompt: "", mode: "temporary" });
const savedRequirements = ref({ prompt: "", mode: "temporary" });
function editRequirements() {
  Object.assign(requirements, savedRequirements.value);
  error.value = "";
  requirementsOpen.value = true;
}
async function saveRequirements() {
  busy.value = true;
  error.value = "";
  try {
    savedRequirements.value = await host.api<{ prompt: string; mode: string }>("external/requirements", { ...requirements });
    requirementsOpen.value = false;
    host.toast("已保存");
  } catch (e) {
    error.value = e instanceof Error ? e.message : "保存失败";
  } finally {
    busy.value = false;
  }
}
async function toggleEnabled(value: boolean) {
  stateBusy.value = true;
  try {
    const data = await host.api<{ enabled: boolean }>("external/state", {
      enabled: value,
    });
    enabled.value = data.enabled;
  } catch {
    host.toast("更新失败", true);
  } finally {
    stateBusy.value = false;
  }
}
const templates = ref<Template[]>([]);
const sessions = ref<Binding[]>([]);
const templateOpen = ref(false);
const sessionOpen = ref(false);
const busy = ref(false);
const error = ref("");
const deleting = ref<{ kind: string; id: string; name: string } | null>(null);
const availableTemplates = computed(() => templates.value.filter(row => row.type === session.type.toLowerCase()));
const isAlways = computed(() => template.type === "private" && template.triggers.includes("always"));
function toggleTrigger(value: string, enabled: boolean) {
  if (value === "always" && enabled) template.triggers = ["always"];
  else template.triggers = enabled ? [...new Set([...template.triggers.filter(x => x !== "always"), value])] : template.triggers.filter(x => x !== value);
  if (value === "keyword" && enabled && !template.keywords.length) template.keywords.push("");
}
function changeTemplateType(value: string) {
  template.type = value as "group" | "private";
  template.mention_owner_only = false;
  template.keyword_owner_only = false;
  template.triggers = value === "group" ? ["mention"] : ["always"];
}

const blank = (): Template => ({
  id: "",
  name: "",
  type: "group",
  triggers: ["mention"],
  mention_owner_only: false,
  keyword_owner_only: false,
  keywords: [],
  judge_probability: 0.1,
  judge_messages: 20,
  judge_start: "09:00",
  judge_end: "23:00",
  context_mode: "messages",
  context_messages: 20,
  summary_messages: 50,
  response_prompt: "",
});
const template = reactive<Template>(blank());
const session = reactive({
  id: "",
  type: "Group",
  number: "",
  template_id: "",
  enabled: true,
});
watch(() => session.type, () => {
  if (!availableTemplates.value.some(t => t.id === session.template_id)) session.template_id = availableTemplates.value[0]?.id || "";
});
async function load() {
  try {
    const data = await host.api<{
      enabled: boolean;
      templates: Template[];
      sessions: Binding[];
      requirements: { prompt: string; mode: string };
    }>("external/config");
    enabled.value = data.enabled;
    templates.value = data.templates;
    sessions.value = data.sessions;
    savedRequirements.value = data.requirements;
  } catch {
    error.value = "加载失败";
  }
}
function editTemplate(row?: Template) {
  Object.assign(template, row ? JSON.parse(JSON.stringify(row)) : blank());
  error.value = "";
  templateOpen.value = true;
}
function editSession(row?: Binding) {
  Object.assign(session, {
    id: row?.id || "",
    type: row?.session_id.split(":")[0] || "Group",
    number: row?.session_id.split(":")[1] || "",
    template_id: row?.template_id || templates.value.find(t => t.type === "group")?.id || "",
    enabled: row?.enabled ?? true,
  });
  error.value = "";
  sessionOpen.value = true;
}
async function saveTemplate() {
  busy.value = true;
  error.value = "";
  try {
    await host.api("external/templates", {
      ...template,
      keywords: template.keywords.map(w => w.trim()).filter(Boolean),
    });
    await load();
    templateOpen.value = false;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "保存失败";
  } finally {
    busy.value = false;
  }
}
async function saveSession() {
  busy.value = true;
  error.value = "";
  try {
    await host.api("external/sessions", {
      id: session.id,
      session_id: session.type + ":" + session.number,
      template_id: session.template_id,
      enabled: session.enabled,
    });
    await load();
    sessionOpen.value = false;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "保存失败";
  } finally {
    busy.value = false;
  }
}
async function toggle(row: Binding, enabled: boolean) {
  try {
    await host.api("external/sessions", { ...row, enabled });
    await load();
  } catch {
    error.value = "更新失败";
  }
}
async function remove() {
  if (!deleting.value) return;
  busy.value = true;
  error.value = "";
  try {
    await host.api(
      "external/" + deleting.value.kind + "/" + deleting.value.id,
      undefined,
      "DELETE",
    );
    await load();
    deleting.value = null;
  } catch {
    error.value = "删除失败";
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>
<template>
  <div class="page-heading">
    <div class="heading-actions">
      <SSwitch
        :model-value="enabled"
        :loading="stateBusy"
        label="启用外部消息回应"
        @change="toggleEnabled"
      />
      <SButton icon="settings" @click="editRequirements">额外要求</SButton>
      <SButton class="button" @click="host.navigate('/agents')">
        Agent 管理</SButton
      ><SButton
        class="button primary"
        @click="tab === 'sessions' ? editSession() : editTemplate()"
      >
        <UiIcon name="plus" :size="16" />{{
          tab === "sessions" ? "新增会话" : "新增模板"
        }}
      </SButton>
    </div>
  </div>
  <UiModal :open="requirementsOpen" title="额外要求" @close="!busy && (requirementsOpen = false)">
    <form id="qq-requirements-form" class="form-stack" @submit.prevent="saveRequirements">
      <SFormItem label="提示词" for="qq-extra-prompt">
        <STextarea id="qq-extra-prompt" v-model="requirements.prompt" :maxlength="10000" rows="6" />
      </SFormItem>
      <SFormItem label="注入模式" for="qq-extra-mode">
        <SSelect id="qq-extra-mode" v-model="requirements.mode">
          <option value="temporary">临时</option>
          <option value="context">上下文</option>
        </SSelect>
      </SFormItem>
      <span v-if="error" class="form-error">{{ error }}</span>
    </form>
    <template #footer>
      <SButton :disabled="busy" @click="requirementsOpen = false">取消</SButton>
      <SButton form="qq-requirements-form" type="submit" variant="primary" :loading="busy">保存</SButton>
    </template>
  </UiModal>
  <div class="page-toolbar">
    <SButton
      class="button"
      :class="{ primary: tab === 'sessions' }"
      @click="tab = 'sessions'"
    >
      会话列表</SButton
    ><SButton
      class="button"
      :class="{ primary: tab === 'templates' }"
      @click="tab = 'templates'"
    >
      响应模板</SButton
    ><span
      v-if="error && !templateOpen && !sessionOpen && !deleting"
      class="form-error"
      >{{ error }}</span
    >
  </div>
  <SCard v-if="tab === 'sessions'" class="surface">
    <div class="table-scroll">
      <STable class="data-table">
        <thead>
          <tr>
            <th>会话</th>
            <th>响应模板</th>
            <th>启用</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in sessions" :key="row.id">
            <td class="mono">{{ row.session_id }}</td>
            <td>
              {{
                templates.find((t) => t.id === row.template_id)?.name ||
                row.template_id
              }}
            </td>
            <td>
              <SSwitch
                :model-value="row.enabled"
                :aria-label="row.session_id"
                @change="toggle(row, $event)"
              />
            </td>
            <td>
              <div class="row-actions">
                <SButton class="text-button" @click="editSession(row)">
                  编辑</SButton
                ><SButton
                  class="text-button danger-text"
                  @click="
                    deleting = {
                      kind: 'sessions',
                      id: row.id,
                      name: row.session_id,
                    }
                  "
                >
                  删除
                </SButton>
              </div>
            </td>
          </tr>
        </tbody>
      </STable>
    </div>
    <UiEmpty v-if="!sessions.length" label="暂无会话" />
  </SCard>
  <SCard v-else class="surface">
    <div class="table-scroll">
      <STable class="data-table">
        <thead>
          <tr>
            <th>名称</th>
            <th>类型</th>
            <th>唤醒判断</th>
            <th>上下文</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in templates" :key="row.id">
            <td>
              <strong>{{ row.name }}</strong>
            </td>
            <td>{{ row.type === 'private' ? '私聊' : '群聊' }}</td>
            <td>
              <span
                v-for="trigger in row.triggers"
                :key="trigger"
                class="badge neutral"
                >{{ triggerLabels[trigger] }}</span
              >
            </td>
            <td>{{ contextLabels[row.context_mode] }}</td>
            <td>
              <div class="row-actions">
                <SButton class="text-button" @click="editTemplate(row)">
                  编辑</SButton
                ><SButton
                  class="text-button danger-text"
                  @click="
                    deleting = { kind: 'templates', id: row.id, name: row.name }
                  "
                >
                  删除
                </SButton>
              </div>
            </td>
          </tr>
        </tbody>
      </STable>
    </div>
    <UiEmpty v-if="!templates.length" label="暂无模板" />
  </SCard>
  <UiModal
    :open="sessionOpen"
    :title="session.id ? '编辑会话' : '新增会话'"
    @close="sessionOpen = false"
    ><form id="reply-session" class="form-stack" @submit.prevent="saveSession">
      <div class="form-row">
        <div class="field">
          <label for="session-type">类型</label
          ><SSelect id="session-type" v-model="session.type">
            <option value="Group">群聊</option>
            <option value="Private">私聊</option>
          </SSelect>
        </div>
        <div class="field">
          <label for="session-number">QQ / 群号</label
          ><SInput
            id="session-number"
            v-model="session.number"
            inputmode="numeric"
            pattern="[1-9][0-9]*"
            required
          />
        </div>
      </div>
      <div class="field">
        <label for="session-template">响应模板</label
        ><SSelect id="session-template" v-model="session.template_id" required>
          <option v-for="row in availableTemplates" :key="row.id" :value="row.id">
            {{ row.name }}
          </option>
        </SSelect>
      </div>
      <label class="check-label"
        ><SCheckbox v-model="session.enabled" />启用</label
      ><span v-if="error" class="form-error">{{ error }}</span>
    </form>
    <template #footer
      ><SButton class="button" @click="sessionOpen = false">取消</SButton
      ><SButton
        form="reply-session"
        class="button primary"
        :disabled="busy || !session.template_id"
      >
        保存
      </SButton></template
    ></UiModal
  >
  <UiModal
    :open="templateOpen"
    :title="template.id ? '编辑模板' : '新增模板'"
    wide
    @close="templateOpen = false"
    ><form
      id="reply-template"
      class="form-stack"
      @submit.prevent="saveTemplate"
    >
      <div class="field">
        <label for="template-name">名称</label
        ><SInput
          id="template-name"
          v-model="template.name"
          maxlength="100"
          required
        />
      </div>
      <div class="field">
        <label for="template-type">类型</label>
        <SSelect id="template-type" :model-value="template.type" :disabled="!!template.id && sessions.some(s => s.template_id === template.id)" @update:model-value="changeTemplateType">
          <option value="group">群聊</option><option value="private">私聊</option>
        </SSelect>
      </div>
      <div class="field">
        <label>唤醒判断</label>
        <div class="trigger-accordion">
          <div v-if="template.type === 'private'" class="trigger-item">
            <label class="trigger-header"><SCheckbox :model-value="template.triggers.includes('always')" @update:model-value="toggleTrigger('always', $event)" />总是唤醒</label>
          </div>
          <div v-if="template.type === 'group'" class="trigger-item">
            <label class="trigger-header"><SCheckbox :model-value="template.triggers.includes('mention')" @update:model-value="toggleTrigger('mention', $event)" />自己被 @</label>
            <div class="trigger-expand" :class="{ open: template.triggers.includes('mention') }"><div class="trigger-inner">
              <label class="check-label"><SCheckbox v-model="template.mention_owner_only" />仅被主人 @</label>
            </div></div>
          </div>
          <div class="trigger-item" :class="{ disabled: isAlways }">
            <label class="trigger-header"><SCheckbox :model-value="template.triggers.includes('keyword')" :disabled="isAlways" @update:model-value="toggleTrigger('keyword', $event)" />提及内容</label>
            <div class="trigger-expand" :class="{ open: template.triggers.includes('keyword') }"><div class="trigger-inner">
              <div v-for="(_, index) in template.keywords" :key="index" class="keyword-row">
                <SInput v-model="template.keywords[index]" :disabled="!template.triggers.includes('keyword')" :required="template.triggers.includes('keyword')" maxlength="200" placeholder="填写提及内容" />
                <SButton class="icon-button" type="button" title="移除" aria-label="移除提及内容" @click="template.keywords.splice(index, 1)"><UiIcon name="trash" :size="16" /></SButton>
              </div>
              <SButton type="button" icon="plus" size="small" :disabled="template.keywords.length >= 100" @click="template.keywords.push('')">新增内容</SButton>
              <label v-if="template.type === 'group'" class="check-label"><SCheckbox v-model="template.keyword_owner_only" />仅被主人提及</label>
            </div></div>
          </div>
          <div class="trigger-item" :class="{ disabled: isAlways }">
            <label class="trigger-header"><SCheckbox :model-value="template.triggers.includes('agent')" :disabled="isAlways" @update:model-value="toggleTrigger('agent', $event)" />Agent 判断</label>
            <div class="trigger-expand" :class="{ open: template.triggers.includes('agent') }"><div class="trigger-inner">
              <fieldset :disabled="!template.triggers.includes('agent')" class="trigger-fields">
                <div class="form-row">
                  <div class="field"><label for="judge-probability">判断概率</label><SInput id="judge-probability" v-model.number="template.judge_probability" type="number" min="0" max="1" step="0.01" required /></div>
                  <div class="field"><label for="judge-messages">判断消息条数</label><SInput id="judge-messages" v-model.number="template.judge_messages" type="number" min="1" max="200" required /></div>
                </div>
                <div class="form-row">
                  <div class="field"><label for="judge-start">生效开始</label><SInput id="judge-start" v-model="template.judge_start" type="time" required /></div>
                  <div class="field"><label for="judge-end">生效结束</label><SInput id="judge-end" v-model="template.judge_end" type="time" required /></div>
                </div>
              </fieldset>
            </div></div>
          </div>
        </div>
      </div>
      <div class="field">
        <label for="context-mode">唤醒前上下文</label
        ><SSelect id="context-mode" v-model="template.context_mode">
          <option value="session">仅会话 ID</option>
          <option value="messages">消息记录</option>
          <option value="summary">Agent 总结</option>
        </SSelect>
      </div>
      <div v-if="template.context_mode === 'messages'" class="field">
        <label for="context-count">注入消息条数</label
        ><SInput
          id="context-count"
          v-model.number="template.context_messages"
          type="number"
          min="1"
          max="200"
          required
        />
      </div>
      <div v-if="template.context_mode === 'summary'" class="field">
        <label for="summary-count">总结消息条数</label
        ><SInput
          id="summary-count"
          v-model.number="template.summary_messages"
          type="number"
          min="1"
          max="200"
          required
        />
      </div>
      <div class="field">
        <label for="response-prompt">响应要求</label
        ><STextarea
          id="response-prompt"
          v-model="template.response_prompt"
          rows="4"
          maxlength="10000"
        ></STextarea>
      </div>
      <span v-if="error" class="form-error">{{ error }}</span>
    </form>
    <template #footer
      ><SButton class="button" @click="templateOpen = false">取消</SButton
      ><SButton form="reply-template" class="button primary" :disabled="busy">
        保存
      </SButton></template
    ></UiModal
  >
  <UiModal :open="!!deleting" title="删除" @close="deleting = null"
    ><strong>{{ deleting?.name }}</strong
    ><span v-if="error" class="form-error">{{ error }}</span
    ><template #footer
      ><SButton class="button" @click="deleting = null">取消</SButton
      ><SButton class="button danger-soft" :disabled="busy" @click="remove">
        删除
      </SButton></template
    ></UiModal
  >
</template>

<style scoped>
.trigger-accordion { display:grid;gap:10px; }
.trigger-item { border:1px solid var(--border);border-radius:11px;background:#fff;overflow:hidden;transition:border-color .2s,opacity .2s; }
.trigger-item:has(.trigger-expand.open) { border-color:#cfc7ee; }
.trigger-item.disabled { opacity:.55; }
.trigger-header { display:flex;align-items:center;gap:10px;padding:13px 15px;cursor:pointer;font-weight:550; }
.trigger-item.disabled .trigger-header { cursor:not-allowed; }
.trigger-expand { display:grid;grid-template-rows:0fr;transition:grid-template-rows .25s ease; }
.trigger-expand.open { grid-template-rows:1fr; }
.trigger-inner { min-height:0;overflow:hidden;display:flex;flex-direction:column;gap:12px; }
.trigger-expand.open .trigger-inner { padding:0 15px 15px; }
.trigger-fields { display:grid;gap:14px;border:0;padding:0;margin:0;min-width:0; }
.keyword-row { display:flex;align-items:center;gap:8px; }
.keyword-row .s-input { flex:1; }
@media (prefers-reduced-motion: reduce) { .trigger-expand { transition:none; } }
</style>
