import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../api'
import type { AdviceItem } from '../components/AdviceCard'
import { Donut, VolumeChart } from '../components/Charts'
import { Card, Empty, ErrorNote, Help, Loading, QuoteBadge, RiskBar, SourceLink, StanceBadge } from '../components/Ui'
import { useFilters } from '../filters'
import { formatDay, formatNumber, formatPct, formatReach, formatSigned, PLATFORM_LABEL, relativeTime } from '../format'
import type { IssueCard, Overview, TrendPoint } from '../types'
import { AlertTriangle, ArrowDown, ArrowUp, Check, Minus } from 'lucide-react'

export default function OverviewPage() {
  const filters = useFilters()
  const navigate = useNavigate()
  const [grain, setGrain] = useState<'day' | 'week' | 'month'>('day')
  const [tab, setTab] = useState<'perhatian' | 'grafik' | 'komposisi' | 'saran'>('perhatian')
  const overview = useApi<Overview>(`/api/overview?${filters.query}`)
  const issues = useApi<{ items: IssueCard[] }>(`/api/issues?${filters.query}`)
  const advice = useApi<{ refreshed_at: string | null; disclaimer: string; items: AdviceItem[] }>('/api/advices?top=3')
  const extra = useApi<{ items: TrendPoint[] }>(grain === 'day' ? null : `/api/trend?granularity=${grain}&${filters.query}`)
  const data = overview.data
  const trend = grain === 'day' ? data?.trend || [] : extra.data?.items || []
  const attention = [...(issues.data?.items || data?.critical_issue_list || [])]
    .sort((a, b) => b.risk_score - a.risk_score)
    .slice(0, 5)

  function openDay(day: string) {
    if (grain !== 'day') return
    filters.setDateFrom(day)
    filters.setDateTo(day)
    navigate('/explorer')
  }

  const critical = data?.kpis.critical_issues.value || 0
  const level = critical > 0 ? 'Waspada' : (data?.kpis.sentiment_pct.negatif || 0) >= 25 ? 'Perlu dipantau' : 'Tenang'
  const situation = !data
    ? ''
    : critical > 0
      ? `Situasi: ${level}. ${formatNumber(critical)} isu perlu perhatian pada rentang ini.`
      : `Situasi: ${level}. Tidak ada isu kritis terbuka pada rentang ini.`
  const volumeDelta = data?.kpis.total_mention.delta_pct
  const trendTitle = volumeDelta == null
    ? 'Volume mention pada rentang ini'
    : `Volume mention ${volumeDelta >= 0 ? 'naik' : 'turun'} ${formatPct(Math.abs(volumeDelta))} dibanding periode sebelumnya`

  const tabs = [
    ['perhatian', 'Perlu perhatian'],
    ['grafik', 'Grafik'],
    ['komposisi', 'Komposisi'],
    ['saran', 'Saran'],
  ] as const

  return (
    <div className="flex flex-col gap-2 md:h-[calc(100dvh-12.5rem)] md:overflow-hidden">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-base font-medium">Ringkasan</h1>
        {data && (
          <p className={`inline-flex items-center gap-2 border px-2 py-1 text-sm ${level === 'Waspada' ? 'border-red-300 bg-red-50 text-red-900' : level === 'Perlu dipantau' ? 'border-amber-300 bg-amber-50 text-amber-950' : 'border-emerald-300 bg-emerald-50 text-emerald-950'}`}>
            {level === 'Tenang' ? <Check size={14} aria-hidden /> : level === 'Perlu dipantau' ? <Minus size={14} aria-hidden /> : <AlertTriangle size={14} aria-hidden />}
            {situation}
          </p>
        )}
      </div>
      {overview.loading && <Loading />}
      {overview.error && <ErrorNote message={overview.error} />}
      {data && (
        <>
          <div className="grid grid-cols-2 gap-2 xl:grid-cols-4">
            <Metric label="Total mention" value={formatNumber(data.kpis.total_mention.value)} delta={data.kpis.total_mention.delta_pct} />
            <Metric label="Sentimen bersih" value={formatNumber(data.kpis.net_sentiment.value)} delta={data.kpis.net_sentiment.delta_points} suffix="" help="Persen positif dikurangi persen negatif." />
            <Metric label="Isu kritis" value={formatNumber(data.kpis.critical_issues.value)} delta={data.kpis.critical_issues.delta_pct} />
            <button className="border border-line bg-card px-3 py-2 text-left" onClick={() => setTab('komposisi')}>
              <p className="text-xs text-muted">Komposisi sentimen</p>
              <p className="mt-1 text-sm">positif {formatPct(data.kpis.sentiment_pct.positif)} · netral {formatPct(data.kpis.sentiment_pct.netral)} · negatif {formatPct(data.kpis.sentiment_pct.negatif)}</p>
            </button>
          </div>
          <div className="flex gap-1 border-b border-line">
            {tabs.map(([id, label]) => (
              <button key={id} className={`h-9 px-3 text-sm ${tab === id ? 'border-b-2 border-navy-900 font-medium' : 'text-muted'}`} onClick={() => setTab(id)}>
                {label}
              </button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-hidden">
            {tab === 'perhatian' && (
              <section className="h-full overflow-auto">
                {attention.length === 0 && <Empty label="Belum ada isu pada filter ini. Coba perluas rentang tanggal." />}
                <ul className="divide-y divide-line border-y border-line">
                  {attention.map((issue) => (
                    <li key={issue.id} className="flex items-center gap-3 py-2">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">{issue.title}</p>
                        <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
                          <StanceBadge stance={issue.stance} />
                          <span>{issue.mention_count} sumber</span>
                          <span>{issue.category}</span>
                        </p>
                      </div>
                      <span className="hidden text-sm sm:inline" title="Skor risiko menggabungkan nada, kecepatan sebar, dan kredibilitas sumber. Bukan keputusan.">
                        Risiko <RiskBar score={issue.risk_score} />
                      </span>
                      <button className="h-9 shrink-0 rounded-md bg-navy-900 px-3 text-sm text-white" onClick={() => navigate(`/isu/${issue.id}`)}>Lihat</button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {tab === 'grafik' && (
              <div className="grid h-full min-h-[16rem] gap-2 lg:grid-cols-5">
                <section className="flex min-h-0 flex-col border border-line bg-card p-3 lg:col-span-3">
                  <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                    <h2 className="text-sm font-medium">{trendTitle}</h2>
                    <div className="flex gap-1">
                      {(['day', 'week', 'month'] as const).map((item) => (
                        <button key={item} className={`h-8 rounded-md px-2 text-xs ${grain === item ? 'bg-navy-900 text-white' : 'border border-line'}`} onClick={() => setGrain(item)}>
                          {item === 'day' ? 'Harian' : item === 'week' ? 'Mingguan' : 'Bulanan'}
                        </button>
                      ))}
                    </div>
                  </div>
                  <p className="mb-1 text-xs text-muted">Klik satu hari untuk membuka berita pada tanggal itu.</p>
                  {trend.length === 0 ? <Empty label="Belum ada mention pada rentang ini." /> : <VolumeChart className="h-52 min-h-0 flex-1 lg:h-auto" data={trend} onPick={openDay} />}
                </section>
                <CategoryShift rows={data.category_shift} />
              </div>
            )}
            {tab === 'komposisi' && (
              <div className="grid h-full min-h-0 gap-2 overflow-auto lg:grid-cols-2">
                <section className="border border-line bg-card p-3">
                  <h2 className="text-sm font-medium">Komposisi kini dan periode lalu</h2>
                  <Donut positif={data.kpis.sentiment_pct.positif} netral={data.kpis.sentiment_pct.netral} negatif={data.kpis.sentiment_pct.negatif} />
                  <div className="space-y-3">
                    <ShareBar label={`${formatDay(data.period.from)}–${formatDay(data.period.to)}`} positif={data.kpis.sentiment_pct.positif} netral={data.kpis.sentiment_pct.netral} negatif={data.kpis.sentiment_pct.negatif} />
                    <ShareBar label={`${formatDay(data.previous_period.from)}–${formatDay(data.previous_period.to)}`} positif={data.kpis.sentiment_pct.previous.positif} netral={data.kpis.sentiment_pct.previous.netral} negatif={data.kpis.sentiment_pct.previous.negatif} />
                  </div>
                  <p className="mt-2 text-xs text-muted">Pembanding nasional dan provinsi lain: [data perlu dilengkapi].</p>
                </section>
                <AreaBars areas={data.areas} />
              </div>
            )}
            {tab === 'saran' && (
              <div className="grid h-full min-h-0 gap-2 overflow-auto lg:grid-cols-2">
                <section className="border border-line bg-card p-3">
                  <div className="flex items-baseline justify-between gap-2">
                    <h2 className="text-sm font-medium">Saran tindakan</h2>
                    <button className="text-sm underline" onClick={() => navigate('/saran')}>Buka Pusat Saran</button>
                  </div>
                  <p className="text-xs text-muted">{advice.data?.disclaimer}</p>
                  <ul className="mt-2 divide-y divide-line">
                    {(advice.data?.items || []).map((item) => (
                      <li key={item.id} className="flex items-center gap-2 py-2">
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm">{item.title}</p>
                          <p className="truncate text-xs text-muted">{item.insufficient ? 'Data belum cukup, perlu verifikasi.' : item.recommendation}</p>
                        </div>
                        <button className="h-8 shrink-0 rounded-md border border-line px-2 text-xs" onClick={() => navigate('/saran')}>Tinjau</button>
                      </li>
                    ))}
                    {advice.data && advice.data.items.length === 0 && <li className="py-2 text-sm text-muted">Belum ada saran dengan bukti pada siklus ini.</li>}
                  </ul>
                </section>
                <div className="grid min-h-0 gap-2">
                  <StoryPanel title="Upside" note={data.top_upside.window_label} items={data.top_upside.items.slice(0, 3)} />
                  <StoryPanel title="Downside" note={data.top_downside.window_label} items={data.top_downside.items.slice(0, 3)} />
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

function Metric({ label, value, help, delta, suffix = '%' }: { label: string; value: string; help?: string; delta?: number | null; suffix?: string }) {
  return (
    <div className="border border-line bg-card px-3 py-2">
      <p className="text-xs text-muted">{label}{help && <Help text={help} />}</p>
      <p className="text-xl font-medium tabular-nums">{value}</p>
      <p className="flex items-center gap-1 text-xs text-muted">
        {delta == null ? 'Tidak ada pembanding' : <><Direction delta={delta} />{formatSigned(delta, suffix)} vs periode lalu</>}
      </p>
    </div>
  )
}

function Direction({ delta }: { delta: number }) {
  if (delta > 0) return <ArrowUp size={14} aria-hidden />
  if (delta < 0) return <ArrowDown size={14} aria-hidden />
  return <Minus size={14} aria-hidden />
}

function CategoryShift({ rows }: { rows: Overview['category_shift'] }) {
  const shown = rows.slice(0, 6)
  const max = Math.max(1, ...shown.map((item) => Math.abs(item.delta)))
  const mover = shown.find((item) => item.delta !== 0)
  const title = mover
    ? `${mover.category} mengubah volume paling besar (${formatSigned(mover.delta)} mention)`
    : 'Volume per kategori tidak berubah dibanding periode lalu'
  return (
    <section className="flex min-h-0 flex-col overflow-auto border border-line bg-card p-3 lg:col-span-2">
      <h2 className="text-sm font-medium">{title}</h2>
      <p className="mt-1 text-xs text-muted">Selisih jumlah mention dibanding jendela sebelumnya.</p>
      <ul className="mt-2 space-y-2">
        {shown.length === 0 && <li className="text-sm text-muted">Belum ada kategori pada rentang ini.</li>}
        {shown.map((item) => {
          const width = `${(Math.abs(item.delta) / max) * 50}%`
          return (
            <li key={item.category} className="grid grid-cols-[1fr_4.5rem] items-center gap-2 text-sm">
              <span className="min-w-0">
                <span className="block truncate">{item.category}</span>
                <span className="relative mt-1 block h-2 bg-line" aria-hidden>
                  <span className="absolute top-0 h-2 bg-navy-800" style={item.delta >= 0 ? { left: '50%', width } : { right: '50%', width }} />
                </span>
              </span>
              <span className="text-right tabular-nums">{formatSigned(item.delta)}</span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

function ShareBar({ label, positif, netral, negatif }: { label: string; positif: number; netral: number; negatif: number }) {
  return (
    <div>
      <p className="text-sm">{label}</p>
      <div className="mt-1 flex h-3" aria-hidden>
        <div className="bg-emerald-700" style={{ width: `${positif}%` }} />
        <div className="bg-slate-400" style={{ width: `${netral}%` }} />
        <div className="bg-red-700" style={{ width: `${negatif}%` }} />
      </div>
      <p className="mt-1 text-sm text-muted">positif {formatPct(positif)} · netral {formatPct(netral)} · negatif {formatPct(negatif)}</p>
    </div>
  )
}

function AreaBars({ areas }: { areas: Overview['areas'] }) {
  const max = Math.max(1, ...areas.map((item) => item.count))
  return (
    <section className="border border-line bg-card p-3">
      <h2 className="text-sm font-medium">Sebaran mention wilayah administrasi</h2>
      <p className="mt-1 text-sm text-muted">Jumlah mention yang menyebut nama wilayah. Bukan peta batas resmi.</p>
      <ul className="mt-3 space-y-2">
        {areas.map((area) => (
          <li key={area.name} className="grid grid-cols-[9rem_1fr_2.5rem] items-center gap-2 text-sm">
            <span className="truncate">{area.name}</span>
            <span className="h-2 bg-line" aria-hidden>
              <span className="block h-2 bg-navy-800" style={{ width: `${(area.count / max) * 100}%` }} />
            </span>
            <span className="text-right tabular-nums">{formatNumber(area.count)}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function StoryPanel({ title, note, items }: { title: string; note: string; items: Overview['top_upside']['items'] }) {
  const navigate = useNavigate()
  return (
    <Card>
      <h2 className="text-sm font-medium">{title}</h2>
      <p className="text-xs text-muted">{note}</p>
      {items.length === 0 && <Empty label="Belum ada berita pada jendela ini." />}
      <ul className="mt-1 divide-y divide-line">
        {items.map((item) => (
          <li key={item.id} className="py-2">
            <button className="block text-left" onClick={() => navigate(`/explorer?m=${item.id}`)}>
              <span className="text-sm text-muted" title={item.published_at}>{item.source_name} · {PLATFORM_LABEL[item.platform] || item.platform} · {relativeTime(item.published_at)}</span>
              <span className="mt-1 line-clamp-2 flex items-start gap-2 text-base"><QuoteBadge show={item.quotes_bi} />{item.title}</span>
            </button>
            <p className="text-sm text-muted">Jangkauan {formatReach(item.reach_estimate)}</p>
            <SourceLink url={item.url} />
          </li>
        ))}
      </ul>
    </Card>
  )
}
