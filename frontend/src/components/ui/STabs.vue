<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
export interface TabItem {
  value: string
  label: string
  count?: number
  disabled?: boolean
}
const props = defineProps<{ modelValue: string; items: TabItem[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: string]; change: [value: string] }>()
const uid = useId()
const nav = ref<HTMLElement>()
const indicator = ref({ width: '0px', transform: 'translateX(0)' })
let observer: ResizeObserver | undefined
function measure() {
  const active = nav.value?.querySelector<HTMLElement>('[aria-selected="true"]')
  if (active)
    indicator.value = { width: active.offsetWidth + 'px', transform: `translateX(${active.offsetLeft}px)` }
}
function select(value: string) {
  if (value === props.modelValue) return
  emit('update:modelValue', value)
  emit('change', value)
}
function keydown(event: KeyboardEvent) {
  const tabs = props.items.filter((item) => !item.disabled)
  const index = tabs.findIndex((item) => item.value === props.modelValue)
  let next = index
  if (event.key === 'ArrowRight') next = (index + 1) % tabs.length
  else if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length
  else if (event.key === 'Home') next = 0
  else if (event.key === 'End') next = tabs.length - 1
  else return
  event.preventDefault()
  const tab = tabs[next]
  if (tab) {
    select(tab.value)
    nextTick(() => document.getElementById(uid + '-' + tab.value)?.focus())
  }
}
watch(
  () => [props.modelValue, props.items],
  () => nextTick(measure),
  { deep: true },
)
onMounted(() => {
  measure()
  observer = new ResizeObserver(measure)
  if (nav.value) observer.observe(nav.value)
})
onBeforeUnmount(() => observer?.disconnect())
</script>
<template>
  <div class="s-tabs">
    <div ref="nav" class="s-tab-nav" role="tablist" @keydown="keydown">
      <button
        v-for="item in items"
        :id="uid + '-' + item.value"
        :key="item.value"
        type="button"
        class="s-tab"
        role="tab"
        :aria-selected="modelValue === item.value"
        :aria-controls="uid + '-panel'"
        :tabindex="modelValue === item.value ? 0 : -1"
        :disabled="item.disabled"
        @click="select(item.value)"
      >
        {{ item.label }}
        <span v-if="item.count !== undefined" class="s-tab-count">{{ item.count }}</span>
      </button>
      <span class="s-tab-indicator" :style="indicator" />
    </div>
    <div
      v-if="$slots.default"
      :id="uid + '-panel'"
      role="tabpanel"
      :aria-labelledby="uid + '-' + modelValue"
      class="s-tab-panel"
    >
      <slot :active="modelValue" />
    </div>
  </div>
</template>

<style>
.s-tab:focus-visible {
  outline: 0;
  box-shadow: var(--s-ring);
}
.s-tabs {
  min-width: 0;
}
.s-tab-nav {
  position: relative;
  display: flex;
  gap: 6px;
  align-items: center;
  max-width: 100%;
  overflow-x: auto;
  scrollbar-width: none;
  border-bottom: 1px solid var(--border);
  margin-bottom: 22px;
  padding: 0 2px;
}
.s-tab {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-shrink: 0;
  padding: 13px 18px 15px;
  background: transparent;
  border: 0;
  color: #9294a7;
  font-weight: 550;
  border-radius: 8px 8px 0 0;
  transition:
    color var(--s-motion),
    background var(--s-motion);
  white-space: nowrap;
}
.s-tab:hover {
  color: var(--accent);
  background: #7162eb06;
}
.s-tab[aria-selected='true'] {
  color: var(--accent);
}
.s-tab-count {
  font-size: 11px;
  line-height: 18px;
  min-width: 20px;
  padding: 0 6px;
  background: #edeef5;
  border-radius: 6px;
  color: #9294a7;
  transition:
    background var(--s-motion),
    color var(--s-motion);
}
.s-tab[aria-selected='true'] .s-tab-count {
  background: #7162eb12;
  color: var(--accent);
}
.s-tab-indicator {
  position: absolute;
  left: 0;
  bottom: 0;
  height: 3px;
  border-radius: 4px 4px 0 0;
  background: var(--accent);
  transition:
    width var(--s-spring),
    transform var(--s-spring);
  pointer-events: none;
}
.s-tab-panel {
  min-width: 0;
}
.s-table {
  width: 100%;
  border-spacing: 0;
}
.s-table tbody tr {
  transition: background var(--s-motion);
}
.s-table-empty {
  padding: 50px 20px !important;
  text-align: center;
  color: var(--muted);
}
.s-page-enter-active,
.s-page-leave-active {
  transition:
    opacity 0.16s ease,
    transform 0.16s ease;
}
.s-page-enter-from {
  opacity: 0;
  transform: translateY(7px);
}
.s-page-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
@media (max-width: 900px) {
  .s-tab {
    padding: 12px 13px;
  }
}
</style>
