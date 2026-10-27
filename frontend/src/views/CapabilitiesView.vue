<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import FunctionsView from './FunctionsView.vue'
import SkillsView from './SkillsView.vue'
const route = useRoute(),
  router = useRouter()
const tab = computed({
  get: () => (route.query.tab === 'skills' ? 'skills' : 'functions'),
  set: (value) => {
    void router.push({ path: '/functions', query: { tab: value } })
  },
})
const tabs = [
  { value: 'functions', label: '函数' },
  { value: 'skills', label: '技能' },
]
</script>
<template>
  <div>
    <SPageHeader title="能力" />
    <STabs v-model="tab" :items="tabs">
      <Transition name="s-page" mode="out-in">
        <div :key="tab">
          <FunctionsView v-if="tab === 'functions'" embedded />
          <SkillsView v-else />
        </div>
      </Transition>
    </STabs>
  </div>
</template>
