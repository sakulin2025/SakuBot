<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PluginsView from './PluginsView.vue'
import SkillsView from './SkillsView.vue'
import FunctionsView from './FunctionsView.vue'
const route = useRoute(), router = useRouter()
const tabs = [{value:'plugins',label:'插件'}, {value:'skills',label:'技能'}, {value:'functions',label:'函数'}]
const tab = computed({
  get: () => tabs.some(item => item.value === route.query.tab) ? String(route.query.tab) : 'plugins',
  set: value => { void router.push({path:'/plugins',query:{...route.query,tab:value}}) },
})
</script>
<template>
  <SPageHeader title="插件与技能" />
  <STabs v-model="tab" :items="tabs">
    <Transition name="s-page" mode="out-in">
      <div :key="tab">
        <PluginsView v-if="tab === 'plugins'" />
        <SkillsView v-else-if="tab === 'skills'" />
        <FunctionsView v-else embedded />
      </div>
    </Transition>
  </STabs>
</template>
