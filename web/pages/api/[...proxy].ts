import type { NextApiRequest, NextApiResponse } from 'next'

const BACKEND_URL = 'http://localhost:8080'

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const { path, ...query } = req.query

  const slug = Array.isArray(path) ? path.join('/') : path ?? ''
  const searchParams = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (typeof value === 'string') {
      searchParams.set(key, value)
    }
  }
  const qs = searchParams.toString()
  const backendUrl = `${BACKEND_URL}/${slug}${qs ? `?${qs}` : ''}`

  try {
    const backendRes = await fetch(backendUrl, {
      method: req.method,
      headers: {
        'Content-Type': 'application/json',
        'X-Demo-User': 'demo',
      },
      body: req.method !== 'GET' && req.method !== 'HEAD' ? JSON.stringify(req.body) : undefined,
    })

    const contentType = backendRes.headers.get('content-type') || ''
    const body = contentType.includes('application/json')
      ? await backendRes.json()
      : await backendRes.text()

    res.status(backendRes.status)
    if (contentType.includes('application/json')) {
      res.json(body)
    } else {
      res.send(body)
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    res.status(502).json({ error: `Backend unreachable: ${message}` })
  }
}
