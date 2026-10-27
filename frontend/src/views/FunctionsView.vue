<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api'
import { useConsole } from '../stores/console'
import UiIcon from '../components/UiIcon.vue'
import UiModal from '../components/UiModal.vue'
import UiEmpty from '../components/UiEmpty.vue'
import type { FunctionInfo } from '../types'
defineProps<{ embedded?: boolean }>()
const store = useConsole()
const items = ref<FunctionInfo[]>([])
const query = ref('')
const loading = ref(false)
const detail = ref<FunctionInfo | null>(null)
const filtered = computed(() => {
  const search = query.value.trim().toLowerCase()
  return items.value.filter((fn) =>
    ((fn.source_label || fn.plugin_id) + '.' + fn.name + ' ' + fn.plugin_id + ' ' + fn.description).toLowerCase().includes(search),
  )
})
async function load() {
  loading.value = true
  try {
    const data = await api<{ items: FunctionInfo[] }>('functions')
    items.value = data.items
  } catch {
    store.toast('加载失败', true)
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch([() => store.status?.registry_revision, () => store.status?.agents_revision], load)
</script>
<template>
  <SPageHeader v-if="!embedded" title="可用函数">
    <SButton :loading="loading" @click="load">刷新</SButton>
  </SPageHeader>
  <div class="page-toolbar">
    <div class="search-field">
      <UiIcon name="search" :size="17" />
      <SInput v-model="query" placeholder="搜索函数" aria-label="搜索函数" />
    </div>
    <SButton v-if="embedded" :loading="loading" @click="load">刷新</SButton>
  </div>
  <SCard class="table-surface">
    <div class="table-scroll">
      <STable class="functions-table">
        <colgroup>
          <col class="function-name-column" />
          <col />
          <col class="function-action-column" />
        </colgroup>
        <thead>
          <tr>
            <th>函数</th>
            <th>描述</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="fn in filtered" :key="fn.plugin_id + '.' + fn.name">
            <td>
              <div class="function-name mono" :title="fn.plugin_id + '.' + fn.name">
                <span class="function-source">{{ fn.source_label || fn.plugin_id }}.</span>
                <strong>{{ fn.name }}</strong>
              </div>
            </td>
            <td>
              <div class="function-description">{{ fn.description || '—' }}</div>
            </td>
            <td><SButton variant="text" @click="detail = fn">详情</SButton></td>
          </tr>
        </tbody>
      </STable>
    </div>
    <UiEmpty v-if="!filtered.length" />
  </SCard>
  <UiModal
    :open="!!detail"
    :title="detail ? detail.plugin_id + '.' + detail.name : '函数'"
    wide
    @close="detail = null"
  >
    <dl class="detail-grid">
      <dt>描述</dt>
      <dd>{{ detail?.description }}</dd>
    </dl>
    <h3>参数</h3>
    <pre class="json-block">{{ JSON.stringify(detail?.parameters, null, 2) }}</pre>
  </UiModal>
</template>
<style scoped>
.functions-table {
  table-layout: fixed;
  min-width: 640px;
}
.function-name-column {
  width: 34%;
}
.function-action-column {
  width: 76px;
}
.function-name {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.function-source {
  color: var(--muted);
  font-weight: 400;
}
.function-description {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow: hidden;
  white-space: normal;
  overflow-wrap: anywhere;
  line-height: 1.65;
  color: var(--ink);
}
</style>
