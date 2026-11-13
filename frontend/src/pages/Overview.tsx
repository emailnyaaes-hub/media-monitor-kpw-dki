import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../api'
import { TrendChart } from '../components/Charts'
import BackToGeneral from '../components/BackToGeneral'
import ChartInsight from '../components/ChartInsight'
import MentionBrief from '../components/MentionBrief'
import { Empty, ErrorNote, Loading, QuoteBadge, StanceBadge } from '../components/Ui'
import { useFilters } from '../filters'
import { formatNumber, formatPct, isoDate, PLATFORM_LABEL, relativeTime } from '../format'
import type { MentionCard, Overview, TrendPoint } from '../types'

const RUBRIK = [
  { id: 'bi_nasional', label: 'Berita Nasional', hint: 'Bank Indonesia, moneter, rupiah, inflasi, keuangan daerah, QRIS, dan mandat BI.' },
  { id: 'kpw_dki', label: 'KPwBI DKI Jakarta', hint: 'KPw BI DKI Jakarta, program lokal, dan berita BI/Jakarta terkait (arsip hingga 1 tahun).' },
  { id: 'kpw_provinsi', label: 'KPwBI', hint: 'Kantor Perwakilan BI di luar DKI — Jawa, Sumatera, Bali, Sulawesi, dan lainnya (arsip hingga 1 tahun).' },
  { id: 'pemprov_dki', label: 'Pemprov DKI Jakarta', hint: 'Pemprov DKI, Balai Kota, Diskominfo, Smart City, dan pejabat daerah (arsip hingga 1 tahun).' },
] as const

export default function OverviewPage() {
  const filters = useFilters()
  const navigate = useNavigate()
  const [rubrik, setRubrik] = useState<(typeof RUBRIK)[number]['id']>('bi_nasional')
  const [grain, setGrain] = useState<'day' | 'week' | 'month'>('day')
  // Rubrik tematik: tampilkan arsip hingga 1 tahun agar section tidak kosong.
  const mentionQuery = (() => {
    const params = new URLSearchParams(filters.query)
    params.set('feed_section', rubrik)
    const end = new Date()
    const start = new Date()
    start.setFullYear(end.getFullYear() - 1)
    params.set('date_from', isoDate(start))
    params.set('date_to', isoDate(end))
    return params.toString()
  })()
  const overview = useApi<Overview>(`/api/overview?${filters.query}`)
  const latest = useApi<{ items: MentionCard[] }>(`/api/mentions?page_size=16&sort=terbaru&${mentionQuery}`)
  const extra = useApi<{ items: TrendPoint[] }>(grain === 'day' ? null : `/api/trend?granularity=${grain}&${filters.query}`)

  const data = overview.data
  const stories = latest.data?.items || []
  const lead = stories[0]
  const side = stories.slice(1, 5)
  const trend = grain === 'day' ? data?.trend || [] : extra.data?.items || []
  const aktif = rubrik
  const rubrikMeta = RUBRIK.find((item) => item.id === rubrik) ?? RUBRIK[0]

  function openAll() {
    navigate(`/explorer?feed_section=${encodeURIComponent(rubrik)}`)
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
              onClick={() => setRubrik(item.id)}
            >
              {item.label}
            </button>
          )
        })}
      </nav>
      <p className="-mt-2 mb-4 text-xs text-muted">{rubrikMeta.hint}</p>

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
        <Empty label={`Belum ada berita pada rubrik «${rubrikMeta.label}». Perlebar tanggal atau jalankan retag bila data lama.`} />
      )}

      {lead && (
        <div className="border-b border-ink pb-6">
          <Story item={lead} lead />
          <div className="mt-4 grid gap-4 border-t border-line pt-4 sm:grid-cols-2">
            {side.map((item) => <Story key={item.id} item={item} />)}
          </div>
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
        <section className="py-6" aria-label="Terbaru">
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
      {!compact && (
        <p className="text-xs font-bold uppercase tracking-wide text-red-700">
          {item.feed_section_label && item.feed_section !== 'beranda' ? item.feed_section_label : item.category}
        </p>
      )}
      <a
        className={`mt-1 block font-bold leading-snug hover:underline ${lead ? 'text-3xl md:text-4xl' : compact ? 'text-base' : 'text-lg'}`}
        href={item.url}
        target="_blank"
        rel="noreferrer"
      >
        <QuoteBadge show={item.quotes_bi} />
        {item.title}
      </a>
      <MentionBrief text={item.brief} />
      <p className="mt-1 text-xs text-muted">
        {item.source_name} · {PLATFORM_LABEL[item.platform] || item.platform} · <time dateTime={item.published_at}>{relativeTime(item.published_at)}</time>
        {' · '}
        <StanceBadge stance={item.stance} />
      </p>
    </article>
  )
}
