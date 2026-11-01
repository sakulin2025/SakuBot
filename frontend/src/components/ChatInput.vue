<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import UiIcon from './UiIcon.vue'

const props = defineProps<{ modelValue: string; disabled?: boolean; inactive?: boolean; running?: boolean; stopping?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string]; send: []; stop: []; resize: [height: number] }>()
const root = ref<HTMLElement>()
const input = ref<HTMLTextAreaElement>()
let observer: ResizeObserver | undefined

function resize() {
  if (!input.value) return
  input.value.style.height = 'auto'
  input.value.style.height = `${Math.min(input.value.scrollHeight, 220)}px`
}
function keydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault()
    if (!props.disabled && props.modelValue.trim()) emit('send')
  }
}
watch(() => props.modelValue, () => { void nextTick(resize) })
onMounted(() => {
  resize()
  if (root.value) {
    observer = new ResizeObserver(() => { if (root.value) emit('resize', root.value.offsetHeight) })
    observer.observe(root.value)
  }
})
onUnmounted(() => observer?.disconnect())
</script>

<template>
  <div ref="root" class="chat-input">
    <slot />
    <div class="chat-input-card" :class="{ 'is-inactive': inactive, 'is-running': running }">
      <textarea ref="input" :value="modelValue" rows="1" maxlength="100000" placeholder="发送消息" aria-label="发送消息"
        @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)" @keydown="keydown" />
      <button type="button" class="chat-input-send" aria-label="发送" :disabled="disabled || !modelValue.trim()" @click="emit('send')">
        <UiIcon name="send" :size="18" />
      </button>
      <button v-if="running" type="button" class="chat-input-stop" aria-label="停止当前运行" title="停止当前运行" :disabled="stopping" @click="emit('stop')">
        <UiIcon :name="stopping ? 'loading' : 'stop'" :size="18" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.chat-input { min-width: 0; }
.chat-input-card { position: relative; padding: 6px; border: 1px solid var(--palette-border-e3dded); border-radius: 16px; background: var(--palette-bg-ffffffc9); box-shadow: 0 8px 32px var(--palette-shadow-3c28591c), 0 2px 8px var(--palette-shadow-3c28590c); backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px); transition: border-color .2s, box-shadow .2s; }
.chat-input-card:focus-within { border-color: var(--palette-border-b6a4dd); box-shadow: 0 8px 32px var(--palette-shadow-3c28591c), 0 0 0 3px var(--palette-shadow-a58ad51a); }
.chat-input-card.is-inactive, .chat-input-card.is-inactive:focus-within { border-color: var(--palette-border-e56970); box-shadow: 0 0 0 2px var(--palette-shadow-ed77772e), 0 0 22px var(--palette-shadow-e44f5a55); }
textarea { display: block; box-sizing: border-box; width: 100%; min-height: 40px; max-height: 220px; padding: 8px 54px 8px 10px; border: 0; outline: 0; resize: none; background: transparent; color: var(--ink); font-family: inherit; font-size: 13px; line-height: 24px; overflow-y: auto; }
textarea::placeholder { color: var(--muted); }
.is-running textarea { padding-right: 100px; }
.chat-input-stop { position: absolute; right: 52px; bottom: 6px; display: grid; place-items: center; width: 40px; height: 40px; border: 1px solid var(--border); border-radius: 11px; background: var(--surface); color: var(--ink); cursor: pointer; transition: opacity .2s, transform .2s; }
.chat-input-stop:hover:not(:disabled) { transform: translateY(-1px); }
.chat-input-stop:disabled { opacity: .4; cursor: default; }
.chat-input-send { position: absolute; right: 6px; bottom: 6px; display: grid; place-items: center; width: 40px; height: 40px; border: 0; border-radius: 11px; background: var(--accent); color: var(--palette-text-ffffff); cursor: pointer; transition: opacity .2s, transform .2s, background .2s; }
.chat-input-send:hover:not(:disabled) { transform: translateY(-1px); }
.chat-input-send:disabled { opacity: .4; cursor: default; }
.chat-input-send:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

 :global(html[data-theme="dark"]) .chat-input-card { background: var(--palette-dark-bg-292633d9); border-color: var(--border); box-shadow: 0 8px 32px var(--palette-dark-shadow-00000066); }
:global(html[data-theme="dark"]) .chat-input-card:focus-within { border-color: var(--accent); box-shadow: 0 8px 32px var(--palette-dark-shadow-00000066), 0 0 0 3px var(--palette-dark-shadow-ad9cff30); }
:global(html[data-theme="dark"]) .chat-input-card.is-inactive { border-color: var(--palette-dark-border-ef7f88); box-shadow: 0 0 0 2px var(--palette-dark-shadow-ed777740), 0 0 22px var(--palette-dark-shadow-e44f5a70); }
</style>
