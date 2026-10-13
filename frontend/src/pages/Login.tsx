import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { APP_LONG, APP_NAME, BiLogo, Copyright, LogoMark, UNIT } from '../components/Logo'

const PHOTOS = [
  '/img/jakarta.jpg',
  '/img/monas.jpg',
  '/img/newsroom.jpg',
  '/img/koran.jpg',
  '/img/pers.jpg',
  '/img/ponsel.jpg',
]

export default function Login() {
  const { user, login } = useAuth()
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
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
    <div className="relative isolate min-h-screen overflow-hidden bg-navy-950 font-sans text-white">
      <div className="absolute inset-0 -z-10 grid grid-cols-2 grid-rows-3 md:grid-cols-3 md:grid-rows-2" aria-hidden>
        {PHOTOS.map((src) => <img key={src} src={src} alt="" className="h-full w-full object-cover" />)}
        <div className="absolute inset-0 bg-navy-950/55" />
        <div className="absolute inset-0 bg-gradient-to-r from-navy-950/70 via-navy-950/30 to-transparent" />
      </div>

      <div className="flex min-h-screen flex-col px-6 py-7 md:px-10">
        <div className="grid flex-1 gap-10 pb-10 lg:grid-cols-[1fr_24rem] lg:pr-[10vw]">
          <section>
            <BiLogo className="h-8 w-auto md:h-9" />
            <p className="mt-6 text-[11px] font-semibold uppercase tracking-[0.28em] text-sky-300">{UNIT}</p>
            <div className="mt-3 flex items-center gap-4">
              <LogoMark className="h-16 w-16 shrink-0 md:h-20 md:w-20" />
              <h1 className="text-5xl font-extrabold uppercase tracking-wide md:text-6xl">{APP_NAME}</h1>
            </div>
            <p className="mt-3 text-base text-slate-100 md:text-lg">{APP_LONG}</p>
          </section>

          <form onSubmit={submit} className="w-full self-center bg-white p-7 text-slate-700">
            <div className="flex items-center gap-3">
              <LogoMark className="h-11 w-11 shrink-0" />
              <div>
                <p className="text-lg font-extrabold uppercase leading-tight tracking-wide text-navy-900">{APP_NAME}</p>
                <p className="text-[11px] uppercase tracking-wide text-slate-500">Masuk ke dashboard resmi</p>
              </div>
            </div>
            <h2 className="mt-6 text-2xl font-extrabold text-navy-900">Selamat datang</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">Masuk dengan akun Admin.</p>
            <label className="mt-5 grid gap-1.5 text-[11px] font-extrabold uppercase tracking-wide text-navy-900">
              Nama pengguna
              <input className="h-10 border border-slate-300 bg-white px-3 text-sm font-normal normal-case tracking-normal text-slate-800" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} />
            </label>
            <label className="mt-4 grid gap-1.5 text-[11px] font-extrabold uppercase tracking-wide text-navy-900">
              Kata sandi
              <input type="password" className="h-10 border border-slate-300 bg-white px-3 text-sm font-normal normal-case tracking-normal text-slate-800" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} />
            </label>
            {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
            <button className="mt-5 h-10 w-full bg-[#0A4A94] text-sm font-bold text-white hover:bg-[#083d7a] disabled:opacity-60" disabled={busy}>
              {busy ? 'Memeriksa...' : 'Masuk'}
            </button>
            <p className="mt-4 text-center text-xs text-slate-500">Bank Indonesia · akses terbatas</p>
          </form>
        </div>

        <Copyright className="text-xs text-slate-300" />
      </div>
    </div>
  )
}
