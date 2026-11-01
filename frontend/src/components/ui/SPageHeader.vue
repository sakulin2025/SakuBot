<script setup lang="ts">
defineProps<{ title: string; count?: number; floating?: boolean }>()
</script>
<template>
  <Teleport v-if="$slots.default && floating" to="body"><div class="floating-actions"><slot /></div></Teleport>
  <div v-else-if="$slots.default" class="page-heading s-page-header">
    <div class="heading-actions"><slot /></div>
  </div>
</template>

<style>
.floating-actions { position: fixed; right: 28px; bottom: 24px; z-index: 20; display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; max-width: calc(100vw - 32px); padding: 8px; border: 1px solid var(--border); border-radius: 14px; background: var(--palette-bg-ffffffdb); box-shadow: 0 8px 30px var(--palette-shadow-30254b26); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); }
@media (max-width: 700px) { .floating-actions { right: 12px; bottom: 12px; } }
.page-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 28px;
  min-height: 55px;
}
.heading-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  position: relative;
  padding-top: 20px;
}
.page-kicker {
  position: absolute;
  top: 0;
  left: 0;
  font-size: 10px;
  color: var(--palette-text-989faf);
  font-weight: 500;
}
.heading-count {
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 23px;
  height: 23px;
  background: var(--palette-bg-e9ecf2);
  border: 1px solid var(--palette-border-e1e5ed);
  color: var(--palette-text-7b8495);
  border-radius: 6px;
  margin-top: 2px;
}
@media (max-width: 700px) {
  .page-heading {
    margin-bottom: 21px;
    gap: 12px;
  }
  .page-heading h1 {
    font-size: 23px;
  }
  .page-heading > .button {
    font-size: 10px;
    padding: 8px 11px;
    min-height: 33px;
  }
}
.page-heading:not(:has(.heading-title)) {
  justify-content: flex-end;
  min-height: 0;
  margin-bottom: 16px;
}
.s-page-header {
  margin-bottom: 16px;
}
.heading-count {
  border-radius: 8px;
  background: var(--palette-bg-eeeaf9);
  color: var(--accent);
}

.heading-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
@media (max-width: 700px) {
  .heading-actions {
    gap: 7px;
  }
}
@media (max-width: 700px) {
  .heading-actions .button {
    font-size: 9px;
    padding: 7px 10px;
  }
}

html[data-theme="dark"] .floating-actions { background: var(--palette-dark-bg-292633e8); border-color: var(--border); box-shadow: 0 8px 30px var(--palette-dark-shadow-00000077); }
</style>
