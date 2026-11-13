import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useFilters } from '../filters'
import type { Evidence } from '../voice'
import EvidenceList from './EvidenceList'

interface Insight {
  title: string
  who?: string
  what?: string
  when?: string
  where?: string
  why?: string
  how?: string
  what_happened: string
  so_what: string
  now_what: string
  keyakinan: string
  insufficient: boolean
  evidence: Evidence[]
  method: string
  insight_version?: string
  framework?: string
}

const CONFIDENCE_CLASS: Record<string, string> = {
  Tinggi: 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200',
  Sedang: 'bg-amber-50 text-amber-900 dark:bg-amber-950/50 dark:text-amber-200',
  Rendah: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200',
}

const STAGES: [number, string][] = [
  [0, 'Mengambil data grafik…'],
  [10, 'Menyusun Who / What / When…'],
  [28, 'Menyusun Where dan How…'],
  [48, 'Menyusun Why kritis dari judul & kategori…'],
  [68, 'Menyusun So what (implikasi)…'],
  [84, 'Menyusun Now what (tindak lanjut)…'],
]

const FIVE_W: { key: keyof Insight; title: string; badge: string }[] = [
  { key: 'who', title: 'Who', badge: 'Siapa' },
  { key: 'what', title: 'What', badge: 'Apa' },
  { key: 'when', title: 'When', badge: 'Kapan' },
  { key: 'where', title: 'Where', badge: 'Di mana' },
  { key: 'why', title: 'Why', badge: 'Mengapa · kritis' },
  { key: 'how', title: 'How', badge: 'Bagaimana' },
]

export default function ChartInsight({ chart, granularity = 'day', extraQuery = '', className = '' }: { chart: 'trend' | 'komposisi' | 'volume' | 'kata' | 'suara'; granularity?: string; extraQuery?: string; className?: string }) {
  const filters = useFilters()
  const [data, setData] = useState<Insight | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [pct, setPct] = useState(0)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => {
    setData(null)
    setError('')
  }, [filters.query, granularity, extraQuery])

  useEffect(() => () => window.clearInterval(timer.current), [])

  async function generate() {
    setBusy(true)
    setError('')
    setData(null)
    setPct(0)
    const started = Date.now()
    timer.current = window.setInterval(() => {
      const seconds = (Date.now() - started) / 1000
      setPct((value) => Math.max(value, Math.min(92, Math.round(6 + 86 * (1 - Math.exp(-seconds / 2))))))
    }, 120)
    try {
      const result = await api<Insight>(`/api/insight/${chart}?granularity=${granularity}&${filters.query}${extraQuery ? `&${extraQuery}` : ''}`, { method: 'POST' })
      setPct(100)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Insight belum tersedia')
    } finally {
      window.clearInterval(timer.current)
      setBusy(false)
    }
  }

  const stage = [...STAGES].reverse().find(([from]) => pct >= from)?.[1]

  return (
    <div className={`no-print ${className}`}>
      <div className="flex flex-wrap items-center gap-2">
        <button className="h-9 rounded-sm bg-navy-900 px-4 text-xs font-bold uppercase tracking-wide text-white disabled:opacity-60" onClick={generate} disabled={busy}>
          {busy ? 'Menyusun…' : 'Generate Insight'}
        </button>
        {data && !busy && <button className="text-xs font-medium underline" onClick={() => setData(null)}>Tutup</button>}
      </div>
      {busy && (
        <div className="surface mt-2 p-3 text-xs" role="status">
          <div className="flex justify-between gap-2"><span>{stage}</span><span className="tabular-nums">{pct}%</span></div>
          <div className="mt-2 h-1 bg-line"><div className="h-1 bg-navy-900 transition-all" style={{ width: `${pct}%` }} /></div>
        </div>
      )}
      {error && <p className="surface mt-2 p-3 text-sm">Insight belum tersedia. {error}</p>}
      {data && (
        <div className="reveal surface mt-3 overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-canvas/80 px-4 py-2.5">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted">Nota pantauan · 5W1H</p>
              <p className="text-sm font-semibold">{data.title}</p>
            </div>
            <span className={`rounded-sm px-2 py-1 text-xs font-bold ${CONFIDENCE_CLASS[data.keyakinan] || CONFIDENCE_CLASS.Rendah}`}>
              Keyakinan {data.keyakinan}
            </span>
          </div>
          <div className="divide-y divide-line">
            {FIVE_W.map((item) => {
              const body = (data[item.key] as string | undefined) || (item.key === 'what' ? data.what_happened : '—')
              return (
                <div key={item.key} className="grid gap-1 px-4 py-3 sm:grid-cols-[7.5rem_minmax(0,1fr)] sm:gap-4">
                  <div>
                    <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-navy-900 dark:text-gold-300">{item.title}</p>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">{item.badge}</p>
                  </div>
                  <p className="text-justify text-sm leading-7 text-ink">{body}</p>
                </div>
              )
            })}
            <div className="grid gap-1 bg-canvas/50 px-4 py-3 sm:grid-cols-[7.5rem_minmax(0,1fr)] sm:gap-4">
              <div>
                <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-navy-900 dark:text-gold-300">So what</p>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">Hipotesis AI</p>
              </div>
              <p className="text-justify text-sm leading-7">{data.so_what}</p>
            </div>
            <div className="grid gap-1 px-4 py-3 sm:grid-cols-[7.5rem_minmax(0,1fr)] sm:gap-4">
              <div>
                <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-navy-900 dark:text-gold-300">Now what</p>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">Tindak lanjut</p>
              </div>
              <p className="whitespace-pre-wrap text-justify text-sm leading-7">{data.now_what}</p>
            </div>
          </div>
          <div className="border-t border-line px-4 py-3">
            <p className="text-[11px] font-bold uppercase tracking-wide text-muted">Bukti sumber</p>
            <div className="mt-1"><EvidenceList items={data.evidence} limit={3} /></div>
            <p className="mt-3 text-[11px] leading-relaxed text-muted">
              {data.method}{data.insight_version ? ` · ${data.insight_version}` : ''}. Why berbasis data fokus; wajib diverifikasi manusia.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
