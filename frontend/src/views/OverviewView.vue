<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useConsole } from '../stores/console'
import { api, formatDate } from '../api'
import type { EventRecord } from '../types'
import UiIcon from '../components/UiIcon.vue'
import UiBadge from '../components/UiBadge.vue'
import UiEmpty from '../components/UiEmpty.vue'
const store = useConsole()
const events = ref<EventRecord[]>([])
const steps = computed(() => [
  {
    key: 'model',
    title: '绑定模型',
    icon: 'model',
    path: store.config?.providers.length ? '/model' : '/providers',
  },
  { key: 'persona', title: '配置 Agent', icon: 'persona', path: '/agents' },
  { key: 'plugins', title: '激活插件', icon: 'plugins', path: '/plugins' },
  ...(store.setup?.steps || []),
])
const next = computed(() =>
  steps.value.find((step) => store.requiredSteps.includes(step.key) && !store.setup?.completed[step.key]),
)
const complete = (key: string) =>
  store.setup?.completed[key] ||
  store.setup?.steps.some((step) => step.key === key && step.completed) ||
  false
async function toggle() {
  try {
    await store.activate()
  } catch {
    /* Store owns toast. */
  }
}
onMounted(async () => {
  try {
    events.value = (await api<{ items: EventRecord[] }>('events?limit=5')).items
  } catch {
    store.toast('记录加载失败', true)
  }
})
</script>
<template>
  <SPageHeader title="主导览">
    <SButton
      class="button"
      :class="store.config?.enabled ? 'danger-soft' : 'primary'"
      :disabled="store.saving || (!store.ready && !store.config?.enabled)"
      @click="toggle"
    >
      <UiIcon :name="store.config?.enabled ? 'pause' : 'power'" :size="17" />
      {{ store.config?.enabled ? '暂停 SakuBot' : '启动 SakuBot' }}
    </SButton>
  </SPageHeader>
  <section class="setup-panel">
    <div class="setup-header">
      <div class="section-heading">
        <span class="section-icon"><UiIcon name="dashboard" :size="19" /></span>
        <h2>初始化</h2>
        <span class="completion-count">
          {{ store.completed }}
          <span>/ {{ store.requiredSteps.length }}</span>
        </span>
      </div>
      <RouterLink v-if="next" :to="next.path" class="button primary compact">
        继续配置
        <UiIcon name="arrow" :size="15" />
      </RouterLink>
      <UiBadge v-else status="done" label="配置完成" />
    </div>
    <progress
      class="setup-progress"
      :value="store.completed"
      :max="store.requiredSteps.length"
      aria-label="初始化进度"
    ></progress>
    <div class="setup-grid">
      <RouterLink
        v-for="(step, index) in steps"
        :key="step.key"
        :to="step.path"
        class="setup-step"
        :class="{ completed: complete(step.key), current: next?.key === step.key }"
      >
        <div class="step-top">
          <span class="step-icon"><UiIcon :name="step.icon" :size="23" /></span>
          <span class="step-number">
            <UiIcon v-if="complete(step.key)" name="check" :size="16" />
            <template v-else>0{{ index + 1 }}</template>
          </span>
        </div>
        <h3>
          {{ step.title }}
          <span
            v-if="
              store.setup?.optional?.includes(step.key) ||
              store.setup?.steps.some((item) => item.key === step.key)
            "
            class="optional-tag"
          >
            可选
          </span>
        </h3>
        <div class="step-bottom">
          <span>{{ complete(step.key) ? '已配置' : '待配置' }}</span>
          <UiIcon name="external" :size="17" />
        </div>
      </RouterLink>
    </div>
  </section>
  <div class="metric-grid">
    <div class="metric">
      <span class="metric-icon violet"><UiIcon name="persona" /></span>
      <div class="metric-main">
        <span>Agent</span>
        <strong>{{ store.config?.enabled ? (store.status?.running ? '运行中' : '待命') : '已暂停' }}</strong>
      </div>
      <span class="metric-dot" :class="{ live: store.config?.enabled }"></span>
    </div>
    <div class="metric">
      <span class="metric-icon blue"><UiIcon name="connection" /></span>
      <div class="metric-main">
        <span>主会话</span>
        <strong class="mono">main</strong>
      </div>
      <UiIcon name="shield" class="faded" :size="16" />
    </div>
    <div class="metric">
      <span class="metric-icon amber"><UiIcon name="events" /></span>
      <div class="metric-main">
        <span>待处理事件</span>
        <strong>{{ store.pending }}</strong>
      </div>
    </div>
    <div class="metric">
      <span class="metric-icon green"><UiIcon name="plugins" /></span>
      <div class="metric-main">
        <span>启用插件</span>
        <strong>{{ store.config?.plugins.length || 0 }}</strong>
      </div>
    </div>
  </div>
  <div class="overview-bottom">
    <SCard class="surface">
      <div class="surface-heading">
        <h2>最近事件</h2>
        <RouterLink to="/events" class="text-button">
          全部
          <UiIcon name="right" :size="14" />
        </RouterLink>
      </div>
      <div v-if="events.length" class="recent-list">
        <div v-for="event in events" :key="event.id" class="recent-item">
          <span class="recent-icon">
            <UiIcon
              :name="event.kind === 'wake' ? 'events' : event.kind === 'notify' ? 'bell' : 'memory'"
              :size="17"
            />
          </span>
          <div class="recent-main">
            <strong>{{ event.label || event.source }}</strong>
            <span>{{ event.text.slice(0, 72) }}</span>
          </div>
          <div class="recent-status">
            <UiBadge :status="event.status" />
            <time>{{ formatDate(event.at) }}</time>
          </div>
        </div>
      </div>
      <UiEmpty v-else />
    </SCard>
    <SCard class="surface quick-panel">
      <div class="surface-heading"><h2>快捷入口</h2></div>
      <RouterLink
        v-for="item in [
          ...store.pages.map((p) => ({ path: p.route, icon: p.icon, title: p.title })),
          { path: '/chat', icon: 'chat', title: '主对话' },
          { path: '/runs', icon: 'activity', title: '运行记录' },
        ]"
        :key="item.path"
        :to="item.path"
        class="quick-link"
      >
        <UiIcon :name="item.icon" :size="19" />
        <span>{{ item.title }}</span>
        <UiIcon name="right" :size="15" />
      </RouterLink>
    </SCard>
  </div>
</template>

<style scoped>
.optional-tag {
  font-size: 10px;
  font-weight: 400;
  color: var(--muted);
  margin-left: 8px;
}
</style>
