const key = 'sakubot-token'

export function sessionToken() { return sessionStorage.getItem(key) || '' }
export function rememberedToken() { return localStorage.getItem(key) || '' }
export function setSessionToken(token: string) {
  sessionStorage.setItem(key, token)
  window.dispatchEvent(new Event('sakubot-token-changed'))
}
export function rememberToken(token: string) {
  localStorage.setItem(key, token)
  setSessionToken(token)
}
export function clearToken(forget = true) {
  sessionStorage.removeItem(key)
  if (forget) localStorage.removeItem(key)
}
export function unauthorized(token: string) {
  if (token === sessionToken()) window.dispatchEvent(new CustomEvent('sakubot-unauthorized', { detail: { token } }))
}
