import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useFilters } from '../filters'
import type { Evidence } from '../voice'
import EvidenceList from './EvidenceList'

interface Insight {
  title: string
  what_happened: string
  so_what: string
  now_what: string
  keyakinan: string
  insufficient: boolean
  evidence: Evidence[]
  method: string
}

const CONFIDENCE_CLASS: Record<string, string> = {
  Tinggi: 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200',
  Sedang: 'bg-amber-50 text-amber-900 dark:bg-amber-950/50 dark:text-amber-200',
  Rendah: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200',
}

const STAGES: [number, string][] = [
  [0, 'Mengambil data grafik…'],
  [12, 'Membaca pola volume dan sentimen…'],
  [35, 'Menyusun What happened…'],
  [58, 'Menyusun So what…'],
  [78, 'Menyusun Now what…'],
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
        <button className="h-8 rounded-md bg-[#0A4A94] px-3 text-xs font-semibold text-white disabled:opacity-60" onClick={generate} disabled={busy}>
          {busy ? 'Menyusun…' : 'Generate Insight'}
        </button>
        {data && !busy && <button className="text-xs underline" onClick={() => setData(null)}>Tutup insight</button>}
      </div>
      {busy && (
        <div className="mt-2 border border-line p-2 text-xs" role="status">
          <div className="flex justify-between gap-2"><span>{stage}</span><span className="tabular-nums">{pct}%</span></div>
          <div className="mt-1 h-1.5 bg-line"><div className="h-1.5 bg-[#0A4A94] transition-all" style={{ width: `${pct}%` }} /></div>
        </div>
      )}
      {error && <p className="mt-2 border border-line p-2 text-sm">Insight belum tersedia. {error}</p>}
      {data && (
        <div className="mt-2 space-y-2 border border-line bg-canvas/60 p-3 text-sm">
          <Section title="What happened">{data.what_happened}</Section>
          <Section title="So what" badge="Hipotesis AI">{data.so_what}</Section>
          <Section title="Now what" badge="Saran, keputusan pada pimpinan">{data.now_what}</Section>
          <p className="text-xs">
            Keyakinan: <span className={`rounded-sm px-1.5 py-0.5 font-semibold ${CONFIDENCE_CLASS[data.keyakinan] || CONFIDENCE_CLASS.Rendah}`}>{data.keyakinan}</span>
          </p>
          <div>
            <p className="text-xs font-bold uppercase tracking-wide text-muted">Bukti</p>
            <div className="mt-1"><EvidenceList items={data.evidence} limit={3} /></div>
          </div>
          <p className="text-xs text-muted">Metode: {data.method}. Wajib diverifikasi manusia sebelum dipakai.</p>
        </div>
      )}
    </div>
  )
}

function Section({ title, badge, children }: { title: string; badge?: string; children: string }) {
  return (
    <div>
      <p className="flex flex-wrap items-center gap-2 text-xs font-bold uppercase tracking-wide text-navy-900 dark:text-gold-300">
        {title}
        {badge && <span className="rounded-sm border border-line px-1 py-0.5 text-[10px] font-semibold normal-case tracking-normal text-muted">{badge}</span>}
      </p>
      <p className="mt-0.5 leading-relaxed">{children}</p>
    </div>
  )
}
