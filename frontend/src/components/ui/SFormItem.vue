<script setup lang="ts">
import { computed, inject } from 'vue'
import { formKey } from './form'
const props = defineProps<{
  label?: string
  for?: string
  prop?: string
  error?: string
  required?: boolean
}>()
const form = inject(formKey, undefined)
const error = computed(() => props.error || (props.prop ? form?.errors[props.prop] : '') || '')
</script>
<template>
  <div class="field s-form-item" :class="{ 'has-error': !!error }">
    <label v-if="label || $slots.label" :for="props.for">
      <slot name="label">{{ label }}</slot>
      <span v-if="required" class="s-required">*</span>
    </label>
    <slot />
    <Transition name="s-error">
      <span v-if="error" class="form-error" role="alert">{{ error }}</span>
    </Transition>
  </div>
</template>

<style>
.field {
  display: flex;
  flex-direction: column;
  gap: 9px;
  min-width: 0;
  position: relative;
}
.field > label {
  font-size: 11px;
  font-weight: 550;
  color: #737b8f;
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 17px;
}
.field-state {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  color: #9aaca1;
  font-size: 9px;
  font-weight: 400;
}
.s-form-item {
  position: relative;
}
.s-form-item.has-error .s-input,
.s-form-item.has-error .s-select {
  border-color: var(--negative);
}
.s-required {
  color: var(--negative);
  margin-left: 4px;
}
.s-error-enter-active,
.s-error-leave-active {
  transition:
    opacity 0.16s ease,
    transform 0.16s ease;
}
.s-error-enter-from,
.s-error-leave-to {
  opacity: 0;
  transform: translateY(-3px);
}

.form-error {
  color: #c99099;
  font-size: 11px;
  margin-top: -14px;
}
</style>
