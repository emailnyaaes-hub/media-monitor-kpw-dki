import { useEffect, useState } from 'react'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const token = localStorage.getItem('bi-token')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  let response: Response
  try {
    response = await fetch(path, { ...options, headers })
  } catch {
    throw new ApiError(0, 'API tidak terjangkau. Jalankan backend pada port 8000.')
  }
  if (response.status === 401 && !path.includes('/auth/login')) {
    localStorage.removeItem('bi-token')
    if (window.location.pathname !== '/login') window.location.assign('/login')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const detail = typeof body.detail === 'string' ? body.detail : 'Permintaan gagal'
    throw new ApiError(response.status, detail)
  }
  return response.json() as Promise<T>
}

export async function downloadPost(path: string, filename: string, body: unknown) {
  const headers = new Headers({ 'Content-Type': 'application/json' })
  const token = localStorage.getItem('bi-token')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(path, { method: 'POST', headers, body: JSON.stringify(body) })
  if (!response.ok) throw new ApiError(response.status, 'Unduhan gagal')
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export async function downloadFile(path: string, filename: string) {
  const headers = new Headers()
  const token = localStorage.getItem('bi-token')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(path, { headers })
  if (!response.ok) throw new ApiError(response.status, 'Unduhan gagal')
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(Boolean(path))
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!path) return
    let cancel = false
    setLoading(true)
    setError('')
    api<T>(path)
      .then((next) => {
        if (!cancel) setData(next)
      })
      .catch((err: Error) => {
        if (!cancel) {
          setError(err.message)
          setData(null)
        }
      })
      .finally(() => {
        if (!cancel) setLoading(false)
      })
    return () => {
      cancel = true
    }
  }, [path, tick])

  return { data, error, loading, reload: () => setTick((value) => value + 1) }
}
