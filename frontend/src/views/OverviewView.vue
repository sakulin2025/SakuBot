<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '../api'
import { useConsole } from '../stores/console'
import UiIcon from '../components/UiIcon.vue'
import UiBadge from '../components/UiBadge.vue'
const store = useConsole()
const steps = computed(() => [
  {
    key: 'model',
    title: '绑定模型',
    icon: 'model',
    path: store.config?.providers.length ? '/model' : '/providers',
  },
  { key: 'agent', title: '配置智能体', icon: 'persona', path: '/agents' },
])
const next = computed(() =>
  steps.value.find((step) => store.requiredSteps.includes(step.key) && !store.setup?.completed[step.key]),
)
const complete = (key: string) =>
  store.setup?.completed[key] || false
const compressDialog = ref(false)
const compressBusy = ref(false)
const compressError = ref('')
const compressionRunning = computed(() => (store.status?.running as any)?.kind === 'compression')
async function compressContext() {
  if (compressBusy.value) return
  compressBusy.value = true
  compressError.value = ''
  try {
    await api('chat/compress-context', { body: { confirmation: '压缩' } })
    compressDialog.value = false
    await store.refreshStatus()
    store.toast('已开始压缩')
  } catch (error) {
    compressError.value = error instanceof Error ? error.message : '压缩失败'
  } finally {
    compressBusy.value = false
  }
}
function openCompression() {
  compressError.value = ''
  compressDialog.value = true
}
</script>
<template>
  <div class="overview">
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
        <h3>{{ step.title }}</h3>
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
        <span>上下文占用</span>
        <strong class="mono">{{ store.status?.main_context_usage ? `${store.status.main_context_usage.estimated ? '约 ' : ''}${store.status.main_context_usage.percent}%` : '—' }}</strong>
      </div>
      <SButton class="compact" :loading="compressionRunning" :disabled="!!store.status?.running" @click="openCompression">压缩</SButton>
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
  <footer class="overview-footer">
    <a href="https://github.com/sakulin2025/SakuBot" target="_blank" rel="noopener noreferrer">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 .297a12 12 0 0 0-3.793 23.387c.6.111.82-.261.82-.577v-2.234c-3.338.726-4.042-1.416-4.042-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.09-.745.083-.73.083-.73 1.205.085 1.84 1.236 1.84 1.236 1.07 1.835 2.807 1.305 3.492.998.108-.776.418-1.305.762-1.605-2.665-.304-5.467-1.333-5.467-5.93 0-1.311.469-2.381 1.236-3.221-.124-.303-.536-1.524.117-3.176 0 0 1.008-.322 3.3 1.23a11.5 11.5 0 0 1 6.006 0c2.291-1.552 3.297-1.23 3.297-1.23.655 1.652.243 2.873.12 3.176.77.84 1.235 1.91 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.103.823 2.222v3.294c0 .319.216.694.825.576A12.001 12.001 0 0 0 12 .297"/></svg>
      <span>github.com/sakulin2025/SakuBot</span>
    </a>
  </footer>
  <SDialog :open="compressDialog" title="确认压缩主对话上下文" @close="!compressBusy && (compressDialog = false)">
    <span v-if="compressError" class="form-error">{{ compressError }}</span>
    <template #footer>
      <SButton :disabled="compressBusy" @click="compressDialog = false">取消</SButton>
      <SButton variant="primary" :loading="compressBusy" @click="compressContext">确认压缩</SButton>
    </template>
  </SDialog>
  </div>
</template>

<style scoped>
.overview { display: flex; flex-direction: column; min-height: calc(100dvh - 202px); }
.overview-footer { display: flex; justify-content: center; margin-top: auto; padding-top: 48px; }
.overview-footer a { display: inline-flex; align-items: center; gap: 9px; color: var(--muted); text-decoration: none; font-size: 12px; transition: color .2s; }
.overview-footer a:hover { color: var(--accent); }
.setup-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
@media (max-width: 700px) { .setup-grid { grid-template-columns: 1fr; } .overview { min-height: calc(100dvh - 180px); } }
</style>
