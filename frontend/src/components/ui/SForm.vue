<script setup lang="ts">
import { provide, reactive, ref } from 'vue'
import { formKey, type FormRule } from './form'
const props = defineProps<{
  model?: Record<string, unknown>
  rules?: Record<string, FormRule[]>
  disabled?: boolean
}>()
const emit = defineEmits<{ submit: [event: Event] }>()
const element = ref<HTMLFormElement>()
const errors = reactive<Record<string, string>>({})
function validate() {
  for (const key of Object.keys(errors)) delete errors[key]
  for (const [key, rules] of Object.entries(props.rules || {})) {
    const value = props.model?.[key]
    for (const rule of rules) {
      if (
        (rule.required && (value === undefined || value === null || value === '')) ||
        (rule.min !== undefined && String(value ?? '').length < rule.min) ||
        (rule.validate && !rule.validate(value))
      ) {
        errors[key] = rule.message
        break
      }
    }
  }
  return Object.keys(errors).length === 0 && !!element.value?.reportValidity()
}
provide(formKey, { errors, disabled: () => !!props.disabled })
function submit(event: Event) {
  event.preventDefault()
  if (validate()) emit('submit', event)
}
defineExpose({
  validate,
  resetValidation: () => {
    for (const key of Object.keys(errors)) delete errors[key]
  },
  element,
})
</script>
<template>
  <form ref="element" class="s-form" @submit="submit">
    <fieldset :disabled="disabled"><slot /></fieldset>
  </form>
</template>

<style>
.s-form > fieldset {
  border: 0;
  margin: 0;
  padding: 0;
  min-width: 0;
  display: contents;
}
</style>
