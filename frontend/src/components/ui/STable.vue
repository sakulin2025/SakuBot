<script setup lang="ts">
import { computed, ref } from 'vue'
const props = withDefaults(
  defineProps<{
    rows?: Record<string, unknown>[]
    columns?: { key: string; label: string; sortable?: boolean }[]
    rowKey?: string
    loading?: boolean
    emptyText?: string
  }>(),
  { rowKey: 'id', emptyText: '暂无记录' },
)
const emit = defineEmits<{ 'sort-change': [value: { key: string; direction: 'asc' | 'desc' }] }>()
const sort = ref({ key: '', direction: 'asc' as 'asc' | 'desc' })
const rows = computed(() => {
  const data = [...(props.rows || [])]
  if (sort.value.key)
    data.sort(
      (a, b) =>
        String(a[sort.value.key] ?? '').localeCompare(String(b[sort.value.key] ?? ''), 'zh-CN', {
          numeric: true,
        }) * (sort.value.direction === 'asc' ? 1 : -1),
    )
  return data
})
function order(key: string) {
  sort.value = { key, direction: sort.value.key === key && sort.value.direction === 'asc' ? 'desc' : 'asc' }
  emit('sort-change', sort.value)
}
</script>
<template>
  <table class="data-table s-table" :aria-busy="loading || undefined">
    <slot>
      <thead>
        <tr>
          <th v-for="column in columns" :key="column.key">
            <button
              v-if="column.sortable"
              type="button"
              class="text-button s-sort"
              @click="order(column.key)"
            >
              {{ column.label }}
              <span>{{ sort.key === column.key ? (sort.direction === 'asc' ? '↑' : '↓') : '↕' }}</span>
            </button>
            <template v-else>{{ column.label }}</template>
          </th>
        </tr>
      </thead>
      <tbody>
        <template v-for="(row, index) in rows" :key="String(row[rowKey] ?? index)">
          <slot name="row" :row="row" :index="index">
            <tr>
              <td v-for="column in columns" :key="column.key">
                <slot :name="'cell-' + column.key" :row="row" :value="row[column.key]">
                  {{ row[column.key] }}
                </slot>
              </td>
            </tr>
          </slot>
        </template>
        <tr v-if="!rows.length">
          <td :colspan="columns?.length || 1" class="s-table-empty">{{ loading ? '加载中' : emptyText }}</td>
        </tr>
      </tbody>
    </slot>
  </table>
</template>

<style>
.data-table {
  border-collapse: collapse;
  width: 100%;
  text-align: left;
  white-space: normal;
}
.data-table th {
  font-size: 10px;
  font-weight: 500;
  background: #fbfcfe;
  color: #a6adbb;
  padding: 13px 21px;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.data-table td {
  font-size: 11px;
  color: #7c8598;
  padding: 18px 21px;
  border-bottom: 1px solid #f0f2f6;
  vertical-align: middle;
}
.data-table tr:last-child td {
  border-bottom: 0;
}
.data-table tr:hover td {
  background: #fdfdff;
}
.data-table td strong {
  color: #646e82;
  font-weight: 550;
}
.data-table .mono {
  font-size: 10px;
}
.data-table .content-cell {
  max-width: 330px;
  min-width: 160px;
  overflow-wrap: anywhere;
  line-height: 1.8;
}
@media (max-width: 700px) {
  .data-table th,
  .data-table td {
    padding-left: 16px;
    padding-right: 16px;
  }
}
.s-sort {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: inherit;
  font-weight: inherit;
}
.s-sort span {
  font-size: 11px;
  color: var(--muted);
}
.data-table th {
  background: #fafafe;
  color: #9294a7;
  font-size: 11px;
  letter-spacing: 0.02em;
  font-weight: 550;
  border-color: var(--border);
}
.data-table td {
  border-color: #f0f0f6;
}
.data-table tbody tr:hover {
  background: #faf9fe;
}
.data-table td:first-child,
.data-table th:first-child {
  padding-left: 22px;
}
</style>
