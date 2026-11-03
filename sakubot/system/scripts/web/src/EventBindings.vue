<script setup lang="ts">
import { computed, ref, UiIcon } from '@sakubot/ui'
import { eventCatalog, type EventNode } from './event-catalog'
const props = defineProps<{ catalog: any; query: string }>()
const emit = defineEmits<{ edit: [binding: any]; create: [source: string]; remove: [binding: any] }>()
const expanded = ref(new Set<string>())
const rows = computed(() => {
  const output: { node: EventNode; depth: number }[] = []
  function append(nodes: EventNode[], depth = 0) {
    for (const node of nodes) {
      output.push({ node, depth })
      if (props.query.trim() || expanded.value.has(node.key)) append(node.children, depth + 1)
    }
  }
  append(eventCatalog(props.catalog, props.query))
  return output
})
function toggle(key: string) {
  const values = new Set(expanded.value)
  if (values.has(key)) values.delete(key)
  else values.add(key)
  expanded.value = values
}
function target(binding: any) {
  if (!binding) return '—'
  if (binding.target_kind === 'wake') return '唤醒主智能体'
  return props.catalog.scripts.find((s: any) => s.id === binding.script_id)?.name || binding.script_id
}
</script>
<template>
  <div class="table-scroll">
    <STable class="event-table">
      <thead><tr><th>事件</th><th>插件</th><th>动作</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="{node, depth} in rows" :key="node.key" :class="{'event-child': depth > 0}">
          <td>
            <div class="event-name" :style="{'--depth': depth}">
              <button v-if="node.generic || node.children.length" class="event-expand" :aria-label="expanded.has(node.key) ? '收起' : '展开'" :aria-expanded="!!query.trim() || expanded.has(node.key)" @click="toggle(node.key)">
                <UiIcon name="right" :size="16" :class="{expanded: !!query.trim() || expanded.has(node.key)}" />
              </button>
              <span v-else class="event-indent"></span>
              <div class="event-title"><div class="event-label"><strong>{{ node.name }}</strong><STag v-if="node.generic" label="泛事件" /><STag v-if="node.generic && node.bound" :label="String(node.bound)" status="enabled" /></div><span class="event-id">{{ node.id }}</span></div>
            </div>
          </td>
          <td><span class="event-plugin">{{ node.plugin }}</span></td>
          <td><div class="event-action"><span>{{ target(node.binding) }}</span><small v-if="node.binding">{{ node.binding.name }}</small></div></td>
          <td>
            <STag :label="!node.declared ? '未声明' : node.binding ? node.binding.reason || (!node.binding.enabled ? '已停用' : undefined) : node.bound ? '已绑定' : '未绑定'" :status="node.binding ? !node.binding.enabled ? 'disabled' : node.binding.available ? 'enabled' : 'unavailable' : node.bound ? 'enabled' : node.available ? 'idle' : 'unavailable'" />
          </td>
          <td><div class="row-actions">
            <template v-if="node.binding"><SButton class="icon-button" aria-label="编辑动作" @click="emit('edit', node.binding)"><UiIcon name="edit" :size="16" /></SButton><SButton class="icon-button" aria-label="删除绑定" @click="emit('remove', node.binding)"><UiIcon name="trash" :size="16" /></SButton></template>
            <SButton v-else-if="node.generic || !node.bound" class="icon-button" aria-label="绑定动作" @click="emit('create', node.id)"><UiIcon name="plus" :size="16" /></SButton>
          </div></td>
        </tr>
        <tr v-if="!rows.length"><td colspan="5" class="event-empty">暂无事件</td></tr>
      </tbody>
    </STable>
  </div>
</template>
<style scoped>
.event-table { min-width: 720px; }
.event-name { display:flex; align-items:center; gap:8px; padding-left:calc(var(--depth) * 24px); }
.event-expand { display:flex; justify-content:center; align-items:center; flex:none; width:26px; height:26px; border:0; border-radius:7px; color:var(--muted); background:transparent; cursor:pointer; }
.event-expand:hover { background:var(--surface-alt); color:var(--ink); }
.event-expand svg { transition:transform .2s ease; }
.event-expand svg.expanded { transform:rotate(90deg); }
.event-indent { width:26px; flex:none; }
.event-title, .event-action { display:flex; flex-direction:column; gap:4px; }
.event-label, .row-actions { display:flex; align-items:center; gap:8px; }
.event-title strong { font-size:13px; font-weight:600; }
.event-id { font-family:monospace; font-size:11px; color:var(--muted); overflow-wrap:anywhere; }
.event-plugin, .event-action small { font-size:12px; color:var(--muted); }
.event-empty { padding:32px; text-align:center; color:var(--muted); }
</style>
