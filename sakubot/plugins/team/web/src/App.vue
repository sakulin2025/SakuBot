<script setup lang="ts">
import {
  ref,
  reactive,
  computed,
  onMounted,
  onUnmounted,
  UiIcon,
  UiBadge,
  UiModal,
  UiEmpty,
  usePluginHost,
  formatDate,
} from "@sakubot/ui";
import type { Task, AgentInfo } from "@sakubot/ui";
interface Member {
  id: string;
  name: string;
  description: string;
  persona?: { prompt: string; visible_plugins: string[] | null } | null;
  model_id?: string;
  agent: AgentInfo;
}
interface Confirmation {
  id: string;
  agent_id: string;
  task_id: string;
  kind: string;
  question: string;
  context: string;
  options: string[];
  status: string;
  answer: string;
  approved: boolean | null;
  created: number;
}
const requests = ref<Confirmation[]>([]);
const responding = ref<Confirmation | null>(null);
const reply = reactive({ answer: "", approved: "" });
const replyError = ref("");
const pendingCount = computed(
  () => requests.value.filter((r) => r.status === "waiting").length,
);
function respond(row: Confirmation) {
  responding.value = row;
  reply.answer = "";
  reply.approved = "";
  replyError.value = "";
}
async function resolveRequest() {
  if (!responding.value) return;
  busy.value = true;
  replyError.value = "";
  try {
    const row = responding.value;
    await host.api("requests/resolve", {
      request_id: row.id,
      answer: reply.answer,
      ...(row.kind === "confirmation"
        ? { approved: reply.approved === "true" }
        : {}),
    });
    await load();
    responding.value = null;
  } catch {
    replyError.value = "答复失败";
  } finally {
    busy.value = false;
  }
}
const host = usePluginHost();
const members = ref<Member[]>([]);
const tasks = ref<Task[]>([]);
const tab = ref("members");
const query = ref("");
const editing = ref(false);
const deleting = ref<Member | null>(null);
const detail = ref<Task | null>(null);
const busy = ref(false);
const form = reactive({
  id: "",
  name: "",
  description: "",
  model_id: "",
  prompt: "",
  visibility: "all",
  visible_plugins: [] as string[],
});
const models = ref<{ id: string; name: string; model_id: string }[]>([]);
const plugins = ref<{ name: string; label: string }[]>([]);
const selectedMember = computed(() =>
  members.value.find((m) => m.id === form.id),
);
function closeEditor() {
  if (!busy.value) editing.value = false;
}
let timer: ReturnType<typeof setInterval> | undefined;
const visible = computed(() =>
  members.value.filter((m) => (m.name + m.description).includes(query.value)),
);
async function load() {
  try {
    const data = await host.api<{ items: Member[] }>("members");
    members.value = data.items;
    const values = await Promise.all([
      host.api<Task[]>("tasks"),
      host.api<Confirmation[]>("requests"),
      host.coreApi<{
        models: {
          id: string;
          name: string;
          model_id: string;
          enabled: boolean;
          provider_id: string;
          capabilities: { text: boolean };
        }[];
        providers: { id: string; enabled: boolean }[];
      }>("config"),
      host.coreApi<{ plugins: { name: string; label: string; required: boolean }[] }>(
        "plugin-registry",
      ),
    ]);
    tasks.value = values[0];
    if (detail.value) detail.value = tasks.value.find((task) => task.id === detail.value?.id) || detail.value;
    requests.value = values[1];
    models.value = values[2].models.filter(
      (m) =>
        m.enabled &&
        m.capabilities.text &&
        values[2].providers.some((p) => p.id === m.provider_id && p.enabled),
    );
    plugins.value = values[3].plugins.filter((plugin) => !plugin.required);
  } catch {
    host.toast("加载失败", true);
  }
}
function edit(member?: Member) {
  Object.assign(form, {
    id: member?.id || "",
    name: member?.name || "",
    description: member?.description || "",
    model_id: member?.model_id || "",
    prompt: member?.persona?.prompt || "",
    visibility: member?.persona?.visible_plugins == null ? "all" : "selected",
    visible_plugins: [...(member?.persona?.visible_plugins || [])],
  });
  editing.value = true;
}
async function save() {
  busy.value = true;
  try {
    await host.api("members", {
      id: form.id,
      name: form.name,
      description: form.description,
      model_id: form.model_id,
      persona: {
        prompt: form.prompt,
        visible_plugins:
          form.visibility === "all" ? null : form.visible_plugins,
      },
    });
    await load();
    host.refresh();
    editing.value = false;
    host.toast("已保存");
  } catch {
    host.toast("保存失败", true);
  } finally {
    busy.value = false;
  }
}
async function remove() {
  if (!deleting.value) return;
  busy.value = true;
  try {
    await host.api(
      "members/" + encodeURIComponent(deleting.value.id),
      undefined,
      "DELETE",
    );
    await load();
    host.refresh();
    deleting.value = null;
    host.toast("已删除");
  } catch {
    host.toast("删除失败", true);
  } finally {
    busy.value = false;
  }
}
async function cancel(id: string) {
  try {
    await host.api("tasks", { action: "cancel", id });
    await load();
    host.toast("已取消");
  } catch {
    host.toast("操作失败", true);
  }
}
onMounted(() => {
  load();
  timer = setInterval(() => {
    if (!document.hidden) load();
  }, 5000);
});
onUnmounted(() => {
  if (timer) clearInterval(timer);
});
</script>
<template>
  <div class="page-heading">
    <div class="heading-title">
      <span class="page-kicker">工作台</span>
      <h1>专业团队</h1>
      <span class="heading-count">{{ members.length }}</span>
    </div>
    <div class="heading-actions">
      <SButton class="button" @click="host.navigate('/agents')">
        Agent 管理</SButton
      ><SButton class="button primary" @click="edit()">
        <UiIcon name="plus" :size="17" />新增 Agent
      </SButton>
    </div>
  </div>
  <div class="page-toolbar">
    <SButton
      class="button"
      :class="{ primary: tab === 'members' }"
      @click="tab = 'members'"
    >
      团队成员</SButton
    ><SButton
      class="button"
      :class="{ primary: tab === 'tasks' }"
      @click="tab = 'tasks'"
    >
      任务记录
    </SButton>
    <SButton
      class="button"
      :class="{ primary: tab === 'requests' }"
      @click="tab = 'requests'"
    >
      待确认<span v-if="pendingCount" class="button-count">{{
        pendingCount
      }}</span>
    </SButton>
    <div v-if="tab === 'members'" class="search-field">
      <UiIcon name="search" :size="17" /><SInput
        v-model="query"
        placeholder="搜索成员"
        aria-label="搜索成员"
      />
    </div>
  </div>
  <template v-if="tab === 'members'"
    ><div class="plugin-grid">
      <section v-for="member in visible" :key="member.id" class="plugin-card">
        <div class="plugin-card-top">
          <span class="plugin-icon"><UiIcon name="persona" :size="26" /></span
          ><UiBadge
            :status="
              member.agent.busy
                ? 'running'
                : member.agent.ready
                  ? 'done'
                  : 'pending'
            "
            :label="
              member.agent.busy
                ? '运行中'
                : member.agent.ready
                  ? '就绪'
                  : '待配置'
            "
          />
        </div>
        <h2>{{ member.name }}</h2>
        <div class="agent-description">{{ member.description || "—" }}</div>
        <span class="plugin-id mono">team:{{ member.id }}</span>
        <div class="cell-sub">
          {{ member.agent.persona_name }}
          · {{ member.agent.model_name }}
        </div>
        <div class="plugin-card-bottom">
          <SButton class="button compact" @click="edit(member)">编辑</SButton
          ><SButton
            class="button compact danger-soft"
            @click="deleting = member"
          >
            删除
          </SButton>
        </div>
      </section>
    </div>
    <UiEmpty v-if="!visible.length" label="暂无团队成员" icon="people"
  /></template>
  <SCard v-else-if="tab === 'tasks'" class="surface">
    <div class="table-scroll">
      <STable class="data-table">
        <thead>
          <tr>
            <th>任务</th>
            <th>状态</th>
            <th>进度</th>
            <th>更新时间</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in tasks" :key="task.id">
            <td>
              <strong>{{ task.data.goal }}</strong
              ><span class="cell-sub mono">{{ task.id }}</span>
            </td>
            <td><UiBadge :status="task.status" /></td>
            <td><span class="team-progress" :title="task.data.progress">{{ task.data.progress || "—" }}</span></td>
            <td>{{ formatDate(task.updated) }}</td>
            <td>
              <div class="row-actions">
                <SButton
                  v-if="['pending', 'running', 'waiting'].includes(task.status)"
                  class="text-button danger-text"
                  @click="cancel(task.id)"
                >
                  取消</SButton
                ><SButton class="text-button" @click="detail = task">
                  详情
                </SButton>
              </div>
            </td>
          </tr>
        </tbody>
      </STable>
    </div>
    <UiEmpty v-if="!tasks.length" />
  </SCard>
  <SCard v-else class="surface">
    <div class="table-scroll">
      <STable class="data-table">
        <thead>
          <tr>
            <th>问题 / 操作</th>
            <th>Agent</th>
            <th>类型</th>
            <th>状态</th>
            <th>时间</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in requests" :key="row.id">
            <td>
              <strong>{{ row.question }}</strong
              ><span class="cell-sub mono">{{ row.id }}</span
              ><span v-if="row.answer" class="cell-sub">{{ row.answer }}</span>
            </td>
            <td>
              {{
                members.find((m) => "team:" + m.id === row.agent_id)?.name ||
                row.agent_id
              }}
            </td>
            <td>{{ row.kind === "confirmation" ? "确认操作" : "提问" }}</td>
            <td><UiBadge :status="row.status" /></td>
            <td>{{ formatDate(row.created) }}</td>
            <td>
              <SButton
                v-if="row.status === 'waiting'"
                class="text-button"
                @click="respond(row)"
              >
                答复
              </SButton>
            </td>
          </tr>
        </tbody>
      </STable>
    </div>
    <UiEmpty v-if="!requests.length" label="暂无请求" />
  </SCard>
  <UiModal :open="!!responding" title="答复" @close="responding = null"
    ><form id="team-answer" class="form-stack" @submit.prevent="resolveRequest">
      <div class="field">
        <label>问题 / 操作</label>
        <pre class="detail-text">{{ responding?.question }}</pre>
      </div>
      <div v-if="responding?.context" class="field">
        <label>上下文</label>
        <pre class="detail-text">{{ responding.context }}</pre>
      </div>
      <div v-if="responding?.options.length" class="capability-tags">
        <SButton
          v-for="option in responding.options"
          :key="option"
          class="button compact"
          type="button"
          @click="reply.answer = option"
        >
          {{ option }}
        </SButton>
      </div>
      <div v-if="responding?.kind === 'confirmation'" class="field">
        <label for="team-decision">确认结果</label
        ><SSelect id="team-decision" v-model="reply.approved" required>
          <option value="">请选择</option>
          <option value="true">同意</option>
          <option value="false">拒绝</option>
        </SSelect>
      </div>
      <div class="field">
        <label for="team-answer-text">答复</label
        ><STextarea
          id="team-answer-text"
          v-model="reply.answer"
          rows="5"
          :required="responding?.kind === 'question'"
          maxlength="20000"
        ></STextarea>
      </div>
      <span v-if="replyError" class="form-error">{{ replyError }}</span>
    </form>
    <template #footer
      ><SButton class="button" @click="responding = null">取消</SButton
      ><SButton class="button primary" form="team-answer" :disabled="busy">
        提交
      </SButton></template
    ></UiModal
  >
  <UiModal
    :open="editing"
    :title="form.id ? '编辑 Agent' : '新增 Agent'"
    wide
    @close="closeEditor"
    ><form id="team-member" class="form-stack" @submit.prevent="save">
      <div class="field">
        <label for="member-name">名称</label
        ><SInput
          id="member-name"
          v-model="form.name"
          required
          maxlength="100"
        />
      </div>
      <div class="field">
        <label for="member-description">描述</label
        ><STextarea
          id="member-description"
          v-model="form.description"
          rows="7"
          maxlength="10000"
        ></STextarea>
      </div>
      <div class="field">
        <label for="member-prompt">人格内容</label
        ><STextarea
          id="member-prompt"
          v-model="form.prompt"
          rows="10"
          maxlength="100000"
          required
        />
      </div>
      <div class="field">
        <label for="member-visibility">可见插件</label>
        <SSelect id="member-visibility" v-model="form.visibility"
          ><option value="all">全部插件</option>
          <option value="selected">指定插件</option></SSelect
        >
        <div v-if="form.visibility === 'selected'" class="capability-tags">
          <label v-for="plugin in plugins" :key="plugin.name"
            ><SCheckbox v-model="form.visible_plugins" :value="plugin.name" />
            {{ plugin.label || plugin.name }}</label
          >
        </div>
      </div>
      <div class="field">
        <label for="member-model">模型</label>
        <SSelect id="member-model" v-model="form.model_id"
          ><option value="">默认</option>
          <option v-for="model in models" :key="model.id" :value="model.id">
            {{ model.name || model.model_id }}
          </option>
        </SSelect>
      </div>
      <div
        v-if="selectedMember?.agent.model_source === 'override'"
        class="field"
      >
        <label>当前模型 · 手动覆盖</label
        ><span>{{ selectedMember.agent.model_name }}</span>
      </div>
    </form>
    <template #footer
      ><SButton class="button" :disabled="busy" @click="closeEditor"
        >取消</SButton
      ><SButton class="button primary" form="team-member" :disabled="busy">
        保存
      </SButton></template
    ></UiModal
  >
  <UiModal :open="!!deleting" title="删除 Agent" @close="deleting = null"
    ><strong>{{ deleting?.name }}</strong
    ><template #footer
      ><SButton class="button" @click="deleting = null">取消</SButton
      ><SButton class="button danger-soft" :disabled="busy" @click="remove">
        删除
      </SButton></template
    ></UiModal
  >
  <UiModal :open="!!detail" title="团队任务" wide @close="detail = null"
    ><div v-if="detail" class="detail-stack">
      <UiBadge :status="detail.status" />
      <div class="field">
        <label>目标</label>
        <pre class="detail-text">{{ detail.data.goal }}</pre>
      </div>
      <div class="field">
        <label>进度</label>
        <pre class="detail-text">{{ detail.data.progress || "—" }}</pre>
      </div>
      <div class="field">
        <label>结果</label>
        <pre class="detail-text">{{ detail.data.result || "—" }}</pre>
      </div>
      <SButton
        v-if="detail.data.run_id"
        class="button"
        @click="host.navigate('/tool-calls?run_id=' + detail.data.run_id)"
      >
        工具调用
      </SButton>
    </div></UiModal
  >
</template>

<style scoped>
.team-progress {
  display: -webkit-box;
  max-width: 320px;
  white-space: normal;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
</style>
