<script setup lang="ts">
import SSpinner from './SSpinner.vue'
const props = defineProps<{ modelValue?: boolean; disabled?: boolean; loading?: boolean; label?: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; change: [value: boolean] }>()
function toggle() {
  if (props.disabled || props.loading) return
  emit('update:modelValue', !props.modelValue)
  emit('change', !props.modelValue)
}
</script>
<template>
  <button
    type="button"
    role="switch"
    class="s-switch"
    :class="{ 'is-checked': modelValue, 'is-loading': loading }"
    :aria-checked="!!modelValue"
    :aria-label="label"
    :disabled="disabled || loading"
    @click="toggle"
  >
    <span class="s-switch-thumb"><SSpinner v-if="loading" /></span>
  </button>
</template>

<style>
.s-switch:focus-visible {
  outline: 0;
  box-shadow: var(--s-ring);
}
.s-switch {
  appearance: none;
  -webkit-appearance: none;
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  position: relative;
  width: 38px;
  height: 22px;
  padding: 3px;
  border: 0;
  border-radius: 99px;
  background: #d6d8e3;
  vertical-align: middle;
  transition:
    background var(--s-motion),
    box-shadow var(--s-motion);
  cursor: pointer;
}
.s-switch:disabled {
  appearance: none;
  -webkit-appearance: none;
  opacity: 0.55;
  cursor: not-allowed;
  background: #d6d8e3;
}
.s-switch.is-checked:disabled {
  background: var(--accent);
}
.s-switch:disabled .s-switch-thumb {
  background: #fff;
}
.s-switch.is-checked {
  background: var(--accent);
}
.s-switch-thumb {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  background: #fff;
  border-radius: 50%;
  box-shadow: 0 1px 3px #23223f26;
  transition: transform var(--s-spring);
}
.s-switch.is-checked .s-switch-thumb {
  transform: translateX(16px);
}
.s-switch:active:not(:disabled) .s-switch-thumb {
  width: 19px;
}
.s-switch:active.is-checked:not(:disabled) .s-switch-thumb {
  transform: translateX(13px);
}
.s-switch-thumb .s-spinner {
  width: 10px;
  height: 10px;
  border-width: 1.5px;
}

.switch {
  display: flex;
  position: relative;
  width: 33px;
  height: 19px;
  cursor: pointer;
}
.switch input {
  position: absolute;
  opacity: 0;
  width: 100%;
  height: 100%;
  margin: 0;
}
.switch > span {
  background: #dde1e9;
  border-radius: 20px;
  position: absolute;
  inset: 0;
  pointer-events: none;
  transition: background 0.2s;
}
.switch > span:after {
  content: '';
  position: absolute;
  left: 3px;
  top: 3px;
  width: 13px;
  height: 13px;
  background: #fff;
  border-radius: 50%;
  box-shadow: 0 1px 3px #0001;
  transition: transform 0.2s;
}
.switch input:checked + span {
  background: var(--accent);
}
.switch input:checked + span:after {
  transform: translateX(14px);
}
.switch input:disabled + span {
  opacity: 0.5;
}
.switch input:focus-visible + span {
  outline: 3px solid #dedfff;
  outline-offset: 2px;
}
</style>
