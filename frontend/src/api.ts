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
  options: { method?: string; body?: unknown; signal?: AbortSignal } = {},
): Promise<T> {
  const token = sessionStorage.getItem('sakubot-token') || ''
  const response = await fetch('/api/' + path, {
    method: options.method || (options.body === undefined ? 'GET' : 'POST'),
    headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  })
  if (response.status === 401) window.dispatchEvent(new Event('sakubot-unauthorized'))
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new ApiError(response.status, typeof data.detail === 'string' ? data.detail : undefined)
  }
  return response.json() as Promise<T>
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
