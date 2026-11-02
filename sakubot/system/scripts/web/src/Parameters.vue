<script setup lang="ts">
import { computed } from "@sakubot/ui";
const props = defineProps<{
  schema: any;
  modelValue: Record<string, any>;
  options?: Record<string, any[]>;
}>();
const emit = defineEmits<{
  "update:modelValue": [value: Record<string, any>];
}>();
const fields = computed(() =>
  Object.entries(props.schema?.properties || {}).map(([key, definition]) => ({
    key,
    ...(definition as any),
  })),
);
function update(key: string, value: any) {
  const next = { ...props.modelValue };
  if (value === "" || value === undefined) delete next[key];
  else next[key] = value;
  emit("update:modelValue", next);
}
function jsonUpdate(key: string, value: string) {
  try {
    update(key, JSON.parse(value));
  } catch {
    update(key, value);
  }
}
</script>
<template>
  <div class="parameters">
    <div v-for="field in fields" :key="field.key" class="field">
      <label>{{ field.title || field.key }}</label>
      <SSwitch
        v-if="field.type === 'boolean'"
        :model-value="modelValue[field.key] ?? field.default ?? false"
        @update:model-value="update(field.key, $event)"
      />
      <SSelect
        v-else-if="field.enum || options?.[field.key]"
        :model-value="modelValue[field.key] ?? field.default ?? ''"
        @update:model-value="update(field.key, $event)"
        ><option value="">—</option>
        <option
          v-for="item in options?.[field.key] ||
          field.enum.map((v: any) => ({ value: v, label: v }))"
          :key="String(item.value)"
          :value="item.value"
        >
          {{ item.label }}
        </option></SSelect
      >
      <STextarea
        v-else-if="field.type === 'object' || field.type === 'array'"
        :model-value="
          typeof modelValue[field.key] === 'string'
            ? modelValue[field.key]
            : JSON.stringify(
                modelValue[field.key] ??
                  field.default ??
                  (field.type === 'array' ? [] : {}),
                null,
                2,
              )
        "
        rows="3"
        @update:model-value="jsonUpdate(field.key, String($event))"
      />
      <SInput
        v-else
        :model-value="modelValue[field.key] ?? field.default ?? ''"
        :type="
          field.type === 'integer' || field.type === 'number'
            ? 'number'
            : field.format === 'time'
              ? 'time'
              : 'text'
        "
        :min="field.minimum"
        :max="field.maximum"
        :required="schema.required?.includes(field.key)"
        :placeholder="field.title || field.key"
        @update:model-value="
          update(
            field.key,
            field.type === 'integer' || field.type === 'number'
              ? $event === ''
                ? undefined
                : Number($event)
              : $event,
          )
        "
      />
    </div>
  </div>
</template>
<style scoped>
.parameters {
  display: grid;
  gap: 14px;
}
</style>
