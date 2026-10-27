<script setup lang="ts" generic="T extends string | number = string">
import { ref, useAttrs } from 'vue'
defineOptions({ inheritAttrs: false })
const props = defineProps<{ modelValue?: T | null; modelModifiers?: { number?: boolean; trim?: boolean } }>()
const emit = defineEmits<{ 'update:modelValue': [value: T]; input: [event: Event]; change: [event: Event] }>()
const attrs = useAttrs()
const composing = ref(false)
function compositionStart() {
  composing.value = true
}
function compositionEnd(event: CompositionEvent) {
  composing.value = false
  input(event)
}
const element = ref<HTMLInputElement>()
function input(event: Event) {
  if (composing.value) return
  let value: string | number = (event.target as HTMLInputElement).value
  if (props.modelModifiers?.trim) value = value.trim()
  if (props.modelModifiers?.number) {
    const number = parseFloat(value)
    if (!Number.isNaN(number)) value = number
  }
  emit('update:modelValue', value as T)
  emit('input', event)
}
defineExpose({ focus: () => element.value?.focus(), select: () => element.value?.select(), element })
</script>
<template>
  <input
    ref="element"
    v-bind="attrs"
    class="s-input"
    :value="modelValue === undefined ? attrs.value : modelValue"
    @compositionstart="compositionStart"
    @compositionend="compositionEnd"
    @input="input"
    @change="emit('change', $event)"
  />
</template>

<style>
input.s-input {
  appearance: none;
  -webkit-appearance: none;
  display: block;
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  min-height: 40px;
  margin: 0;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #fff;
  color: var(--ink);
  font: inherit;
  font-size: 13px;
  line-height: 1.45;
  box-shadow: 0 1px 2px #30294604;
  outline: none;
  outline-offset: 0;
  caret-color: var(--accent);
  accent-color: var(--accent);
  transition:
    background var(--s-motion),
    border-color var(--s-motion),
    box-shadow var(--s-motion);
}
input.s-input::placeholder {
  color: var(--muted);
  opacity: 0.85;
}
input.s-input:hover:not(:disabled):not(:focus) {
  border-color: #c8c2df;
}
input.s-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: var(--s-ring);
  background: #fff;
}
input.s-input:disabled {
  background: #f3f2f8;
  color: var(--muted);
  cursor: not-allowed;
  box-shadow: none;
  opacity: 1;
  -webkit-text-fill-color: var(--muted);
}
input.s-input[readonly] {
  background: #f8f7fb;
  color: var(--ink);
  box-shadow: none;
}
input.s-input:user-invalid {
  border-color: var(--negative);
}
input.s-input:user-invalid:focus {
  box-shadow: 0 0 0 3px #c67b8718;
}
input.s-input::selection {
  background: #7162db26;
}
input.s-input[type='number'] {
  appearance: textfield;
  -moz-appearance: textfield;
  font-variant-numeric: tabular-nums;
}
input.s-input::-webkit-inner-spin-button,
input.s-input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
input.s-input:is([type='date'], [type='time'], [type='datetime-local']) {
  font-variant-numeric: tabular-nums;
  color-scheme: light;
}
input.s-input::-webkit-calendar-picker-indicator {
  cursor: pointer;
  opacity: 0.55;
  padding: 3px;
  border-radius: 5px;
  transition:
    opacity var(--s-motion),
    background var(--s-motion);
}
input.s-input::-webkit-calendar-picker-indicator:hover {
  opacity: 0.9;
  background: #7162db12;
}
input.s-input::-webkit-date-and-time-value {
  text-align: left;
  min-height: 19px;
}
input.s-input[type='file'] {
  padding: 6px;
  color: var(--muted);
  cursor: pointer;
  line-height: 28px;
}
input.s-input::file-selector-button {
  border: 1px solid #e0dcef;
  border-radius: 7px;
  background: #f3f0fc;
  color: var(--accent);
  font: inherit;
  font-weight: 550;
  padding: 5px 12px;
  margin-right: 12px;
  cursor: pointer;
  transition:
    background var(--s-motion),
    border-color var(--s-motion);
}
input.s-input::file-selector-button:hover {
  background: #ebe5fb;
  border-color: #c8bdec;
}
input.s-input[type='file']:disabled,
input.s-input[type='file']:disabled::file-selector-button {
  cursor: not-allowed;
}
input.s-input:-webkit-autofill {
  -webkit-text-fill-color: var(--ink);
  -webkit-box-shadow: 0 0 0 1000px #fff inset;
}
input.s-input:-webkit-autofill:focus {
  -webkit-box-shadow:
    0 0 0 1000px #fff inset,
    var(--s-ring);
}
.s-input {
  transition:
    background var(--s-motion),
    border-color var(--s-motion),
    box-shadow var(--s-motion);
}
.s-input:focus {
  outline: 0;
  border-color: var(--accent);
  box-shadow: var(--s-ring);
  background: #fff;
}
.s-input:disabled {
  background: #f5f5f9;
  color: var(--muted);
  cursor: not-allowed;
}

.search-field input.s-input {
  padding-left: 37px;
}
</style>
