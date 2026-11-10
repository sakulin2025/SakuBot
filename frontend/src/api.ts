import { sessionToken, unauthorized } from './credentials'

export class ApiError extends Error {
  constructor(
    public status: number,
    message?: string,
  ) {
    super(message || (status === 401 ? '登录已过期' : '操作失败'))
  }
}

export async function api<T>(
  path: string,
  options: { method?: string; body?: unknown; signal?: AbortSignal; timeout?: number } = {},
): Promise<T> {
  const token = sessionToken()
  const method = options.method || (options.body === undefined ? 'GET' : 'POST')
  const controller = new AbortController()
  let timedOut = false
  const cancel = () => controller.abort()
  if (options.signal?.aborted) cancel()
  else options.signal?.addEventListener('abort', cancel, { once: true })
  const timer = setTimeout(() => { timedOut = true; controller.abort() }, options.timeout ?? (method === 'GET' ? 20000 : 180000))
  try {
    const response = await fetch('/api/' + path, {
      method,
      headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
    })
    if (response.status === 401) unauthorized(token)
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new ApiError(response.status, typeof data.detail === 'string' ? data.detail : undefined)
    }
    return await response.json() as T
  } catch (error) {
    if (timedOut) throw new ApiError(408, '请求超时，请稍后重试')
    throw error
  } finally {
    clearTimeout(timer)
    options.signal?.removeEventListener('abort', cancel)
  }
}

export function formatDate(time?: number | null): string {
  return time
    ? new Intl.DateTimeFormat('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      }).format(time * 1000)
    : '—'
}

export function parseJson(value: unknown): unknown {
  try {
    return typeof value === 'string' ? JSON.parse(value) : value
  } catch {
    return value
  }
}
