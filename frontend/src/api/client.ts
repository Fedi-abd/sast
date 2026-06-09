/**
 * Tiny fetch wrapper that handles the two Django-specific concerns
 * the rest of the app shouldn't have to think about:
 *
 *   1. Session cookies — Django auth lives in the `sessionid` cookie,
 *      so every API call needs `credentials: 'same-origin'`.
 *   2. CSRF — Django's CsrfViewMiddleware requires the `X-CSRFToken`
 *      header on POST/PUT/PATCH/DELETE, with the value matching the
 *      `csrftoken` cookie Django set on first GET. SessionAuthentication
 *      in DRF enforces this for write endpoints.
 *
 * On 401/403 the wrapper throws an `UnauthorizedError`; views should
 * catch this at the top level and bounce to /accounts/login/.
 */

export class UnauthorizedError extends Error {
  constructor(message = 'Not authenticated') {
    super(message)
    this.name = 'UnauthorizedError'
  }
}

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, body: unknown, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

function readCookie(name: string): string | null {
  const cookies = document.cookie.split(';')
  for (const raw of cookies) {
    const [key, value] = raw.trim().split('=')
    if (key === name) return decodeURIComponent(value ?? '')
  }
  return null
}

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

interface RequestOptions {
  method?: Method
  body?: unknown
  headers?: Record<string, string>
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method: Method = options.method ?? 'GET'
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(options.headers ?? {}),
  }

  if (method !== 'GET') {
    const csrf = readCookie('csrftoken')
    if (csrf) headers['X-CSRFToken'] = csrf
    if (options.body !== undefined && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json'
    }
  }

  const init: RequestInit = {
    method,
    headers,
    credentials: 'same-origin',
  }
  if (options.body !== undefined) {
    init.body =
      options.body instanceof FormData
        ? options.body
        : JSON.stringify(options.body)
  }

  const response = await fetch(path, init)

  if (response.status === 401 || response.status === 403) {
    throw new UnauthorizedError()
  }

  if (!response.ok) {
    let parsed: unknown = null
    try {
      parsed = await response.json()
    } catch {
      // some error responses (404 HTML, gateway errors) aren't JSON
    }
    throw new ApiError(response.status, parsed, `Request failed (${response.status})`)
  }

  // 204 No Content (e.g., DELETE) — no body to parse.
  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
