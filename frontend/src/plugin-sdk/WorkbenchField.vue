<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import UiIcon from '../components/UiIcon.vue'
const props = defineProps<{
  field: any
  modelValue: any
  options?: any[]
  editing?: boolean
  configured?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [value: any] }>()
const id = useId(),
  reveal = ref(false)
const value = computed({ get: () => props.modelValue, set: (v) => emit('update:modelValue', v) })
const locked = computed(() => props.field.readonly || (props.field.immutable && props.editing))
</script>
<template>
  <div
    class="wb-field"
    :class="{ 'wb-field-wide': field.type === 'text', 'wb-field-toggle': field.type === 'boolean' }"
  >
    <label :for="id">
      {{ field.label }}
      <span v-if="field.required" class="wb-required">*</span>
    </label>
    <SSwitch
      v-if="field.type === 'boolean'"
      :id="id"
      v-model="value"
      :disabled="locked"
      :aria-label="field.label"
    />
    <SSelect
      v-else-if="field.type === 'select'"
      :id="id"
      v-model="value"
      :options="options || []"
      :disabled="locked"
      :required="field.required"
      :placeholder="field.placeholder || '请输入' + field.label"
    />
    <STextarea
      v-else-if="field.type === 'text'"
      :id="id"
      v-model="value"
      :readonly="locked"
      :required="field.required"
      :placeholder="field.placeholder || '请输入' + field.label"
      rows="6"
    />
    <div v-else class="wb-input-wrap">
      <SInput
        :id="id"
        v-model="value"
        :type="
          field.type === 'number'
            ? 'number'
            : field.type === 'secret' && !reveal
              ? 'password'
              : field.format === 'http-url'
                ? 'url'
                : 'text'
        "
        :readonly="locked"
        :required="field.required && !configured"
        :min="field.min"
        :max="field.max"
        :placeholder="configured ? '已配置，留空保留原值' : field.placeholder || '请输入' + field.label"
        :maxlength="field.max_length"
        :pattern="field.pattern"
        :autocomplete="field.type === 'secret' ? 'new-password' : 'off'"
      />
      <button
        v-if="field.type === 'secret'"
        type="button"
        class="wb-reveal"
        :aria-label="reveal ? '隐藏密钥' : '显示密钥'"
        @click="reveal = !reveal"
      >
        <UiIcon :name="reveal ? 'hidden' : 'eye'" :size="16" />
      </button>
    </div>
  </div>
</template>
<style scoped>
.wb-field {
  display: flex;
  flex-direction: column;
  gap: 9px;
  min-width: 0;
}
.wb-field > label {
  font-size: 13px;
  font-weight: 550;
  color: var(--ink);
}
.wb-required {
  color: var(--negative);
  margin-left: 5px;
}
.wb-field-wide {
  grid-column: 1/-1;
}
.wb-field-toggle {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  min-height: 60px;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--canvas);
}
.wb-input-wrap {
  position: relative;
}
.wb-input-wrap .s-input {
  width: 100%;
}
.wb-input-wrap:has(.wb-reveal) .s-input {
  padding-right: 42px;
}
.wb-reveal {
  position: absolute;
  right: 5px;
  top: 50%;
  transform: translateY(-50%);
  border: 0;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  display: grid;
  place-items: center;
  padding: 8px;
  border-radius: 8px;
}
.wb-reveal:hover {
  color: var(--accent);
  background: var(--canvas);
}
</style>
