<script setup lang="ts">
import SSpinner from './SSpinner.vue'
defineProps<{ title?: string; loading?: boolean; divided?: boolean }>()
</script>
<template>
  <section
    class="surface s-card"
    :class="{ 'is-loading': loading, 'is-divided': divided }"
    :aria-busy="loading || undefined"
  >
    <header v-if="title || $slots.header || $slots.actions" class="s-card-header">
      <slot name="header">
        <h2>{{ title }}</h2>
      </slot>
      <div v-if="$slots.actions" class="row-actions"><slot name="actions" /></div>
    </header>
    <slot />
    <Transition name="s-fade">
      <div v-if="loading" class="s-loading-mask"><SSpinner /></div>
    </Transition>
  </section>
</template>

<style>
.surface {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: var(--shadow);
  overflow: hidden;
}
.surface-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 19px 23px;
  border-bottom: 1px solid var(--border);
}
@media (max-width: 700px) {
  .surface-heading {
    padding: 17px 18px;
  }
}
.s-card {
  position: relative;
  transition:
    border-color var(--s-motion),
    box-shadow var(--s-motion);
  border-radius: var(--s-radius);
  background: #fff;
}
.s-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 22px;
  border-bottom: 1px solid var(--border);
  min-height: 62px;
}
.s-loading-mask {
  position: absolute;
  inset: 0;
  z-index: 5;
  background: #ffffffbd;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: inherit;
  backdrop-filter: blur(2px);
}
.s-fade-enter-active,
.s-fade-leave-active {
  transition: opacity 0.16s ease;
}
.s-fade-enter-from,
.s-fade-leave-to {
  opacity: 0;
}
.surface {
  border-color: var(--border);
  box-shadow: 0 2px 8px #27213e03;
  border-radius: var(--s-radius);
}
@media (max-width: 900px) {
  .s-card-header {
    padding: 16px 18px;
  }
}
</style>
