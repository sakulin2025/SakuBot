<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api'
import { useConsole } from '../stores/console'
import UiIcon from '../components/UiIcon.vue'
import UiModal from '../components/UiModal.vue'
import UiEmpty from '../components/UiEmpty.vue'
interface Skill {
  id: string
  name: string
  description: string
  source: string
  plugin_id: string
  version: string
}
interface SkillDetail extends Skill {
  content: string
  body: string
  files: string[]
}
interface SkillFile {
  content: string
  binary: boolean
  has_more: boolean
  offset: number
  next_offset: number
  total_lines: number
}
const store = useConsole()
const rows = ref<Skill[]>([]),
  query = ref(''),
  loading = ref(false),
  busy = ref(false),
  error = ref('')
const invalid = ref<{ id: string; error: string }[]>([])
const detail = ref<SkillDetail | null>(null),
  tab = ref('body'),
  file = ref(''),
  page = ref<SkillFile | null>(null),
  history = ref<number[]>([])
const filtered = computed(() =>
  rows.value.filter((row) =>
    (row.id + row.name + row.description).toLowerCase().includes(query.value.trim().toLowerCase()),
  ),
)
async function load() {
  loading.value = true
  try {
    const data = await api<{ items: Skill[]; errors: { id: string; error: string }[] }>('skills')
    rows.value = data.items
    invalid.value = data.errors
  } catch {
    store.toast('加载失败', true)
  } finally {
    loading.value = false
  }
}
async function inspect(row: Skill) {
  busy.value = true
  error.value = ''
  try {
    detail.value = await api<SkillDetail>('skills/' + encodeURIComponent(row.id))
    tab.value = 'body'
    file.value = ''
    page.value = null
    history.value = []
  } catch {
    store.toast('加载失败', true)
  } finally {
    busy.value = false
  }
}
async function readFile(path: string, offset = 0) {
  if (!detail.value) return
  busy.value = true
  error.value = ''
  try {
    const result = await api<SkillFile>(
      'skills/' +
        encodeURIComponent(detail.value.id) +
        '/file?' +
        new URLSearchParams({ path, offset: String(offset) }),
    )
    file.value = path
    page.value = result
  } catch {
    error.value = '读取失败'
  } finally {
    busy.value = false
  }
}
function openFile(path: string) {
  history.value = []
  void readFile(path)
}
function clearFile() {
  file.value = ''
  page.value = null
}
function next() {
  if (page.value?.has_more) {
    history.value.push(page.value.offset)
    void readFile(file.value, page.value.next_offset)
  }
}
function previous() {
  const offset = history.value.pop()
  if (offset !== undefined) void readFile(file.value, offset)
}
onMounted(load)
watch(() => store.status?.registry_revision, load)
</script>
<template>
  <div class="page-toolbar">
    <div class="search-field">
      <UiIcon name="search" :size="17" />
      <SInput v-model="query" placeholder="搜索技能" aria-label="搜索技能" />
    </div>
    <SButton :loading="loading" @click="load">刷新</SButton>
  </div>
  <div v-if="filtered.length" class="skill-grid">
    <button v-for="row in filtered" :key="row.id" type="button" class="skill-card" :disabled="busy" @click="inspect(row)">
      <div class="skill-card-top"><span class="skill-icon"><UiIcon name="memory" :size="21" /></span><span class="skill-source-chip">{{ row.source }}</span></div>
      <strong class="skill-card-name">{{ row.name }}</strong>
      <span class="skill-card-id mono">{{ row.id }}</span>
      <span class="skill-description">{{ row.description || '—' }}</span>
      <span class="skill-card-action"><UiIcon name="right" :size="15" /></span>
    </button>
  </div>
  <UiEmpty v-else label="暂无技能" icon="memory" />
  <div v-for="item in invalid" :key="item.id" class="form-error">{{ item.id }} · {{ item.error }}</div>
  <UiModal :open="!!detail" :title="detail?.id || '技能'" wide @close="detail = null">
    <STabs
      v-model="tab"
      :items="[
        { value: 'body', label: '正文' },
        { value: 'files', label: '附属文件', count: detail?.files.length || 0 },
      ]"
    />
    <pre v-if="tab === 'body'" class="skill-body">{{ detail?.content }}</pre>
    <template v-else>
      <div v-if="!file" class="skill-file-list">
        <SButton
          v-for="path in detail?.files"
          :key="path"
          variant="text"
          icon="file"
          :disabled="busy"
          @click="openFile(path)"
        >
          {{ path }}
        </SButton>
        <UiEmpty v-if="!detail?.files.length" label="暂无文件" />
      </div>
      <template v-else>
        <div class="page-toolbar">
          <SButton icon="left" @click="clearFile">文件列表</SButton>
          <span class="mono">{{ file }}</span>
        </div>
        <span v-if="page?.binary" class="badge neutral">二进制</span>
        <pre v-else class="skill-body">{{ page?.content }}</pre>
        <div class="skill-file-pager">
          <SButton :disabled="!history.length || busy" @click="previous">上一页</SButton>
          <SButton :disabled="!page?.has_more || busy" @click="next">下一页</SButton>
        </div>
      </template>
    </template>
    <span v-if="error" class="form-error">{{ error }}</span>
  </UiModal>
</template>
<style scoped>
.skill-grid { display:grid;grid-template-columns:repeat(auto-fill,minmax(245px,1fr));gap:16px; }
.skill-card { position:relative;display:flex;flex-direction:column;align-items:flex-start;gap:9px;min-width:0;min-height:180px;padding:20px;text-align:left;border:1px solid var(--border);border-radius:15px;background:#fff;color:var(--ink);font:inherit;cursor:pointer;transition:transform .2s,border-color .2s,box-shadow .2s; }
.skill-card:hover:not(:disabled) { transform:translateY(-3px);border-color:#d5cdf1;box-shadow:0 10px 26px #493b8610; }
.skill-card:focus-visible { outline:0;box-shadow:var(--s-ring); }
.skill-card-top { display:flex;align-items:center;justify-content:space-between;width:100%;margin-bottom:3px; }
.skill-icon { display:grid;place-items:center;width:40px;height:40px;border-radius:12px;background:#f0edfc;color:var(--accent); }
.skill-source-chip { max-width:60%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding:4px 8px;border-radius:7px;background:var(--canvas);color:var(--muted);font-size:11px; }
.skill-card-name { font-size:14px;overflow-wrap:anywhere; }
.skill-card-id { font-size:11px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;max-width:100%;white-space:nowrap; }
.skill-card-action { position:absolute;right:18px;bottom:16px;color:var(--accent); }
.skill-card .skill-description { padding-right:18px;color:var(--muted);font-size:12px; }

.skills-table {
  table-layout: fixed;
  min-width: 640px;
}
.skill-name-column {
  width: 34%;
}
.skill-actions-column {
  width: 76px;
}
.skill-id {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.skill-source {
  color: var(--muted);
  font-weight: 400;
}
.skill-description {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow: hidden;
  white-space: normal;
  overflow-wrap: anywhere;
  line-height: 1.65;
}
.skill-body {
  font: 12px/1.85 var(--mono);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 55vh;
  overflow: auto;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: #faf9fd;
  margin: 0;
}
.skill-file-list {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
}
.skill-file-pager {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 14px;
}
</style>
