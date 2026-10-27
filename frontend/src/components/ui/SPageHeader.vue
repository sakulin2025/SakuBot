<script setup lang="ts">
defineProps<{ title: string; count?: number }>()
</script>
<template>
  <div class="page-heading s-page-header">
    <div class="heading-title">
      <h1>{{ title }}</h1>
      <span v-if="count !== undefined" class="heading-count">{{ count }}</span>
    </div>
    <div v-if="$slots.default" class="heading-actions"><slot /></div>
  </div>
</template>

<style>
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
  color: #989faf;
  font-weight: 500;
}
.heading-count {
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 23px;
  height: 23px;
  background: #e9ecf2;
  border: 1px solid #e1e5ed;
  color: #7b8495;
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
.s-page-header {
  margin-bottom: 24px;
}
.heading-count {
  border-radius: 8px;
  background: #eeeaf9;
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
</style>
