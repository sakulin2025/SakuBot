<script setup lang="ts">
import {
  ref,
  computed,
  onMounted,
  UiIcon,
  UiBadge,
  UiModal,
  UiEmpty,
  usePluginHost,
  formatDate,
} from "@sakubot/ui";
import type { Person } from "@sakubot/ui";
const host = usePluginHost();
const rows = ref<Person[]>([]);
const query = ref("");
const selected = ref<Person | null>(null);
const loading = ref(false);
const filtered = computed(() =>
  rows.value.filter((row) => JSON.stringify(row.data).includes(query.value)),
);
async function load() {
  loading.value = true;
  try {
    rows.value = await host.api<Person[]>("people");
  } catch {
    host.toast("加载失败", true);
  } finally {
    loading.value = false;
  }
}
onMounted(load);
</script>
<template>
  <SCard class="surface">
    <div class="table-toolbar">
      <div class="search-field">
        <UiIcon name="search" :size="17" /><SInput
          v-model="query"
          placeholder="搜索人物"
          aria-label="搜索人物"
        />
      </div>
      <span class="toolbar-spacer"></span
      ><SButton
        class="icon-button"
        aria-label="刷新"
        :disabled="loading"
        @click="load"
      >
        <UiIcon name="refresh" :class="{ spinning: loading }" :size="17" />
      </SButton>
    </div>
    <div v-if="filtered.length" class="table-scroll">
      <STable class="data-table">
        <thead>
          <tr>
            <th>人物</th>
            <th>QQ</th>
            <th>别名</th>
            <th class="align-right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in filtered" :key="row.id">
            <td>
              <div class="person-cell">
                <span class="person-avatar">{{
                  (row.data.nickname || row.id).slice(0, 1)
                }}</span
                ><strong>{{ row.data.nickname || row.id }}</strong>
              </div>
            </td>
            <td class="mono">{{ row.id }}</td>
            <td class="content-cell">{{ row.data.aliases.join("、") }}</td>
            <td>
              <div class="row-actions">
                <SButton class="text-button" @click="selected = row">
                  详情<UiIcon name="right" :size="13" />
                </SButton>
              </div>
            </td>
          </tr>
        </tbody>
      </STable>
    </div>
    <UiEmpty v-else />
  </SCard>
  <UiModal :open="!!selected" title="人物" @close="selected = null"
    ><div v-if="selected" class="form-stack">
      <div class="person-cell">
        <span class="person-avatar">{{
          (selected.data.nickname || selected.id).slice(0, 1)
        }}</span
        ><strong>{{ selected.data.nickname }}</strong>
      </div>
      <div class="field">
        <label>QQ</label><span class="mono">{{ selected.id }}</span>
      </div>
      <div class="field">
        <label>别名</label><span>{{ selected.data.aliases.join("、") }}</span>
      </div>
      <div class="field">
        <label>群名片</label>
        <div
          v-for="(name, group) in selected.data.groups"
          :key="group"
          class="tool-row"
        >
          <span class="mono">{{ group }}</span
          ><strong>{{ name }}</strong>
        </div>
      </div>
      <span class="subtle">{{ formatDate(selected.updated) }}</span>
    </div></UiModal
  >
</template>
