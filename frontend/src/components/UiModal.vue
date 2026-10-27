<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import UiIcon from './UiIcon.vue'
const props = withDefaults(defineProps<{ open: boolean; title: string; wide?: boolean }>(), { wide: false })
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement>()
let closing: ReturnType<typeof setTimeout> | undefined
watch(
  () => props.open,
  async (value) => {
    await nextTick()
    clearTimeout(closing)
    if (value) {
      dialog.value?.classList.remove('is-leaving')
      if (!dialog.value?.open) dialog.value?.showModal()
    } else if (dialog.value?.open) {
      dialog.value.classList.add('is-leaving')
      closing = setTimeout(() => dialog.value?.close(), 150)
    }
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  clearTimeout(closing)
  dialog.value?.close()
})
</script>
<template>
  <dialog ref="dialog" class="modal" :class="{ wide }" closedby="none" @cancel.prevent>
    <div class="modal-header">
      <h2>{{ title }}</h2>
      <SButton class="icon-button" type="button" aria-label="关闭" @click="emit('close')">
        <UiIcon name="close" />
      </SButton>
    </div>
    <div class="modal-content"><slot /></div>
    <div v-if="$slots.footer" class="modal-footer"><slot name="footer" /></div>
  </dialog>
</template>

<style>
.modal {
  width: min(570px, calc(100vw - 32px));
  border: 1px solid #e1e5ed;
  border-radius: 13px;
  padding: 0;
  background: #fff;
  color: var(--ink);
  max-height: 88vh;
  box-shadow: 0 25px 100px #101b4026;
}
.modal.wide {
  width: min(870px, calc(100vw - 32px));
}
.modal::backdrop {
  background: #22283d55;
  backdrop-filter: blur(4px);
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 21px 25px;
  border-bottom: 1px solid var(--border);
}
.modal-header h2 {
  font-size: 15px;
}
.modal-content {
  padding: 25px;
  overflow: auto;
  max-height: calc(88vh - 140px);
}
.modal-footer {
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 17px 25px;
}
@media (max-width: 700px) {
  .modal-header {
    padding: 19px 20px;
  }
  .modal-content {
    padding: 21px 20px;
  }
  .modal-footer {
    padding: 15px 20px;
  }
}
.modal[open] {
  animation: s-dialog-in 0.22s cubic-bezier(0.2, 0.9, 0.2, 1);
}
.modal[open]::backdrop {
  animation: s-backdrop-in 0.2s ease;
  background: #24233e59;
  backdrop-filter: blur(4px);
}
.modal.is-leaving {
  animation: s-dialog-out 0.15s ease forwards;
}
.modal.is-leaving::backdrop {
  animation: s-backdrop-out 0.15s ease forwards;
}
@keyframes s-dialog-in {
  from {
    opacity: 0;
    transform: translateY(16px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
@keyframes s-dialog-out {
  to {
    opacity: 0;
    transform: translateY(8px) scale(0.99);
  }
}
@keyframes s-backdrop-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
@keyframes s-backdrop-out {
  to {
    opacity: 0;
  }
}
html:has(dialog[open]) {
  overflow: hidden;
}
.modal {
  border: 1px solid #f2f0fa;
  border-radius: 16px;
  box-shadow: 0 24px 80px #24213b24;
}
.modal-header {
  background: #fdfcfe;
}
.modal-footer {
  background: #faf9fd;
}
.plugin-document .modal {
  max-height: 94vh;
}
.plugin-document .modal-content {
  max-height: calc(94vh - 140px);
}
</style>
