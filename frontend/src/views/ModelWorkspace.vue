<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useConsole } from '../stores/console'
import ModelsView from './ModelsView.vue'
import ProvidersView from './ProvidersView.vue'
const store = useConsole()
const route = useRoute(),
  router = useRouter()
const tab = computed({
  get: () => (route.query.tab === 'providers' ? 'providers' : 'models'),
  set: (value) => {
    void router.push({ path: '/model', query: { tab: value } })
  },
})
const tabs = computed(() => [
  { value: 'models', label: '模型', count: store.config?.models.length || 0 },
  { value: 'providers', label: '供应商', count: store.config?.providers.length || 0 },
])
</script>
<template>
  <div>
    <SPageHeader title="模型" />
    <STabs v-model="tab" :items="tabs">
      <Transition name="s-page" mode="out-in">
        <div :key="tab" class="workspace-body">
          <ModelsView v-if="tab === 'models'" embedded />
          <ProvidersView v-else embedded />
        </div>
      </Transition>
    </STabs>
  </div>
</template>
