const LOCAL_API_BASE = 'http://127.0.0.1:8080'

export function getApiBase(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL || LOCAL_API_BASE
}

export async function parseApiError(res: Response): Promise<string> {
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    const data = await res.json().catch(() => null)
    if (data?.error?.message) return String(data.error.message)
    if (Array.isArray(data?.detail)) {
      return data.detail.map((entry: { msg?: string }) => entry.msg || 'Invalid request').join('; ')
    }
    if (data?.detail) return String(data.detail)
  }
  const text = await res.text().catch(() => '')
  return text || `Request failed with HTTP ${res.status}`
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  if (!headers.has('Content-Type') && init.body) {
    headers.set('Content-Type', 'application/json')
  }
  headers.set('X-Demo-User', headers.get('X-Demo-User') || 'demo-user')
  const res = await fetch(`${getApiBase()}${path}`, { ...init, headers })
  if (!res.ok) {
    throw new Error(await parseApiError(res))
  }
  return res
}
