<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { buildNavigation } from '../navigation'
import type { NavItem } from '../navigation'
import { useConsole } from '../stores/console'
import UiIcon from './UiIcon.vue'
import UiBadge from './UiBadge.vue'
const store = useConsole()
const route = useRoute()
const navigation = computed(() => buildNavigation(store.pages))
const mobileOpen = ref(false)
function isActive(item: NavItem): boolean {
  return item.path === route.path || (typeof item.routeName === 'string' && item.routeName === route.name)
}
const currentGroup = computed(() => navigation.value.find((group) => group.items.some(isActive)))
const currentItem = computed(() => currentGroup.value?.items.find(isActive))
const refreshing = ref(false)
async function refresh() {
  refreshing.value = true
  try {
    await store.refresh()
  } catch {
    store.toast('刷新失败', true)
  } finally {
    refreshing.value = false
  }
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
        <span class="account-avatar"><UiIcon name="persona" :size="21" /></span>
        <div>
          <strong>SakuBot</strong>
          <span>main</span>
        </div>
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
        <div class="topbar-actions">
          <UiBadge :status="store.config?.enabled ? 'enabled' : 'disabled'" />
          <span class="topbar-divider"></span>
          <SButton class="icon-button" aria-label="刷新" :disabled="refreshing" @click="refresh">
            <UiIcon name="refresh" :class="{ spinning: refreshing }" :size="17" />
          </SButton>
          <span class="owner-avatar">S</span>
        </div>
      </header>
      <main class="main-content"><slot /></main>
    </div>
  </div>
</template>
