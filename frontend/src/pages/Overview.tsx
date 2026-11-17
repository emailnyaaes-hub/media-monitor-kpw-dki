import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../api'
import { TrendChart } from '../components/Charts'
import BackToGeneral from '../components/BackToGeneral'
import ChartInsight from '../components/ChartInsight'
import MentionBrief from '../components/MentionBrief'
import { Empty, ErrorNote, QuoteBadge, SkeletonFeed, StanceBadge } from '../components/Ui'
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
    <div className="mx-auto max-w-6xl pb-16 md:pb-0">
      <nav className="mb-3 flex gap-1 overflow-x-auto border-b border-ink" aria-label="Kanal rubrik">
        {RUBRIK.map((item) => {
          const on = aktif === item.id
          return (
            <button
              key={item.id}
              aria-current={on ? 'page' : undefined}
              className="kanal-tab"
              onClick={() => setRubrik(item.id)}
            >
              {item.label}
            </button>
          )
        })}
      </nav>
      <p className="reveal mb-5 max-w-3xl text-sm text-muted">{rubrikMeta.hint}</p>

      {data && (
        <p className="reveal reveal-delay-1 mb-5 text-sm">
          <span className="font-bold uppercase tracking-[0.14em]">Situasi</span>
          <span className="text-muted"> · </span>
          {formatNumber(data.kpis.total_mention.value)} berita
          <span className="text-muted"> · </span>
          positif {formatPct(data.kpis.sentiment_pct.positif)}, netral {formatPct(data.kpis.sentiment_pct.netral)}, negatif {formatPct(data.kpis.sentiment_pct.negatif)}
          {data.active_alerts.length > 0 ? ` · ${data.active_alerts.length} alert` : ''}
        </p>
      )}

      {(latest.loading || overview.loading) && <SkeletonFeed />}
      {(latest.error || overview.error) && <ErrorNote message={latest.error || overview.error} />}

      {!latest.loading && stories.length === 0 && (
        <Empty
          label={`Belum ada berita pada kanal «${rubrikMeta.label}».`}
          hint="Perlebar tanggal di header, atau tekan Perbarui bila data lama."
        />
      )}

      {lead && (
        <div key={rubrik} className="surface-section reveal">
          <Story item={lead} lead />
          <div className="mt-6 grid gap-5 border-t border-line pt-5 sm:grid-cols-2">
            {side.map((item, index) => (
              <div key={item.id} className={`reveal reveal-delay-${Math.min(index + 1, 3)}`}>
                <Story item={item} />
              </div>
            ))}
          </div>
        </div>
      )}

      {data && (
        <section className="surface-section" aria-label="Perkembangan volume">
          <SectionHead title="Perkembangan" />
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-muted">Klik satu hari untuk menyaring berita pada tanggal itu.</p>
            <div className="flex gap-1">
              {(['day', 'week', 'month'] as const).map((item) => (
                <button key={item} className={`h-8 px-2.5 text-xs font-bold uppercase tracking-wide ${grain === item ? 'bg-ink text-card' : 'border border-line hover:bg-line/30'}`} onClick={() => setGrain(item)}>
                  {item === 'day' ? 'Harian' : item === 'week' ? 'Mingguan' : 'Bulanan'}
                </button>
              ))}
            </div>
          </div>
          <BackToGeneral />
          {trend.length === 0 ? (
            <Empty label="Belum ada percakapan pada rentang ini." hint="Ubah filter tanggal atau platform." />
          ) : (
            <div className="chart-enter surface mt-2 p-2">
              <TrendChart className="h-56" data={trend} onPick={(day) => { if (grain === 'day') filters.focusDay(day, '/') }} />
            </div>
          )}
          <ChartInsight chart="trend" granularity={grain} className="mt-3" />
        </section>
      )}

      {stories.length > 0 && (
        <section className="surface-section" aria-label="Berita utama">
          <SectionHead title="Berita utama" actionLabel="Lihat semua" onAction={openAll} />
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {stories.slice(0, 8).map((item) => <Story key={item.id} item={item} />)}
          </div>
        </section>
      )}

      {stories.length > 0 && (
        <section className="py-6" aria-label="Terbaru">
          <SectionHead title="Terbaru" actionLabel="Lihat lebih banyak" onAction={openAll} />
          <ul className="divide-y divide-line">
            {stories.map((item) => (
              <li key={item.id} className="grid gap-1 py-3.5 sm:grid-cols-[8.5rem_minmax(0,1fr)] sm:items-baseline">
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
    <div className="mb-3 flex items-end justify-between gap-3 border-b border-ink pb-1.5">
      <h2 className="text-sm font-bold uppercase tracking-[0.16em]">{title}</h2>
      {actionLabel && onAction && (
        <button className="text-xs font-bold uppercase tracking-wide text-muted hover:text-ink hover:underline" onClick={onAction}>{actionLabel}</button>
      )}
    </div>
  )
}

function Story({ item, lead = false, compact = false }: { item: MentionCard; lead?: boolean; compact?: boolean }) {
  return (
    <article>
      {!compact && (
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-red-700">
          {item.feed_section_label && item.feed_section !== 'beranda' ? item.feed_section_label : item.category}
        </p>
      )}
      <a
        className={`mt-1.5 block font-extrabold leading-snug hover:underline ${lead ? 'hero-title' : compact ? 'text-base font-bold' : 'text-lg'}`}
        href={item.url}
        target="_blank"
        rel="noreferrer"
      >
        <QuoteBadge show={item.quotes_bi} />
        {item.title}
      </a>
      {!compact && <MentionBrief text={item.brief} compact={!lead} />}
      <p className="mt-2 text-xs text-muted">
        {item.source_name} · {PLATFORM_LABEL[item.platform] || item.platform} · <time dateTime={item.published_at}>{relativeTime(item.published_at)}</time>
        {' · '}
        <StanceBadge stance={item.stance} />
      </p>
    </article>
  )
}
