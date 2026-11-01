<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { buildNavigation } from '../navigation'
import type { NavItem } from '../navigation'
import { useConsole } from '../stores/console'
import UiIcon from './UiIcon.vue'
import ThemeSwitcher from './ThemeSwitcher.vue'
const store = useConsole()
const route = useRoute()
const navigation = computed(() => buildNavigation(store.pages))
const mobileOpen = ref(false)
function isActive(item: NavItem): boolean {
  return item.path === route.path || (typeof item.routeName === 'string' && item.routeName === route.name)
}
const currentGroup = computed(() => navigation.value.find((group) => group.items.some(isActive)))
const currentItem = computed(() => currentGroup.value?.items.find(isActive))
async function toggleMain() {
  try { await store.activate() }
  catch { store.toast('更新失败', true) }
}
</script>
<template>
  <div class="app-layout">
    <SButton
      v-if="mobileOpen"
      class="sidebar-backdrop"
      aria-label="关闭导航"
      @click="mobileOpen = false"
    ></SButton>
    <aside class="sidebar" :class="{ 'mobile-open': mobileOpen }">
      <RouterLink to="/" class="brand" @click="mobileOpen = false">
        <span class="brand-logo">
          <svg width="25" height="25" viewBox="0 0 32 32" fill="none">
            <path
              d="M24 8H13a5 5 0 000 10h6a4 4 0 010 8H8"
              stroke="currentColor"
              stroke-width="3.4"
              stroke-linecap="round"
            />
          </svg>
        </span>
        <span>SakuBot</span>
        <span class="version-tag">{{ store.status?.version }}</span>
      </RouterLink>
      <nav aria-label="主导航">
        <div v-for="group in navigation" :key="group.label" class="nav-group">
          <div class="nav-group-label">{{ group.label }}</div>
          <RouterLink
            v-for="item in group.items"
            :key="item.path"
            :to="item.path"
            class="nav-item"
            :class="{ active: isActive(item) }"
            @click="mobileOpen = false"
          >
            <UiIcon :name="item.icon" :size="18" />
            <span>{{ item.label }}</span>
            <span v-if="item.path === '/activity' && store.pending" class="nav-count">
              {{ store.pending }}
            </span>
          </RouterLink>
        </div>
      </nav>
      <div class="sidebar-account">
        <ThemeSwitcher />
        <SButton class="icon-button" aria-label="退出登录" @click="store.logout()">
          <UiIcon name="logout" :size="17" />
        </SButton>
      </div>
    </aside>
    <div class="main-layout">
      <header class="topbar">
        <div class="breadcrumbs">
          <SButton class="icon-button mobile-menu" aria-label="导航" @click="mobileOpen = true">
            <UiIcon name="menu" />
          </SButton>
          <span>{{ currentGroup?.label }}</span>
          <UiIcon name="right" :size="13" />
          <strong>{{ currentItem?.label }}</strong>
        </div>
        <SButton class="button" :class="store.config?.enabled ? 'danger-soft' : 'primary'"
          :disabled="store.saving || (!store.ready && !store.config?.enabled)" @click="toggleMain">
          <UiIcon :name="store.config?.enabled ? 'pause' : 'power'" :size="17" />
          {{ store.config?.enabled ? '暂停 SakuBot' : '启动 SakuBot' }}
        </SButton>
      </header>
      <main class="main-content" :class="{ 'chat-content': route.path === '/chat', 'plugin-content': String(route.name || '').startsWith('extension:') }"><slot /></main>
    </div>
  </div>
</template>
<style scoped>
.main-layout { padding-top: 72px; }
.topbar { position: fixed; top: 0; left: 236px; right: 0; z-index: 20; }
.sidebar-account > :deep(.theme-switcher) { flex-direction: row; }
.main-content:not(.chat-content):not(.plugin-content) { padding-bottom: 96px; }
.main-content.chat-content { height: calc(100dvh - 72px); max-width: none; width: 100%; padding: 0; }
.chat-content :deep(.route-surface) { height: 100%; }
.main-content.plugin-content { height: calc(100dvh - 72px); max-width: none; width: 100%; padding: 0; }
.plugin-content :deep(.route-surface), .plugin-content :deep(.plugin-frame) { height: 100%; min-height: 0; }
@media (max-width: 1180px) { .topbar { left: 213px; } }
@media (max-width: 700px) {
  .main-layout { padding-top: 61px; }
  .topbar { left: 0; }
  .main-content.chat-content, .main-content.plugin-content { height: calc(100dvh - 61px); }
}
</style>
