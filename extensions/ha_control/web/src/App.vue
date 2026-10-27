<script setup lang="ts">
import {PluginWorkbench} from '@sakubot/ui'
</script>
<template>
  <PluginWorkbench :filters="{ entities: { label: '显示忽略', field: 'policy', value: 'ignore' } }" />
</template>
