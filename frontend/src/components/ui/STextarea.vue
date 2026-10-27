<script setup lang="ts">
import { nextTick, onMounted, ref, useAttrs, watch } from 'vue'
defineOptions({ inheritAttrs: false })
const props = defineProps<{ modelValue?: string; autosize?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string]; input: [event: Event] }>()
const element = ref<HTMLTextAreaElement>()
const attrs = useAttrs()
const composing = ref(false)
function compositionStart() {
  composing.value = true
}
function compositionEnd(event: CompositionEvent) {
  composing.value = false
  input(event)
}
function resize() {
  if (props.autosize && element.value) {
    element.value.style.height = 'auto'
    element.value.style.height = element.value.scrollHeight + 'px'
  }
}
watch(
  () => props.modelValue,
  () => nextTick(resize),
)
onMounted(resize)
function input(event: Event) {
  if (composing.value) return
  emit('update:modelValue', (event.target as HTMLTextAreaElement).value)
  emit('input', event)
  resize()
}
defineExpose({ focus: () => element.value?.focus(), element })
</script>
<template>
  <textarea
    ref="element"
    v-bind="attrs"
    class="s-input s-textarea"
    :value="modelValue === undefined ? String(attrs.value ?? '') : modelValue"
    @compositionstart="compositionStart"
    @compositionend="compositionEnd"
    @input="input"
  />
</template>

<style>
textarea.s-input {
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
textarea.s-input::placeholder {
  color: var(--muted);
  opacity: 0.85;
}
textarea.s-input:hover:not(:disabled):not(:focus) {
  border-color: #c8c2df;
}
textarea.s-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: var(--s-ring);
  background: #fff;
}
textarea.s-input:disabled {
  background: #f3f2f8;
  color: var(--muted);
  cursor: not-allowed;
  box-shadow: none;
  opacity: 1;
  -webkit-text-fill-color: var(--muted);
}
textarea.s-input[readonly] {
  background: #f8f7fb;
  color: var(--ink);
  box-shadow: none;
}
textarea.s-input:user-invalid {
  border-color: var(--negative);
}
textarea.s-input:user-invalid:focus {
  box-shadow: 0 0 0 3px #c67b8718;
}
textarea.s-input::selection {
  background: #7162db26;
}
textarea.s-textarea {
  min-height: 104px;
  resize: vertical;
  line-height: 1.75;
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
.s-textarea {
  resize: vertical;
  min-height: 88px;
}
</style>
