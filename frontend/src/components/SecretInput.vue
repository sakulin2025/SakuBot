<script setup lang="ts">
import { ref } from 'vue'
import UiIcon from './UiIcon.vue'
defineOptions({ inheritAttrs: false })
defineProps<{ modelValue: string; id: string; required?: boolean }>()
defineEmits<{ 'update:modelValue': [value: string] }>()
const reveal = ref(false)
</script>
<template>
  <div class="secret-input">
    <SInput
      v-bind="$attrs"
      :id="id"
      :type="reveal ? 'text' : 'password'"
      :value="modelValue"
      :required="required"
      autocomplete="new-password"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
    <SButton
      class="icon-button"
      type="button"
      :aria-label="reveal ? '隐藏' : '显示'"
      @click="reveal = !reveal"
    >
      <UiIcon :name="reveal ? 'hidden' : 'eye'" :size="17" />
    </SButton>
  </div>
</template>

<style>
.secret-input {
  display: flex;
  align-items: center;
  position: relative;
}
.secret-input input {
  padding-right: 40px;
  width: 100%;
  min-width: 0;
}
.secret-input .icon-button {
  position: absolute;
  right: 5px;
  color: #b0b6c4;
}
</style>
