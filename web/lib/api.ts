const LOCAL_API_BASE = 'http://127.0.0.1:8080'

export interface ApiErrorPayload {
  code?: string
  message: string
  provider?: string
  model_name?: string
  agent_name?: string
}

export class ApiRequestError extends Error {
  status: number
  payload: ApiErrorPayload

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message)
    this.name = 'ApiRequestError'
    this.status = status
    this.payload = payload
  }
}

export function getApiBase(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL || LOCAL_API_BASE
}

export async function parseApiErrorPayload(res: Response): Promise<ApiErrorPayload> {
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    const data = await res.json().catch(() => null)
    if (data?.error?.message) {
      return {
        code: data.error.code ? String(data.error.code) : undefined,
        message: String(data.error.message),
        provider: data.error.provider ? String(data.error.provider) : undefined,
        model_name: data.error.model_name ? String(data.error.model_name) : undefined,
        agent_name: data.error.agent_name ? String(data.error.agent_name) : undefined,
      }
    }
    if (Array.isArray(data?.detail)) {
      return { message: data.detail.map((entry: { msg?: string }) => entry.msg || 'Invalid request').join('; ') }
    }
    if (data?.detail) return { message: String(data.detail) }
  }
  const text = await res.text().catch(() => '')
  return { message: text || `Request failed with HTTP ${res.status}` }
}

export async function parseApiError(res: Response): Promise<string> {
  const payload = await parseApiErrorPayload(res)
  return payload.message
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  if (!headers.has('Content-Type') && init.body) {
    headers.set('Content-Type', 'application/json')
  }
  headers.set('X-Demo-User', headers.get('X-Demo-User') || 'demo-user')
  const res = await fetch(`${getApiBase()}${path}`, { ...init, headers })
  if (!res.ok) {
    throw new ApiRequestError(res.status, await parseApiErrorPayload(res))
  }
  return res
}
