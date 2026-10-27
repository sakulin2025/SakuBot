<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import EventsView from './EventsView.vue'
import TraceView from './TraceView.vue'
import RecordsView from './RecordsView.vue'
const route = useRoute(),
  router = useRouter()
const tabs = [
  { value: 'events', label: '事件中心' },
  { value: 'logs', label: '追踪日志' },
  { value: 'tool-calls', label: '工具调用' },
  { value: 'runs', label: '运行记录' },
  { value: 'deliveries', label: '消息投递' },
]
const tab = computed({
  get: () => (tabs.some((t) => t.value === route.query.tab) ? String(route.query.tab) : 'events'),
  set: (value) => {
    void router.push({ path: '/activity', query: { tab: value } })
  },
})
</script>
<template>
  <div>
    <SPageHeader title="活动中心" />
    <STabs v-model="tab" :items="tabs">
      <Transition name="s-page" mode="out-in">
        <div :key="tab" class="workspace-body">
          <EventsView v-if="tab === 'events'" embedded />
          <TraceView v-else-if="tab === 'logs' || tab === 'tool-calls'" :kind="tab" embedded />
          <RecordsView v-else :kind="tab" embedded />
        </div>
      </Transition>
    </STabs>
  </div>
</template>
