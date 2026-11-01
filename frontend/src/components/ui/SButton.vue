<script setup lang="ts">
import { computed, ref, useAttrs } from 'vue'
import UiIcon from '../UiIcon.vue'
defineOptions({ inheritAttrs: false })
const props = withDefaults(
  defineProps<{
    variant?: 'default' | 'primary' | 'danger' | 'text'
    loading?: boolean
    disabled?: boolean
    size?: 'small' | 'default'
    icon?: string
  }>(),
  { variant: 'default', size: 'default' },
)
const attrs = useAttrs()
const pressed = ref(false)
const plain = computed(
  () => (Boolean(attrs.class) && !/(^|\s)button(\s|$)/.test(String(attrs.class))) || props.variant === 'text',
)
</script>
<template>
  <button
    v-bind="attrs"
    :disabled="disabled || loading"
    :aria-busy="loading || undefined"
    :class="[
      's-button',
      {
        button: !plain,
        primary: variant === 'primary',
        danger: variant === 'danger',
        'text-button': variant === 'text',
        compact: size === 'small',
        'is-pressed': pressed,
        'is-loading': loading,
      },
    ]"
    @pointerdown="pressed = true"
    @pointerup="pressed = false"
    @pointerleave="pressed = false"
    @blur="pressed = false"
  >
    <UiIcon
      v-if="loading || icon"
      :name="loading ? 'loading' : icon!"
      :size="16"
      :class="{ spinning: loading }"
    />
    <slot :loading="loading" />
  </button>
</template>

<style>
.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 9px 15px;
  min-height: 36px;
  border: 1px solid var(--palette-border-dfe3eb);
  background: var(--palette-bg-ffffff);
  color: var(--palette-text-616a7c);
  border-radius: 7px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  box-shadow: 0 1px 2px var(--palette-shadow-17203404);
  transition:
    background 0.15s,
    border-color 0.15s;
}
.button:hover {
  background: var(--palette-bg-f8f9fc);
  border-color: var(--palette-border-cbd2df);
}
.button.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--palette-text-ffffff);
  box-shadow: 0 2px 4px var(--palette-shadow-515bdf18);
}
.button.primary:hover {
  background: var(--palette-bg-444acb);
  border-color: var(--palette-border-444acb);
}
.button.compact {
  padding: 7px 11px;
  min-height: 32px;
  font-size: 10px;
}
.button.danger-soft {
  background: var(--palette-bg-ffffff);
  color: var(--palette-text-986166);
  border-color: var(--palette-border-ebdce0);
}
.button.danger {
  background: var(--negative);
  color: var(--palette-text-ffffff);
  border-color: var(--negative);
}
.button-count {
  font-size: 10px;
  padding: 0 5px;
  border-radius: 4px;
  background: var(--palette-bg-f0f1f6);
}
.icon-button {
  width: 31px;
  height: 31px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--palette-text-8a93a5);
  transition: background 0.15s;
}
.icon-button:hover {
  background: var(--palette-bg-eff1f7);
  color: var(--palette-text-59657d);
}
.text-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: transparent;
  border: 0;
  padding: 3px 0;
  color: var(--palette-text-8c94a6);
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}
.text-button:hover {
  color: var(--accent);
}
.s-button {
  position: relative;
  transition:
    background var(--s-motion),
    border-color var(--s-motion),
    box-shadow var(--s-motion),
    transform var(--s-motion);
  white-space: nowrap;
  isolation: isolate;
}
.s-button.is-pressed:not(:disabled) {
  transform: translateY(1px) scale(0.975);
}
.s-button.primary {
  background: linear-gradient(135deg, var(--palette-bg-7668ec), var(--palette-bg-5c50cb));
  border-color: var(--palette-border-6c5cdb);
  box-shadow:
    0 3px 7px var(--palette-shadow-6958d829),
    inset 0 1px 0 var(--palette-shadow-ffffff30);
}
.s-button.primary:hover:not(:disabled) {
  box-shadow: 0 5px 14px var(--palette-shadow-6958d83b);
  background: linear-gradient(135deg, var(--palette-bg-8274f2), var(--palette-bg-685ad5));
}
.s-button.is-loading {
  cursor: progress;
}
.s-button:focus-visible {
  outline: 0;
  box-shadow: var(--s-ring);
}

html[data-theme="dark"] .button:not(.primary):not(.danger) { background: var(--surface-alt); color: var(--ink); border-color: var(--border); }
html[data-theme="dark"] .button:not(.primary):not(.danger):hover { background: var(--palette-dark-bg-373145); }
html[data-theme="dark"] .button.danger-soft { color: var(--negative); }
html[data-theme="dark"] .icon-button:hover { background: var(--surface-alt); color: var(--accent); }
</style>
