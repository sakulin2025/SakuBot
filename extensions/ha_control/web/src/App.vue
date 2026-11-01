<script setup lang="ts">
import {PluginWorkbench} from '@sakubot/ui'

function hiddenEntity(row: { area?: string }, data: { rooms?: { area: string; enabled: boolean }[] }) {
  return !row.area || row.area === '__unassigned__' || !(data.rooms || []).some(room => room.area === row.area && room.enabled === true)
}
</script>
<template>
  <PluginWorkbench :filters="{ entities: { label: '显示忽略', field: 'policy', value: 'ignore', exclude: hiddenEntity } }" />
</template>
