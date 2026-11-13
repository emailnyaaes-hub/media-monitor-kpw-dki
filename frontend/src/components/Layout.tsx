import { Bell, Compass, LayoutGrid, LogOut, Menu, MessageSquareText, Moon, Search, Settings, Sparkles, Sun, X } from 'lucide-react'
import { FormEvent, useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { api, useApi } from '../api'
import { useAuth } from '../auth'
import { useFilters } from '../filters'
import { formatDay, PLATFORM_LABEL } from '../format'
import { useTheme } from '../theme'
import type { AlertItem } from '../types'
import { BiLogo, Copyright, Logo, UNIT } from './Logo'
import { inputClass } from './Ui'

const NAV = [
  { to: '/', label: 'Ringkasan' },
  { to: '/suara', label: 'Suara Publik' },
  { to: '/review', label: 'Review Konten' },
  { to: '/saran', label: 'Rekomendasi' },
  { to: '/explorer', label: 'Jelajah Berita' },
]

const MOBILE_NAV = [
  { to: '/', label: 'Ringkasan', icon: LayoutGrid },
  { to: '/suara', label: 'Suara', icon: MessageSquareText },
  { to: '/saran', label: 'Saran', icon: Sparkles },
  { to: '/explorer', label: 'Jelajah', icon: Compass },
]

const CATEGORIES = [
  'Kebijakan Moneter',
  'Sistem Pembayaran',
  'Rupiah/Kurs',
  'Inflasi',
  'Perbankan/Kredit',
  'Pengedaran Uang',
  'Reputasi/Kelembagaan',
  'Hoaks/Penipuan',
  'Kegiatan KPw DKI',
  'Ekonomi Jakarta',
  'Lainnya',
]

const TOUR = [
  'Ringkasan dibaca seperti kanal berita. Mulai dari judul utama, lalu berita di bawahnya.',
  'Pilih rubrik di atas daftar, misalnya Berita Nasional atau KPw DKI, untuk mengganti kanal.',
  'Mode briefing membesarkan teks agar nyaman dibaca di layar presentasi.',
]

interface SavedView {
  name: string
  dateFrom: string
  dateTo: string
  platform: string
  category: string
}

export default function Layout() {
  const { user, logout } = useAuth()
  const filters = useFilters()
  const { theme, toggle } = useTheme()
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [briefing, setBriefing] = useState(() => document.documentElement.classList.contains('briefing'))
  const [tourStep, setTourStep] = useState<number | null>(null)
  const [viewName, setViewName] = useState('')
  const [views, setViews] = useState<SavedView[]>(() => readViews())
  const [searchParams, setSearchParams] = useSearchParams()
  const urlReady = useRef(false)

  useEffect(() => {
    if (urlReady.current) return
    urlReady.current = true
    const dari = searchParams.get('dari')
    const sampai = searchParams.get('sampai')
    if (dari && sampai) {
      filters.apply({
        dateFrom: dari,
        dateTo: sampai,
        platform: searchParams.get('platform') || 'semua',
        category: searchParams.get('kategori') || 'semua',
      })
    }
  }, [filters, searchParams])

  useEffect(() => {
    if (!urlReady.current) return
    const next = new URLSearchParams()
    next.set('dari', filters.dateFrom)
    next.set('sampai', filters.dateTo)
    if (filters.platform !== 'semua') next.set('platform', filters.platform)
    if (filters.category !== 'semua') next.set('kategori', filters.category)
    setSearchParams(next, { replace: true })
  }, [filters.dateFrom, filters.dateTo, filters.platform, filters.category, setSearchParams, urlReady])
  const alerts = useApi<{ unread: number; items: AlertItem[] }>('/api/alerts')
  const unread = alerts.data?.items.filter((item) => !item.is_read).length || 0

  useEffect(() => {
    if (!localStorage.getItem('bi-tour-done')) setTourStep(0)
  }, [])

  function toggleBriefing() {
    const next = !briefing
    setBriefing(next)
    document.documentElement.classList.toggle('briefing', next)
    if (next) document.documentElement.classList.remove('analisis')
  }

  function search(event: FormEvent) {
    event.preventDefault()
    navigate(query.trim() ? `/explorer?q=${encodeURIComponent(query.trim())}` : '/explorer')
  }

  function saveView(event: FormEvent) {
    event.preventDefault()
    const name = viewName.trim()
    if (!name) return
    const next = [...views.filter((item) => item.name !== name), { name, dateFrom: filters.dateFrom, dateTo: filters.dateTo, platform: filters.platform, category: filters.category }]
    setViews(next)
    localStorage.setItem('bi-views', JSON.stringify(next))
    setViewName('')
  }

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `flex min-h-11 items-center border-l-2 px-3 text-base ${isActive ? 'border-gold-500 bg-white/10 text-gold-300' : 'border-transparent text-slate-200 hover:bg-white/5'}`

  const sidebar = (
    <div className="relative isolate flex h-full flex-col bg-navy-900 text-slate-100">
      <div className="pointer-events-none absolute inset-0 -z-10" aria-hidden>
        <img src="/img/newsroom.jpg" alt="" className="h-full w-full object-cover" />
        <div className="absolute inset-0 bg-navy-900/90" />
      </div>
      <div className="border-b border-white/10 px-4 py-4">
        <BiLogo className="h-6 w-auto" />
        <p className="mt-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-sky-300">{UNIT}</p>
        <div className="mt-2">
          <Logo light />
        </div>
      </div>
      <nav className="flex-1 overflow-y-auto py-2" aria-label="Utama">
        {NAV.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.to === '/'} onClick={() => setOpen(false)} className={linkClass}>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-white/10">
        <NavLink to="/pengaturan" onClick={() => setOpen(false)} className={linkClass}>
          <Settings size={16} className="mr-2" aria-hidden />
          Pengaturan
        </NavLink>
        <div className="px-4 py-3 text-sm text-slate-300">
          <p className="font-medium text-slate-100">{user?.full_name}</p>
          <p>{user?.role_label}</p>
        </div>
      </div>
    </div>
  )

  return (
    <div className="relative isolate min-h-screen text-ink">
      <div className="no-print pointer-events-none fixed inset-0 -z-10" aria-hidden>
        <img src="/img/jakarta.jpg" alt="" className="h-full w-full object-cover" />
        <div className="absolute inset-0" style={{ background: 'var(--canvas)', opacity: 0.88 }} />
      </div>
      <aside className="no-briefing fixed inset-y-0 left-0 z-30 hidden w-60 md:block">{sidebar}</aside>
      {open && (
        <div className="no-briefing fixed inset-0 z-40 md:hidden">
          <button className="absolute inset-0 bg-navy-950/70" aria-label="Tutup menu" onClick={() => setOpen(false)} />
          <div className="relative h-full w-72">{sidebar}</div>
        </div>
      )}
      <div className="briefing-shift md:pl-60">
        <header className="sticky top-0 z-20 border-b border-line bg-card">
          <div className="flex flex-wrap items-end gap-2 px-4 py-3">
            <button className="no-briefing grid h-11 w-11 place-items-center rounded-md border border-line md:hidden" onClick={() => setOpen(true)} aria-label="Buka menu">
              {open ? <X size={18} /> : <Menu size={18} />}
            </button>
            <span className="no-briefing flex h-11 items-center md:hidden">
              <BiLogo variant="blue" className="h-6 w-auto dark:hidden" />
              <BiLogo className="hidden h-6 w-auto dark:block" />
            </span>
            <form className="no-briefing flex min-w-48 flex-1 items-end gap-2" onSubmit={search}>
              <label className="grid min-w-40 flex-1 gap-1 text-sm text-muted">
                Cari judul atau isu
                <span className="flex items-center gap-2">
                  <Search size={16} aria-hidden />
                  <input className={inputClass} value={query} onChange={(event) => setQuery(event.target.value)} />
                </span>
              </label>
              <button className="h-11 rounded-md bg-navy-900 px-3 text-sm text-white">Cari</button>
            </form>
            <details className="w-full md:contents">
              <summary className="flex h-11 cursor-pointer items-center md:hidden">Filter</summary>
              <div className="mt-2 flex w-full flex-wrap gap-2 md:contents">
            <label className="grid gap-1 text-sm text-muted">
              Dari
              <input className={inputClass} type="date" value={filters.dateFrom} onChange={(event) => filters.setDateFrom(event.target.value)} />
            </label>
            <label className="grid gap-1 text-sm text-muted">
              Sampai
              <input className={inputClass} type="date" value={filters.dateTo} onChange={(event) => filters.setDateTo(event.target.value)} />
            </label>
            <label className="grid gap-1 text-sm text-muted">
              Platform
              <select className={inputClass} value={filters.platform} onChange={(event) => filters.setPlatform(event.target.value)}>
                <option value="semua">Semua</option>
                {Object.entries(PLATFORM_LABEL).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
              </select>
            </label>
            <label className="grid min-w-40 gap-1 text-sm text-muted">
              Kategori
              <select className={inputClass} value={filters.category} onChange={(event) => filters.setCategory(event.target.value)}>
                <option value="semua">Semua</option>
                {CATEGORIES.map((item) => <option key={item}>{item}</option>)}
              </select>
            </label>
              </div>
            </details>
            <div className="ml-auto flex items-center gap-2">
              <button className="h-11 rounded-md border border-line px-3 text-sm" onClick={toggleBriefing} aria-pressed={briefing}>
                {briefing ? 'Keluar briefing' : 'Briefing'}
              </button>
              <button className="no-briefing relative grid h-11 w-11 place-items-center rounded-md border border-line" aria-label="Notifikasi" onClick={() => navigate('/alert')}>
                <Bell size={18} />
                {unread > 0 && <span className="absolute right-1 top-1 grid h-4 min-w-4 place-items-center rounded-sm bg-red-700 px-1 text-[10px] text-white">{unread}</span>}
              </button>
              <button className="no-briefing grid h-11 w-11 place-items-center rounded-md border border-line" onClick={toggle} aria-label={theme === 'dark' ? 'Mode terang' : 'Mode gelap'}>
                {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
              </button>
              <button className="grid h-11 w-11 place-items-center rounded-md border border-line" onClick={() => { logout(); navigate('/login') }} aria-label="Keluar">
                <LogOut size={18} />
              </button>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 border-t border-line px-4 py-2 text-sm">
            <span className="rounded-sm border border-line px-2 py-1">{formatDay(filters.dateFrom)} – {formatDay(filters.dateTo)}</span>
            {filters.platform !== 'semua' && (
              <button className="rounded-sm border border-line px-2 py-1" onClick={() => filters.setPlatform('semua')}>
                {PLATFORM_LABEL[filters.platform] || filters.platform} ×
              </button>
            )}
            {filters.category !== 'semua' && (
              <button className="rounded-sm border border-line px-2 py-1" onClick={() => filters.setCategory('semua')}>
                {filters.category} ×
              </button>
            )}
            <button className="underline" onClick={filters.reset}>Atur ulang semua</button>
            <details className="no-briefing">
              <summary className="cursor-pointer">Tampilan tersimpan</summary>
              <form className="mt-2 flex flex-wrap gap-2" onSubmit={saveView}>
                <input className={inputClass} placeholder="Nama tampilan" value={viewName} onChange={(event) => setViewName(event.target.value)} />
                <button className="h-11 rounded-md border border-line px-3">Simpan tampilan</button>
              </form>
              <ul className="mt-2 space-y-1">
                {views.length === 0 && <li className="text-muted">Belum ada tampilan tersimpan.</li>}
                {views.map((item) => (
                  <li key={item.name}>
                    <button className="underline" onClick={() => filters.apply(item)}>{item.name}</button>
                  </li>
                ))}
              </ul>
            </details>
          </div>
          <RefreshBar />
        </header>
        <main className="px-4 py-5 pb-24 md:px-6 md:pb-5">
          <Outlet />
        </main>
        <footer className="no-briefing hidden border-t border-line px-4 py-4 text-sm leading-relaxed text-muted md:block md:px-6">
          <p>Angka sentimen, skor risiko, dan saran bersifat pendukung. Putuskan setelah membaca sumber asli.</p>
          <Copyright className="mt-1 text-xs" />
        </footer>
      </div>
      <nav className="bottom-nav no-briefing no-print" aria-label="Navigasi cepat">
        {MOBILE_NAV.map((item) => {
          const Icon = item.icon
          const active = item.to === '/' ? location.pathname === '/' : location.pathname.startsWith(item.to)
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={`flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 text-[10px] font-bold uppercase tracking-wide ${active ? 'text-navy-900 dark:text-gold-300' : 'text-muted'}`}
            >
              <Icon size={18} aria-hidden />
              {item.label}
            </NavLink>
          )
        })}
      </nav>
      {tourStep !== null && (
        <div className="no-briefing fixed inset-x-0 bottom-14 z-50 border-t border-line bg-card p-4 shadow-none md:bottom-0 md:left-60" role="dialog" aria-labelledby="tour-title">
          <p id="tour-title" className="text-sm text-muted">Langkah {tourStep + 1} dari {TOUR.length}</p>
          <p className="mt-1 text-base">{TOUR[tourStep]}</p>
          <div className="mt-3 flex gap-2">
            <button className="h-11 rounded-md bg-navy-900 px-3 text-sm text-white" onClick={() => tourStep === TOUR.length - 1 ? finishTour(setTourStep) : setTourStep(tourStep + 1)}>
              {tourStep === TOUR.length - 1 ? 'Selesai' : 'Berikutnya'}
            </button>
            <button className="h-11 rounded-md border border-line px-3 text-sm" onClick={() => finishTour(setTourStep)}>Lewati</button>
          </div>
        </div>
      )}
    </div>
  )
}

function finishTour(setTourStep: (value: number | null) => void) {
  localStorage.setItem('bi-tour-done', '1')
  setTourStep(null)
}

function readViews(): SavedView[] {
  try {
    const raw = localStorage.getItem('bi-views')
    return raw ? JSON.parse(raw) as SavedView[] : []
  } catch {
    return []
  }
}

function RefreshBar() {
  const { user } = useAuth()
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  const canRefresh = user?.role === 'admin' || user?.role === 'analis'
  if (!canRefresh) return null

  async function refresh() {
    setBusy(true)
    setNote('Mengambil sumber… bisa 30–60 detik.')
    try {
      // Jangan retag dulu — retag seluruh arsip sering timeout di Vercel sebelum ingest jalan.
      const result = await api<{ status: string; added?: number; skipped?: number; message?: string }>(
        '/api/jobs/ingest?mode=cepat&wait=true&force=true',
        { method: 'POST' },
      )
      if (result.status === 'sedang_berjalan') {
        setNote('Pengambilan lain masih berjalan. Tunggu sebentar lalu coba lagi.')
        return
      }
      if (result.status === 'gagal') {
        setNote(result.message || 'Pengambilan gagal. Coba lagi.')
        return
      }
      const added = result.added ?? 0
      setNote(added > 0 ? `Selesai: ${added} berita baru. Memuat ulang…` : 'Selesai: belum ada berita baru dari sumber. Memuat ulang…')
      window.setTimeout(() => window.location.reload(), 900)
    } catch (err) {
      setNote(err instanceof Error ? err.message : 'Pengambilan gagal.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-end gap-3 border-t border-line px-4 py-2 md:px-6">
      {note ? <p className="max-w-md text-right text-sm text-muted" role="status">{note}</p> : null}
      <button
        type="button"
        className="no-briefing h-9 rounded-md bg-navy-900 px-4 text-sm text-white disabled:opacity-60"
        disabled={busy}
        onClick={() => void refresh()}
      >
        {busy ? 'Memperbarui…' : 'Perbarui'}
      </button>
    </div>
  )
}
