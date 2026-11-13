import { Search } from 'lucide-react'
import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

const ACTIONS = [
  { id: 'ringkasan', label: 'Buka Ringkasan', hint: 'Beranda berita', path: '/' },
  { id: 'suara', label: 'Buka Suara Publik', hint: 'Tren & isu', path: '/suara' },
  { id: 'review', label: 'Buka Review Konten', hint: 'Koreksi label', path: '/review' },
  { id: 'saran', label: 'Buka Rekomendasi', hint: 'Tindak lanjut', path: '/saran' },
  { id: 'explorer', label: 'Buka Jelajah Berita', hint: 'Cari semua berita', path: '/explorer' },
  { id: 'alert', label: 'Buka Alert', hint: 'Notifikasi', path: '/alert' },
  { id: 'settings', label: 'Buka Pengaturan', hint: 'Akun & sistem', path: '/pengaturan' },
]

export default function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    const actions = ACTIONS.filter((item) => !q || `${item.label} ${item.hint}`.toLowerCase().includes(q))
    const search = q
      ? [{ id: 'search', label: `Cari berita «${query.trim()}»`, hint: 'Jelajah Berita', path: `/explorer?q=${encodeURIComponent(query.trim())}` }]
      : []
    return [...search, ...actions]
  }, [query])

  useEffect(() => {
    if (!open) return
    setQuery('')
    setActive(0)
  }, [open])

  useEffect(() => {
    setActive(0)
  }, [query])

  if (!open) return null

  function go(path: string) {
    onClose()
    navigate(path)
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    const item = filtered[active]
    if (item) go(item.path)
  }

  return (
    <div className="cmd-overlay no-print" role="dialog" aria-modal="true" aria-label="Perintah cepat" onClick={onClose}>
      <div className="surface w-full max-w-lg overflow-hidden shadow-none" onClick={(event) => event.stopPropagation()}>
        <form className="flex items-center gap-2 border-b border-line px-3 py-2" onSubmit={onSubmit}>
          <Search size={16} className="text-muted" aria-hidden />
          <input
            autoFocus
            className="h-10 w-full bg-transparent text-sm outline-none placeholder:text-muted"
            placeholder="Cari menu atau berita… (Esc tutup)"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Escape') onClose()
              if (event.key === 'ArrowDown') {
                event.preventDefault()
                setActive((value) => Math.min(value + 1, Math.max(filtered.length - 1, 0)))
              }
              if (event.key === 'ArrowUp') {
                event.preventDefault()
                setActive((value) => Math.max(value - 1, 0))
              }
            }}
          />
          <kbd className="hidden rounded-sm border border-line px-1.5 py-0.5 text-[10px] text-muted sm:inline">esc</kbd>
        </form>
        <ul className="max-h-72 overflow-y-auto py-1">
          {filtered.length === 0 && <li className="px-3 py-4 text-sm text-muted">Tidak ada hasil.</li>}
          {filtered.map((item, index) => (
            <li key={item.id}>
              <button
                type="button"
                className={`flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left text-sm ${index === active ? 'bg-navy-900 text-white' : 'hover:bg-line/40'}`}
                onMouseEnter={() => setActive(index)}
                onClick={() => go(item.path)}
              >
                <span className="font-medium">{item.label}</span>
                <span className={`text-xs ${index === active ? 'text-white/70' : 'text-muted'}`}>{item.hint}</span>
              </button>
            </li>
          ))}
        </ul>
        <p className="border-t border-line px-3 py-2 text-[11px] text-muted">
          Pintasan: <kbd className="rounded-sm border border-line px-1">⌘</kbd>/<kbd className="rounded-sm border border-line px-1">Ctrl</kbd>+<kbd className="rounded-sm border border-line px-1">K</kbd>
        </p>
      </div>
    </div>
  )
}
