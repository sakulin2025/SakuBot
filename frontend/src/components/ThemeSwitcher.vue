<script setup lang="ts">
import { setTheme, themePreference, type ThemePreference } from '../theme'
import UiIcon from './UiIcon.vue'
const choices: { value: ThemePreference; label: string; icon: string }[] = [
  { value: 'light', label: '亮色模式', icon: 'sun' },
  { value: 'system', label: '跟随系统', icon: 'monitor' },
  { value: 'dark', label: '深色模式', icon: 'moon' },
]
</script>
<template>
  <div class="theme-switcher" role="radiogroup" aria-label="外观">
    <button v-for="choice in choices" :key="choice.value" type="button" role="radio" :aria-checked="themePreference === choice.value"
      :aria-label="choice.label" :title="choice.label" :class="{ selected: themePreference === choice.value }" @click="setTheme(choice.value)">
      <UiIcon :name="choice.icon" :size="16" />
    </button>
  </div>
</template>
<style scoped>
.theme-switcher { display: flex; flex-direction: row; align-items: center; flex: 1; gap: 3px; padding: 3px; border: 1px solid var(--border); border-radius: 10px; background: var(--canvas); }
.theme-switcher button { display: grid; flex: 1; place-items: center; height: 29px; padding: 0; border: 0; border-radius: 7px; background: transparent; color: var(--muted); transition: color .2s, background .2s, box-shadow .2s; }
.theme-switcher button:hover { color: var(--ink); }
.theme-switcher button.selected { color: var(--accent); background: var(--surface); box-shadow: 0 1px 5px var(--palette-shadow-211b4018); }
.theme-switcher button:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
</style>
