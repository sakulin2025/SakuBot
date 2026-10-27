<script setup lang="ts" generic="T extends boolean | string[] = boolean">
import { computed, onMounted, ref, useAttrs, watch } from 'vue'
defineOptions({ inheritAttrs: false })
const props = defineProps<{ modelValue?: T; value?: string; checked?: boolean; indeterminate?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: T]; change: [event: Event] }>()
const attrs = useAttrs()
const element = ref<HTMLInputElement>()
const checked = computed(() =>
  Array.isArray(props.modelValue)
    ? props.modelValue.includes(props.value || '')
    : (props.modelValue ?? props.checked ?? false),
)
function sync() {
  if (element.value) element.value.indeterminate = !!props.indeterminate
}
onMounted(sync)
watch(() => props.indeterminate, sync)
function change(event: Event) {
  const value = (event.target as HTMLInputElement).checked
  const selection = Array.isArray(props.modelValue)
    ? value
      ? [...props.modelValue, props.value || '']
      : props.modelValue.filter((item) => item !== props.value)
    : value
  emit('update:modelValue', selection as T)
  emit('change', event)
}
defineExpose({ focus: () => element.value?.focus(), element })
</script>
<template>
  <input
    ref="element"
    v-bind="attrs"
    class="s-checkbox"
    type="checkbox"
    :value="value"
    :checked="checked"
    @change="change"
  />
</template>

<style>
.checkbox-field {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #858d9e;
  font-size: 11px;
  cursor: pointer;
  min-height: 24px;
}
input[type='checkbox'] {
  accent-color: var(--accent);
  width: 14px;
  height: 14px;
}
.s-checkbox {
  appearance: none !important;
  -webkit-appearance: none !important;
  display: inline-block;
  position: relative;
  width: 16px !important;
  height: 16px !important;
  min-width: 16px !important;
  min-height: 16px !important;
  margin: 0;
  padding: 0 !important;
  border: 1.5px solid #d6d2e5 !important;
  border-radius: 5px !important;
  background: #fff;
  vertical-align: middle;
  cursor: pointer;
  transition:
    background var(--s-motion),
    border-color var(--s-motion),
    box-shadow var(--s-motion);
}
.s-checkbox:checked,
.s-checkbox:indeterminate {
  background: var(--accent) !important;
  border-color: var(--accent) !important;
}
.s-checkbox:checked::after {
  content: '';
  position: absolute;
  left: 4px;
  top: 1px;
  width: 4px;
  height: 8px;
  border: solid #fff;
  border-width: 0 1.8px 1.8px 0;
  transform: rotate(45deg);
  animation: s-check-in 0.16s ease;
}
.s-checkbox:indeterminate::after {
  content: '';
  position: absolute;
  left: 3px;
  top: 6px;
  width: 7px;
  height: 2px;
  background: #fff;
  border-radius: 2px;
}
.s-checkbox:focus-visible {
  outline: 0;
  box-shadow: var(--s-ring);
}
.s-checkbox:disabled {
  appearance: none !important;
  -webkit-appearance: none !important;
  opacity: 0.55;
  cursor: not-allowed;
}
@keyframes s-check-in {
  from {
    opacity: 0;
    transform: rotate(45deg) scale(0.5);
  }
  to {
    opacity: 1;
    transform: rotate(45deg) scale(1);
  }
}
</style>
