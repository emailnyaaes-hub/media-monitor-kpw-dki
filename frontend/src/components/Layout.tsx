import { AlertTriangle, Bell, LogOut, Menu, Moon, Search, Settings, Sun, X } from 'lucide-react'
import { FormEvent, useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { api, useApi } from '../api'
import { useAuth } from '../auth'
import { useFilters } from '../filters'
import { formatDay, formatWhen, PLATFORM_LABEL } from '../format'
import { useTheme } from '../theme'
import type { AlertItem } from '../types'
import { Logo } from './Logo'
import { inputClass } from './Ui'

const NAV = [
  { to: '/', label: 'Ringkasan' },
  { to: '/isu', label: 'Isu & Tren' },
  { to: '/pantauan', label: 'Pantauan Kata' },
  { to: '/saran', label: 'Pusat Saran' },
  { to: '/explorer', label: 'Jelajah Berita' },
  { to: '/laporan', label: 'Laporan' },
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
  'Di paling atas, kalimat situasi menjawab apakah ada masalah sekarang.',
  'Daftar Perlu perhatian sekarang menunjukkan isu yang paling penting. Tekan Lihat.',
  'Di bawah grafik ada tiga saran tindakan. Terima, tolak, atau tunda di Pusat Saran.',
  'Filter tanggal, platform, dan kategori ada di header. Chip aktif bisa dihapus.',
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
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [briefing, setBriefing] = useState(() => document.documentElement.classList.contains('briefing'))
  const [tourStep, setTourStep] = useState<number | null>(null)
  const [viewName, setViewName] = useState('')
  const [views, setViews] = useState<SavedView[]>(() => readViews())
  const alerts = useApi<{ unread: number; items: AlertItem[] }>('/api/alerts')
  const unread = alerts.data?.items.filter((item) => !item.is_read).length || 0

  useEffect(() => {
    if (!localStorage.getItem('bi-tour-done')) setTourStep(0)
  }, [])

  function toggleBriefing() {
    const next = !briefing
    setBriefing(next)
    document.documentElement.classList.toggle('briefing', next)
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
    <div className="flex h-full flex-col bg-navy-900 text-slate-100">
      <div className="border-b border-white/10 px-4 py-4">
        <Logo light />
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
    <div className="min-h-screen bg-canvas text-ink">
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
                {briefing ? 'Keluar mode briefing' : 'Mode briefing'}
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
        <main className="px-4 py-5 md:px-6">
          <Outlet />
        </main>
        <footer className="px-4 pb-8 text-sm leading-relaxed text-muted md:px-6">
          Angka sentimen, skor risiko, dan saran bersifat pendukung. Putuskan setelah membaca sumber asli.
        </footer>
      </div>
      {tourStep !== null && (
        <div className="no-briefing fixed inset-x-0 bottom-0 z-50 border-t border-line bg-card p-4 shadow-none md:left-60" role="dialog" aria-labelledby="tour-title">
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

interface ConnectorStatus {
  name: string
  status: string
  message: string
  found: number
  added: number
  finished_at: string
}

interface IngestStatus {
  last_updated: string | null
  next_update: string | null
  running: boolean
  connectors: ConnectorStatus[]
}

function RefreshBar() {
  const { user } = useAuth()
  const status = useApi<IngestStatus>('/api/ingest/status')
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  const data = status.data
  const stale = isStale(data?.last_updated || null)
  const failed = data?.connectors.filter((item) => item.status !== 'berhasil') || []

  async function refresh() {
    setBusy(true)
    setNote('')
    try {
      const result = await api<{ status?: string; added?: number }>('/api/jobs/ingest', { method: 'POST' })
      setNote(result.status === 'sedang_berjalan' ? 'Pembaruan lain masih berjalan.' : `Selesai. Item baru: ${result.added ?? 0}.`)
      status.reload()
    } catch (err) {
      setNote(err instanceof Error ? err.message : 'Pembaruan gagal')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line px-4 py-2 text-sm text-muted">
      <span>Terakhir diperbarui: {data?.last_updated ? `${formatWhen(data.last_updated)} WIB` : 'belum ada'}</span>
      <span>Berikutnya: {data?.next_update ? `${formatWhen(data.next_update)} WIB` : 'menunggu penjadwal'}</span>
      {stale && (
        <span className="inline-flex items-center gap-1 text-amber-800 dark:text-amber-200">
          <AlertTriangle size={14} aria-hidden />
          Data lebih dari 2 jam. Angka di layar memakai pembaruan terakhir.
        </span>
      )}
      {data?.running && <span>Pengambilan sedang berjalan</span>}
      <details>
        <summary className="cursor-pointer">
          {failed.length ? `Sumber: ${failed.length} gagal` : 'Sumber: terkini'}
        </summary>
        <ul className="mt-1 max-w-3xl space-y-1">
          {data?.connectors.map((item) => (
            <li key={item.name}>
              <span className="text-ink">{item.name}</span>
              {' · '}
              {item.status === 'berhasil'
                ? `berhasil, item baru ${item.added}`
                : `Sumber ${item.name} gagal diperbarui ${formatWhen(item.finished_at)} WIB. Data lama tetap ditampilkan.`}
            </li>
          ))}
          {!data?.connectors.length && <li>Status sumber belum ada.</li>}
        </ul>
      </details>
      {user?.role === 'admin' && (
        <button className="no-briefing h-9 rounded-md bg-navy-900 px-2 text-white disabled:opacity-60" disabled={busy} onClick={refresh}>
          {busy ? 'Memperbarui...' : 'Perbarui sekarang'}
        </button>
      )}
      {note && <span className="text-ink">{note}</span>}
      {failed.length > 0 && <span className="sr-only">{failed.length} sumber gagal</span>}
    </div>
  )
}

function isStale(iso: string | null) {
  if (!iso) return false
  const [date, time] = iso.split('T')
  if (!date) return false
  const [year, month, day] = date.split('-').map(Number)
  const [hour, minute] = (time || '00:00').split(':')
  const stamp = new Date(year, (month || 1) - 1, day || 1, Number(hour), Number(minute))
  return Date.now() - stamp.getTime() > 2 * 60 * 60 * 1000
}
