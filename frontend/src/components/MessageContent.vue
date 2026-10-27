<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ text: string; parts?: unknown }>()
interface Part {
  type: string
  text?: string
  url?: string
  name?: string
}
const parts = computed<Part[]>(() =>
  Array.isArray(props.parts)
    ? props.parts.filter(
        (item): item is Part => !!item && typeof item === 'object' && typeof item.type === 'string',
      )
    : [],
)
function url(value?: string) {
  if (!value) return ''
  try {
    const parsed = new URL(value, window.location.origin)
    return ['http:', 'https:'].includes(parsed.protocol) ? parsed.href : ''
  } catch {
    return ''
  }
}
</script>
<template>
  <div v-if="parts.length" class="message-content">
    <template v-for="(part, index) in parts" :key="index">
      <span v-if="part.type === 'text'">{{ part.text }}</span>
      <img
        v-else-if="part.type === 'image' && url(part.url)"
        :src="url(part.url)"
        :alt="part.name || '图片'"
        loading="lazy"
        referrerpolicy="no-referrer"
      />
      <video
        v-else-if="part.type === 'video' && url(part.url)"
        :src="url(part.url)"
        controls
        preload="metadata"
      />
      <audio
        v-else-if="part.type === 'audio' && url(part.url)"
        :src="url(part.url)"
        controls
        preload="metadata"
      />
      <a v-else-if="url(part.url)" :href="url(part.url)" target="_blank" rel="noopener noreferrer">
        {{ part.name || '文件' }}
      </a>
      <span v-else>
        {{
          part.name ||
          { image: '图片', video: '视频', audio: '语音', file: '文件' }[part.type as 'file'] ||
          part.type
        }}
      </span>
    </template>
  </div>
  <template v-else>{{ text }}</template>
</template>
<style scoped>
.message-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.message-content img,
.message-content video {
  display: block;
  max-width: min(100%, 480px);
  max-height: 420px;
  border-radius: 10px;
  object-fit: contain;
}
.message-content audio {
  max-width: 100%;
}
.message-content a {
  color: var(--primary);
  overflow-wrap: anywhere;
}
</style>
