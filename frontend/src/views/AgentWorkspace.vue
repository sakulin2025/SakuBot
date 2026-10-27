<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AgentsView from './AgentsView.vue'
import PersonasView from './PersonasView.vue'
const route = useRoute(), router = useRouter()
const tab = computed({
  get: () => route.query.tab === 'personas' ? 'personas' : 'agents',
  set: value => { void router.push({ path: '/agents', query: { ...route.query, tab: value } }) },
})
const tabs = [{value:'personas',label:'人格'}, {value:'agents',label:'Agent 管理'}]
</script>
<template>
  <SPageHeader title="Agent 管理" />
  <STabs v-model="tab" :items="tabs">
    <Transition name="s-page" mode="out-in">
      <div :key="tab">
        <PersonasView v-if="tab === 'personas'" embedded />
        <AgentsView v-else embedded />
      </div>
    </Transition>
  </STabs>
</template>
