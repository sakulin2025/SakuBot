<script setup lang="ts">
defineOptions({ name: 'StructuredValue' })
defineProps<{ value: unknown }>()
const entries = (value: unknown) => Object.entries(value as Record<string, unknown>)
const complex = (value: unknown) => value !== null && typeof value === 'object'
const display = (value: unknown) => value === null ? 'null' : typeof value === 'string' ? value : String(value)
</script>

<template>
  <div v-if="complex(value)" class="structured">
    <div v-for="([key, item]) in entries(value)" :key="key" class="structured-row">
      <span class="structured-key">{{ Array.isArray(value) ? Number(key) + 1 : key }}</span>
      <StructuredValue v-if="complex(item)" :value="item" />
      <pre v-else class="structured-value">{{ display(item) }}</pre>
    </div>
    <span v-if="!entries(value).length" class="structured-empty">{{ Array.isArray(value) ? '[]' : '{}' }}</span>
  </div>
  <pre v-else class="structured-value">{{ display(value) }}</pre>
</template>

<style scoped>
.structured { min-width: 0; display: grid; gap: 8px; border-left: 1px solid var(--border); padding-left: 12px; }
.structured-row { min-width: 0; display: grid; grid-template-columns: minmax(90px, 170px) minmax(0, 1fr); gap: 12px; align-items: start; }
.structured-key { color: var(--text-muted); overflow-wrap: anywhere; font-size: 12px; }
.structured-value { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; font-size: 13px; }
.structured-empty { color: var(--text-muted); }
@media (max-width: 600px) { .structured-row { grid-template-columns: 1fr; gap: 3px; } }
</style>
