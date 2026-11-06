<script setup lang="ts">
import { computed, ref } from '@sakubot/ui'
const props = defineProps<{ source: any }>()
const tab = ref('variables')
function schemaType(value: any): string {
  if (value?.anyOf || value?.oneOf) return [...new Set((value.anyOf || value.oneOf).map(schemaType))].join(' | ')
  return Array.isArray(value?.type) ? value.type.join(' | ') : value?.type || 'object'
}
function fields(schema: any, prefix: string): any[] {
  const rows: any[] = []
  for (const [key, raw] of Object.entries(schema?.properties || {})) {
    const value = raw as any
    const path = prefix ? `${prefix}[${JSON.stringify(key)}]` : key
    rows.push({ path, type: schemaType(value),
      description: value.description, required: schema.required?.includes(key), unit: value['x-unit'],
      meanings: value['x-enum-descriptions'], example: value.examples?.[0] })
    rows.push(...fields(value, path))
    for (const branch of value.anyOf || value.oneOf || []) rows.push(...fields(branch, path))
    if (value.items?.properties) rows.push(...fields(value.items, path + '[i]'))
    if (value.items?.['x-enum-descriptions']) rows.push({path:path+'[i]',type:value.items.type,description:value.items.description,meanings:value.items['x-enum-descriptions']})
  }
  return rows
}
const variables = computed(() => fields(props.source?.event_schema, 'ctx.event["data"]'))
const parameters = computed(() => fields(props.source?.parameters, 'source_params'))
const envelope = [
  {path:'ctx.event["id"]',type:'string',description:'生产插件提供的去重 ID'},
  {path:'ctx.event["source"]',type:'string',description:'实际完整事件 ID，不含通配符'},
  {path:'ctx.event["at"]',type:'number',description:'框架分发时间，Unix 秒（UTC 基准），不是业务事件发生时间'},
  {path:'ctx.event["data"]',type:'object',description:'下方声明的业务事件数据'},
]
</script>
<template>
  <div v-if="source" class="source-docs">
    <div class="source-docs-heading"><code>{{ source.id }}</code><span>{{ source.event_schema?.description }}</span><span>{{ source.id_description }}</span></div>
    <STabs v-model="tab" :items="[{value:'variables',label:'事件变量'},{value:'parameters',label:'绑定参数'},{value:'examples',label:'事件示例'}]" />
    <div v-if="tab !== 'examples'" class="table-scroll">
      <STable><thead><tr><th>变量</th><th>类型</th><th>说明</th></tr></thead>
        <tbody><tr v-for="row in tab === 'variables' ? [...envelope, ...variables] : parameters" :key="row.path">
          <td><code>{{ row.path }}</code><STag v-if="row.required" label="必填" /></td><td>{{ row.type }}</td>
          <td>{{ row.description }}<span v-if="row.unit"> · {{ row.unit }}</span><div v-for="(meaning, value) in row.meanings" :key="String(value)"><code>{{ value }}</code>：{{ meaning }}</div></td>
        </tr><tr v-if="tab === 'parameters' && !parameters.length"><td colspan="3">无绑定参数</td></tr></tbody>
      </STable>
    </div>
    <div v-else class="source-docs-examples"><pre v-for="(example, index) in source.event_schema?.examples || []" :key="index">{{ JSON.stringify(example, null, 2) }}</pre></div>
  </div>
</template>
<style scoped>
.source-docs { display:flex; flex-direction:column; gap:12px; min-width:0; }
.source-docs-heading { display:flex; flex-direction:column; gap:8px; color:var(--muted); font-size:13px; line-height:1.6; }
.source-docs code { font-size:12px; overflow-wrap:anywhere; }
.source-docs td { vertical-align:top; line-height:1.6; }
.source-docs-examples pre { margin:0; padding:16px; overflow:auto; background:var(--surface-alt); color:var(--ink); border:1px solid var(--border); border-radius:10px; font-size:12px; }
</style>
