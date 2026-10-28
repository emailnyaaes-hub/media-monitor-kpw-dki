import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../api'
import type { AdviceItem } from '../components/AdviceCard'
import { priorityOf } from '../components/AdviceCard'
import { TrendChart } from '../components/Charts'
import BackToGeneral from '../components/BackToGeneral'
import ChartInsight from '../components/ChartInsight'
import RecommendationDrawer from '../components/RecommendationDrawer'
import { Empty, ErrorNote, Loading, QuoteBadge, StanceBadge } from '../components/Ui'
import { useFilters } from '../filters'
import { formatNumber, formatPct, PLATFORM_LABEL, relativeTime } from '../format'
import type { MentionCard, Overview, TrendPoint } from '../types'
import ExecutivePage from './Executive'

const RUBRIK = [
  { id: 'semua', label: 'Beranda' },
  { id: 'Kebijakan Moneter', label: 'Moneter' },
  { id: 'Rupiah/Kurs', label: 'Rupiah' },
  { id: 'Inflasi', label: 'Inflasi' },
  { id: 'Sistem Pembayaran', label: 'Pembayaran' },
  { id: 'Perbankan/Kredit', label: 'Perbankan' },
  { id: 'Ekonomi Jakarta', label: 'Ekonomi Jakarta' },
  { id: 'Kegiatan KPw DKI', label: 'KPw DKI' },
  { id: 'Reputasi/Kelembagaan', label: 'Kelembagaan' },
  { id: 'Hoaks/Penipuan', label: 'Hoaks' },
]

export default function OverviewPage() {
  const filters = useFilters()
  const navigate = useNavigate()
  const [grain, setGrain] = useState<'day' | 'week' | 'month'>('day')
  const [picked, setPicked] = useState<AdviceItem | null>(null)
  const overview = useApi<Overview>(`/api/overview?${filters.query}`)
  const latest = useApi<{ items: MentionCard[] }>(`/api/mentions?page_size=16&sort=terbaru&${filters.query}`)
  const popular = useApi<{ items: MentionCard[] }>(`/api/mentions?page_size=6&sort=jangkauan&${filters.query}`)
  const extra = useApi<{ items: TrendPoint[] }>(grain === 'day' ? null : `/api/trend?granularity=${grain}&${filters.query}`)
  const advice = useApi<{ disclaimer: string; items: AdviceItem[] }>('/api/advices?top=3')

  const data = overview.data
  const stories = latest.data?.items || []
  const lead = stories[0]
  const side = stories.slice(1, 5)
  const trend = grain === 'day' ? data?.trend || [] : extra.data?.items || []
  const aktif = filters.category || 'semua'

  function openAll() {
    navigate('/explorer')
  }

  return (
    <div className="mx-auto max-w-6xl">
      <nav className="-mx-1 mb-4 flex gap-1 overflow-x-auto border-b-2 border-ink pb-1" aria-label="Rubrik">
        {RUBRIK.map((item) => {
          const on = aktif === item.id
          return (
            <button
              key={item.id}
              aria-current={on ? 'page' : undefined}
              className={`shrink-0 px-3 py-2 text-sm font-bold uppercase tracking-wide ${on ? 'bg-ink text-card' : 'hover:underline'}`}
              onClick={() => filters.setCategory(item.id)}
            >
              {item.label}
            </button>
          )
        })}
      </nav>

      {data && (
        <p className="mb-4 text-sm">
          <span className="font-bold uppercase tracking-wide">Situasi</span>
          {' · '}
          {formatNumber(data.kpis.total_mention.value)} berita
          {' · '}
          positif {formatPct(data.kpis.sentiment_pct.positif)}, netral {formatPct(data.kpis.sentiment_pct.netral)}, negatif {formatPct(data.kpis.sentiment_pct.negatif)}
          {data.active_alerts.length > 0 ? ` · ${data.active_alerts.length} alert` : ''}
        </p>
      )}

      {(latest.loading || overview.loading) && <Loading />}
      {(latest.error || overview.error) && <ErrorNote message={latest.error || overview.error} />}

      {!latest.loading && stories.length === 0 && (
        <Empty label="Belum ada berita pada rubrik dan rentang ini. Pilih Beranda atau perlebar tanggal." />
      )}

      {lead && (
        <div className="grid gap-6 border-b border-ink pb-6 lg:grid-cols-[minmax(0,1fr)_17rem]">
          <div>
            <Story item={lead} lead />
            <div className="mt-4 grid gap-4 border-t border-line pt-4 sm:grid-cols-2">
              {side.map((item) => <Story key={item.id} item={item} />)}
            </div>
          </div>
          <aside aria-label="Terpopuler">
            <SectionHead title="Terpopuler" />
            <ol className="divide-y divide-line">
              {(popular.data?.items || []).map((item, index) => (
                <li key={item.id} className="flex gap-3 py-3">
                  <span className="w-8 shrink-0 text-2xl font-bold leading-none tabular-nums text-red-700">{String(index + 1).padStart(2, '0')}</span>
                  <Story item={item} compact />
                </li>
              ))}
            </ol>
            {popular.data && popular.data.items.length === 0 && <p className="text-sm text-muted">Belum ada berita dengan jangkauan pada rentang ini.</p>}
          </aside>
        </div>
      )}

      {data && (
        <section className="border-b border-ink py-6" aria-label="Perkembangan volume">
          <SectionHead title="Perkembangan" />
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-muted">Klik satu hari untuk menyaring berita pada tanggal itu.</p>
            <div className="flex gap-1">
              {(['day', 'week', 'month'] as const).map((item) => (
                <button key={item} className={`h-8 px-2 text-xs font-bold uppercase ${grain === item ? 'bg-ink text-card' : 'border border-line'}`} onClick={() => setGrain(item)}>
                  {item === 'day' ? 'Harian' : item === 'week' ? 'Mingguan' : 'Bulanan'}
                </button>
              ))}
            </div>
          </div>
          <BackToGeneral />
          {trend.length === 0 ? <Empty label="Belum ada percakapan pada rentang ini." /> : <TrendChart className="h-56" data={trend} onPick={(day) => { if (grain === 'day') filters.focusDay(day, '/') }} />}
          <ChartInsight chart="trend" granularity={grain} className="mt-2" />
        </section>
      )}

      {stories.length > 0 && (
        <section className="border-b border-ink py-6" aria-label="Berita utama">
          <SectionHead title="Berita utama" actionLabel="Lihat semua" onAction={openAll} />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {stories.slice(0, 8).map((item) => <Story key={item.id} item={item} />)}
          </div>
        </section>
      )}

      {stories.length > 0 && (
        <section className="border-b border-ink py-6" aria-label="Terbaru">
          <SectionHead title="Terbaru" actionLabel="Lihat lebih banyak" onAction={openAll} />
          <ul className="divide-y divide-line">
            {stories.map((item) => (
              <li key={item.id} className="grid gap-1 py-3 sm:grid-cols-[8rem_minmax(0,1fr)] sm:items-baseline">
                <p className="text-xs font-bold uppercase tracking-wide text-red-700">{item.category}</p>
                <Story item={item} compact />
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="border-b border-ink py-6" aria-label="Untuk pimpinan">
        <SectionHead title="Untuk pimpinan" actionLabel="Lihat semua" onAction={() => navigate('/saran')} />
        {(advice.data?.items || []).length === 0 && <p className="text-sm text-muted">Belum ada rekomendasi dengan bukti pada siklus ini.</p>}
        <ul className="grid gap-4 md:grid-cols-3">
          {(advice.data?.items || []).map((item) => (
            <li key={item.id}>
              <button className="block w-full text-left" onClick={() => setPicked(item)}>
                <span className={`text-xs font-bold uppercase ${priorityOf(item.urgency).className}`}>{priorityOf(item.urgency).label}</span>
                <span className="mt-1 block text-lg font-bold leading-snug hover:underline">{item.title}</span>
                <span className="mt-1 block text-sm text-muted">{item.unit}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="py-6" aria-label="Fokus isu">
        <ExecutivePage />
      </section>

      {picked && <RecommendationDrawer item={picked} disclaimer={advice.data?.disclaimer || ''} onClose={() => setPicked(null)} onChanged={advice.reload} />}
    </div>
  )
}

function SectionHead({ title, actionLabel, onAction }: { title: string; actionLabel?: string; onAction?: () => void }) {
  return (
    <div className="mb-3 flex items-end justify-between gap-3 border-b-2 border-ink pb-1">
      <h2 className="text-sm font-bold uppercase tracking-[0.16em]">{title}</h2>
      {actionLabel && onAction && (
        <button className="text-xs font-bold uppercase tracking-wide hover:underline" onClick={onAction}>{actionLabel}</button>
      )}
    </div>
  )
}

function Story({ item, lead = false, compact = false }: { item: MentionCard; lead?: boolean; compact?: boolean }) {
  return (
    <article>
      {!compact && <p className="text-xs font-bold uppercase tracking-wide text-red-700">{item.category}</p>}
      <a
        className={`mt-1 block font-bold leading-snug hover:underline ${lead ? 'text-3xl md:text-4xl' : compact ? 'text-base' : 'text-lg'}`}
        href={item.url}
        target="_blank"
        rel="noreferrer"
      >
        <QuoteBadge show={item.quotes_bi} />
        {item.title}
      </a>
      <p className="mt-1 text-xs text-muted">
        {item.source_name} · {PLATFORM_LABEL[item.platform] || item.platform} · <time dateTime={item.published_at}>{relativeTime(item.published_at)}</time>
        {' · '}
        <StanceBadge stance={item.stance} />
      </p>
    </article>
  )
}
