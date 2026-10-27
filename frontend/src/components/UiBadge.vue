<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ status?: string; label?: string }>()
const labels: Record<string, string> = {
  done: '已完成',
  info: '信息',
  warning: '警告',
  error: '错误',
  sent: '已发送',
  online: '已连接',
  offline: '未连接',
  pending: '待处理',
  waiting: '等待答复',
  answered: '已答复',
  running: '进行中',
  failed: '失败',
  interrupted: '已中断',
  uncertain: '执行结果未知',
  unsupported: '接口未实现',
  superseded: '已转移',
  expired: '已过期',
  cancelled: '已取消',
  recorded: '已保存',
  routing: '筛选中',
  route_failed: '筛选失败',
  enabled: '已启用',
  disabled: '未启用',
  unavailable: '不可用',
  pending_configuration: '待配置',
  context: '上下文',
  wake: '唤醒 Agent',
  notify: '直接通知',
  sending: '发送中',
}
const tone = computed(() =>
  ['done', 'sent', 'online', 'enabled', 'answered'].includes(props.status || '')
    ? 'positive'
    : ['failed', 'route_failed', 'error'].includes(props.status || '')
      ? 'negative'
      : [
            'pending',
            'uncertain',
            'interrupted',
            'warning',
            'waiting',
            'unavailable',
            'pending_configuration',
          ].includes(props.status || '')
        ? 'warning'
        : ['running', 'routing', 'wake'].includes(props.status || '')
          ? 'accent'
          : 'neutral',
)
</script>
<template>
  <span class="badge" :class="tone">
    <span class="badge-dot"></span>
    {{ label || labels[status || ''] || status }}
  </span>
</template>

<style>
.badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 22px;
  border-radius: 5px;
  padding: 2px 7px;
  font-size: 10px;
  font-weight: 500;
  white-space: nowrap;
  border: 1px solid transparent;
  line-height: 1.4;
}
.badge-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.8;
}
.badge.neutral {
  background: #f1f3f7;
  color: #8991a1;
  border-color: #e9ecf2;
}
.badge.positive {
  background: #edf7f0;
  color: #5c9570;
  border-color: #e1efe6;
}
.badge.negative {
  background: #fbedee;
  color: #c06e79;
  border-color: #f5dfe3;
}
.badge.warning {
  background: #fcf5e9;
  color: #ba9861;
  border-color: #f3e9d3;
}
.badge.accent {
  background: #f0f0ff;
  color: #7d7bd0;
  border-color: #e7e6fb;
}
.badge {
  border-radius: 6px;
}
</style>
