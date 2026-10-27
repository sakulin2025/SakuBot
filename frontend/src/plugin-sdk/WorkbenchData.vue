<script setup lang="ts">
import { computed } from 'vue'
const props = withDefaults(defineProps<{ value: any; depth?: number }>(), { depth: 0 })
const labels: Record<string, string> = {
  last_balance: '最近余额',
  fetched_at: '查询时间',
  provider_id: '供应商 ID',
  name: '名称',
  description: '描述',
  id: 'ID',
  status: '状态',
  online: '在线',
  connected: '已连接',
  address: '地址',
  host: '主机',
  port: '端口',
  username: '用户名',
  device: '设备',
  alias: '别名',
  aliases: '别名',
  server: '服务器',
  version: '版本',
  players: '玩家',
  max_players: '人数上限',
  latency: '延迟',
  latency_ms: '延迟 · ms',
  motd: '服务器公告',
  edition: '版本类型',
  error: '错误',
  result: '结果',
  data: '数据',
  items: '条目',
  success: '成功',
  message: '消息',
  text: '内容',
  at: '时间',
  updated_at: '更新时间',
  last_seen: '最近出现',
  ip: 'IP',
  mac: 'MAC',
  devices: '设备',
  count: '数量',
  total: '总计',
  has_more: '还有更多',
  next_cursor: '下一页游标',
  balance: '余额',
  currency: '币种',
  total_balance: '总余额',
  granted_balance: '赠送余额',
  topped_up_balance: '充值余额',
  is_available: '可用',
  balance_infos: '余额明细',
  entity_id: '实体 ID',
  friendly_name: '名称',
  state: '状态',
  attributes: '属性',
  temperature: '温度',
  humidity: '湿度',
  feelsLike: '体感温度',
  temp: '温度',
  windDir: '风向',
  windScale: '风力',
  obsTime: '观测时间',
  updateTime: '更新时间',
  now: '实时天气',
  daily: '每日预报',
  hourly: '逐时预报',
  fxDate: '预报日期',
  fxTime: '预报时间',
  tempMax: '最高温度',
  tempMin: '最低温度',
  textDay: '白天天气',
  textNight: '夜间天气',
  location: '位置',
  cwd: '工作目录',
  shell: 'Shell',
  timeout: '超时',
  output: '输出',
  exit_code: '退出码',
  command: '命令',
  public_key: '公钥',
  initialized: '已初始化',
  rooms: '房间',
  entities: '实体',
  notifications: '通知',
  enabled: '启用',
}
const data = computed(() => {
  if (typeof props.value === 'string') {
    try {
      return JSON.parse(props.value)
    } catch {
      /* plain text */
    }
  }
  return props.value
})
const arrayObjects = computed(
  () =>
    Array.isArray(data.value) &&
    data.value.length &&
    data.value.every((x: any) => x && typeof x === 'object' && !Array.isArray(x)),
)
const columns = computed<string[]>(() =>
  arrayObjects.value ? [...new Set<string>(data.value.flatMap((x: any) => Object.keys(x)))] : [],
)
const name = (key: string) => labels[key] || key
</script>
<template>
  <div v-if="data == null || data === ''" class="wb-data-empty">—</div>
  <div v-else-if="arrayObjects && depth < 3" class="wb-data-table">
    <table>
      <thead>
        <tr>
          <th v-for="key in columns" :key="key">{{ name(key) }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, i) in data" :key="i">
          <td v-for="key in columns" :key="key"><WorkbenchData :value="row[key]" :depth="depth + 1" /></td>
        </tr>
      </tbody>
    </table>
  </div>
  <div v-else-if="Array.isArray(data)" class="wb-data-list">
    <div v-for="(item, i) in data" :key="i"><WorkbenchData :value="item" :depth="depth + 1" /></div>
    <span v-if="!data.length" class="wb-data-empty">—</span>
  </div>
  <dl v-else-if="typeof data === 'object'" class="wb-data-object">
    <div v-for="(value, key) in data" :key="String(key)">
      <dt>{{ name(String(key)) }}</dt>
      <dd><WorkbenchData :value="value" :depth="depth + 1" /></dd>
    </div>
  </dl>
  <STag
    v-else-if="typeof data === 'boolean'"
    :status="data ? 'enabled' : 'disabled'"
    :label="data ? '是' : '否'"
  />
  <span v-else class="wb-data-value">{{ data }}</span>
</template>
<style scoped>
.wb-data-empty {
  color: var(--muted);
}
.wb-data-object {
  margin: 0;
  display: grid;
  gap: 0;
}
.wb-data-object > div {
  display: grid;
  grid-template-columns: minmax(100px, 160px) minmax(0, 1fr);
  gap: 20px;
  padding: 13px 0;
  border-bottom: 1px solid var(--border);
}
.wb-data-object > div:last-child {
  border-bottom: 0;
}
.wb-data-object dt {
  font-size: 12px;
  color: var(--muted);
  overflow-wrap: anywhere;
}
.wb-data-object dd {
  margin: 0;
  min-width: 0;
  font-size: 13px;
}
.wb-data-value {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.7;
}
.wb-data-table {
  overflow: auto;
  max-width: 100%;
}
.wb-data-table table {
  border-collapse: collapse;
  width: 100%;
  font-size: 12px;
}
.wb-data-table th {
  text-align: left;
  font-weight: 550;
  color: var(--muted);
  white-space: nowrap;
  background: var(--canvas);
}
.wb-data-table th,
.wb-data-table td {
  padding: 10px 13px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}
.wb-data-table td {
  min-width: 90px;
  max-width: 300px;
}
.wb-data-list {
  display: grid;
  gap: 12px;
}
.wb-data-list > div + div {
  border-top: 1px solid var(--border);
  padding-top: 12px;
}
@media (max-width: 600px) {
  .wb-data-object > div {
    grid-template-columns: 1fr;
    gap: 5px;
  }
}
</style>
