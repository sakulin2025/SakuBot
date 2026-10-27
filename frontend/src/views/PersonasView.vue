<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, reactive } from 'vue'
import { useRoute } from 'vue-router'
import { api, formatDate, parseJson } from '../api'
import { useConsole } from '../stores/console'
import UiIcon from '../components/UiIcon.vue'
import UiBadge from '../components/UiBadge.vue'
import UiModal from '../components/UiModal.vue'
import UiEmpty from '../components/UiEmpty.vue'
import type { Persona } from '../types'
defineProps<{ embedded?: boolean }>()
const store = useConsole()
const query = ref('')
const editing = ref(false)
const deleting = ref<Persona | null>(null)
const busy = ref(false)
const form = reactive({ id: '', name: '', prompt: '', visible_plugins: null as string[] | null })
const pluginChoices = computed(() => [
  ...store.plugins.filter((p) => !p.required).map((p) => ({ id: p.name, name: p.label })),
  ...(form.visible_plugins || [])
    .filter((id) => !store.plugins.some((p) => p.name === id))
    .map((id) => ({ id, name: id })),
])
function togglePlugin(id: string, event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  const selected =
    form.visible_plugins === null ? pluginChoices.value.map((p) => p.id) : [...form.visible_plugins]
  form.visible_plugins = checked ? [...new Set([...selected, id])] : selected.filter((item) => item !== id)
}
function toggleAll(event: Event) {
  form.visible_plugins = (event.target as HTMLInputElement).checked ? null : []
}
const items = computed(() => store.personas.filter((p) => (p.name + p.prompt).includes(query.value)))
function edit(p?: Persona) {
  Object.assign(form, {
    id: p?.id || '',
    name: p?.name || '',
    prompt: p?.prompt || '',
    visible_plugins: p?.visible_plugins == null ? null : [...p.visible_plugins],
  })
  editing.value = true
}
async function save() {
  busy.value = true
  try {
    await api('personas', { body: form })
    await store.refresh()
    editing.value = false
    store.toast('已保存')
  } catch {
    store.toast('保存失败', true)
  } finally {
    busy.value = false
  }
}
async function remove() {
  if (!deleting.value) return
  busy.value = true
  try {
    await api('personas/' + encodeURIComponent(deleting.value.id), { method: 'DELETE' })
    await store.refresh()
    deleting.value = null
    store.toast('已删除')
  } catch {
    store.toast('删除失败', true)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <SPageHeader title="人格">
    <SButton class="button primary" @click="edit()">
      <UiIcon name="plus" :size="17" />
      新增人格
    </SButton>
  </SPageHeader>
  <div class="page-toolbar">
    <div class="search-field">
      <UiIcon name="search" :size="17" />
      <SInput v-model="query" placeholder="搜索人格" aria-label="搜索人格" />
    </div>
    <RouterLink v-if="!embedded" to="/agents" class="button">Agent 管理</RouterLink>
  </div>
  <div class="plugin-grid">
    <section v-for="persona in items" :key="persona.id" class="plugin-card">
      <div class="plugin-card-top">
        <span class="plugin-icon"><UiIcon name="persona" :size="26" /></span>
        <span
          v-if="store.agents.some((a) => a.id === 'main' && a.effective_persona_id === persona.id)"
          class="badge positive"
        >
          主 Agent
        </span>
      </div>
      <h2>{{ persona.name }}</h2>
      <p class="persona-preview">{{ persona.prompt }}</p>
      <div class="plugin-card-bottom">
        <time>{{ formatDate(persona.updated) }}</time>
        <SButton class="button compact" @click="edit(persona)">编辑</SButton>
        <SButton
          class="button compact danger-soft"
          :disabled="
            persona.id === store.agentDefaults.persona_id ||
            store.agents.some((a) => a.effective_persona_id === persona.id)
          "
          @click="deleting = persona"
        >
          删除
        </SButton>
      </div>
    </section>
  </div>
  <UiEmpty v-if="!items.length" />
  <UiModal :open="editing" :title="form.id ? '编辑人格' : '新增人格'" wide @close="editing = false">
    <form id="persona-form" class="form-body" @submit.prevent="save">
      <div class="field">
        <label for="persona-name">名称</label>
        <SInput id="persona-name" v-model="form.name" required maxlength="100" />
      </div>
      <div class="field">
        <label for="persona-prompt">系统提示词</label>
        <STextarea
          id="persona-prompt"
          v-model="form.prompt"
          class="persona-editor"
          required
          maxlength="100000"
          spellcheck="false"
        ></STextarea>
        <span class="character-count">{{ form.prompt.length }}</span>
      </div>
      <div class="field">
        <div class="persona-plugin-heading">
          <label>可见插件</label>
          <label class="check-label">
            <SCheckbox :checked="form.visible_plugins === null" @change="toggleAll" />
            全部插件
          </label>
        </div>
        <div class="persona-plugin-list">
          <label v-for="plugin in pluginChoices" :key="plugin.id" class="persona-plugin-option">
            <span>
              <strong>{{ plugin.name }}</strong>
              <span class="mono">{{ plugin.id }}</span>
            </span>
            <SCheckbox
              :checked="form.visible_plugins === null || form.visible_plugins.includes(plugin.id)"
              @change="togglePlugin(plugin.id, $event)"
            />
          </label>
        </div>
      </div>
    </form>
    <template #footer>
      <SButton class="button" @click="editing = false">取消</SButton>
      <SButton class="button primary" form="persona-form" :disabled="busy">保存</SButton>
    </template>
  </UiModal>
  <UiModal :open="!!deleting" title="删除人格" @close="deleting = null">
    <strong>{{ deleting?.name }}</strong>
    <template #footer>
      <SButton class="button" @click="deleting = null">取消</SButton>
      <SButton class="button danger-soft" :disabled="busy" @click="remove">删除</SButton>
    </template>
  </UiModal>
</template>
