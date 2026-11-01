import { ref } from 'vue'

export type ThemePreference = 'system' | 'light' | 'dark'
const key = 'sakubot-theme'
const valid = (value: string | null): ThemePreference => value === 'light' || value === 'dark' ? value : 'system'
export const themePreference = ref<ThemePreference>(valid(localStorage.getItem(key)))
const system = window.matchMedia('(prefers-color-scheme: dark)')
let initialized = false

function apply() {
  document.documentElement.dataset.theme = themePreference.value === 'system' ? (system.matches ? 'dark' : 'light') : themePreference.value
  window.dispatchEvent(new Event('sakubot-theme-changed'))
}
export function setTheme(value: ThemePreference) {
  themePreference.value = value
  localStorage.setItem(key, value)
  apply()
}
export function initTheme() {
  if (initialized) return
  initialized = true
  apply()
  system.addEventListener('change', apply)
  window.addEventListener('storage', event => {
    if (event.key === key) { themePreference.value = valid(event.newValue); apply() }
  })
}
