import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { Logo } from '../components/Logo'

const DEMOS = [
  { username: 'analis', password: 'analis123', label: 'Analis' },
  { username: 'pimpinan', password: 'pimpinan123', label: 'Pimpinan' },
  { username: 'admin', password: 'admin123', label: 'Admin' },
]

export default function Login() {
  const { user, login } = useAuth()
  const [username, setUsername] = useState('analis')
  const [password, setPassword] = useState('analis123')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/" replace />

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await login(username, password)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Gagal masuk')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-screen bg-navy-950 text-slate-100 md:grid-cols-2">
      <section className="flex flex-col justify-between px-8 py-10 md:px-12">
        <div>
          <Logo light />
          <h1 className="mt-8 max-w-md font-serif text-3xl leading-tight">Media Monitor dan Social Listening</h1>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-slate-300">
            Memantau pemberitaan dan percakapan publik tentang Bank Indonesia serta kegiatan KPw DKI,
            lalu memisahkan peluang (upside) dari risiko reputasi (downside).
          </p>
        </div>
        <p className="max-w-md text-xs leading-relaxed text-slate-400">
          Hasil analisis otomatis wajib diverifikasi manusia sebelum dipakai untuk komunikasi resmi atau masukan kebijakan.
        </p>
      </section>
      <section className="flex items-center bg-canvas px-6 py-10 text-ink">
        <form onSubmit={submit} className="mx-auto w-full max-w-sm rounded-md border border-line bg-card p-6">
          <h2 className="text-lg font-semibold">Masuk</h2>
          <p className="mt-1 text-sm text-muted">Gunakan akun demo. Sandi ini hanya untuk latihan lokal.</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {DEMOS.map((item) => (
              <button
                type="button"
                key={item.username}
                className="rounded-full border border-line px-3 py-1 text-xs"
                onClick={() => { setUsername(item.username); setPassword(item.password) }}
              >
                {item.label}
              </button>
            ))}
          </div>
          <label className="mt-4 grid gap-1 text-sm">
            Nama pengguna
            <input className="h-10 rounded-lg border border-line bg-card px-3" value={username} onChange={(event) => setUsername(event.target.value)} />
          </label>
          <label className="mt-3 grid gap-1 text-sm">
            Sandi
            <input type="password" className="h-10 rounded-lg border border-line bg-card px-3" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
          <button className="mt-5 h-10 w-full rounded-lg bg-navy-900 text-sm font-medium text-white" disabled={busy}>
            {busy ? 'Memeriksa...' : 'Masuk ke dashboard'}
          </button>
        </form>
      </section>
    </div>
  )
}
