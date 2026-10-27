<script setup lang="ts">
import UiIcon from './UiIcon.vue'
withDefaults(defineProps<{ label?: string; icon?: string }>(), { label: '暂无记录', icon: 'empty' })
</script>
<template>
  <div class="empty-state">
    <div class="empty-icon"><UiIcon :name="icon" :size="26" /></div>
    <span>{{ label }}</span>
    <slot />
  </div>
</template>

<style>
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 13px;
  min-height: 235px;
  padding: 35px;
  color: #aab1c0;
  font-size: 11px;
}
.empty-icon {
  width: 52px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f7f8fb;
  border: 1px solid #eff1f6;
  border-radius: 14px;
  color: #bec4d0;
}
</style>
