import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../api'
import type { AdviceItem } from '../components/AdviceCard'
import { TrendChart } from '../components/Charts'
import { Card, Empty, ErrorNote, Help, Loading, PageHeader, QuoteBadge, RiskBar, SentimentBadge, SourceLink, StanceBadge } from '../components/Ui'
import { useFilters } from '../filters'
import { formatNumber, formatPct, formatReach, formatSigned, PLATFORM_LABEL, relativeTime } from '../format'
import type { IssueCard, Overview, TrendPoint } from '../types'
import { AlertTriangle, Check, Minus } from 'lucide-react'

export default function OverviewPage() {
  const filters = useFilters()
  const navigate = useNavigate()
  const [grain, setGrain] = useState<'day' | 'week' | 'month'>('day')
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

  return (
    <div>
      <PageHeader title="Ringkasan" description="Apa yang terjadi, isu mana yang utama, dan tindakan yang bisa ditinjau." />
      {overview.loading && <Loading />}
      {overview.error && <ErrorNote message={overview.error} />}
      {data && (
        <>
          <p className={`mb-4 flex items-start gap-2 border px-3 py-3 text-base ${level === 'Waspada' ? 'border-red-300 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-100' : level === 'Perlu dipantau' ? 'border-amber-300 bg-amber-50 text-amber-950 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-100' : 'border-emerald-300 bg-emerald-50 text-emerald-950 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-100'}`}>
            {level === 'Tenang' ? <Check size={18} aria-hidden /> : level === 'Perlu dipantau' ? <Minus size={18} aria-hidden /> : <AlertTriangle size={18} aria-hidden />}
            <span>{situation}</span>
          </p>
          <section>
            <h2 className="font-serif text-xl">Perlu perhatian sekarang</h2>
            {attention.length === 0 && <Empty label="Belum ada isu pada filter ini. Coba perluas rentang tanggal." />}
            <ul className="mt-2 divide-y divide-line border-y border-line">
              {attention.map((issue) => (
                <li key={issue.id} className="flex flex-wrap items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-2 text-base font-medium">{issue.title}</p>
                    <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted">
                      <StanceBadge stance={issue.stance} />
                      <span>{issue.mention_count} sumber</span>
                      <span>{issue.category}</span>
                    </p>
                  </div>
                  <span className="text-sm" title="Skor risiko menggabungkan nada, kecepatan sebar, dan kredibilitas sumber. Bukan keputusan.">
                    Risiko <RiskBar score={issue.risk_score} />
                  </span>
                  <button className="h-11 rounded-md bg-navy-900 px-3 text-sm text-white" onClick={() => navigate(`/isu/${issue.id}`)}>Lihat</button>
                </li>
              ))}
            </ul>
          </section>
          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric label="Total mention" value={formatNumber(data.kpis.total_mention.value)} note="Konten unik pada periode." delta={data.kpis.total_mention.delta_pct} />
            <div className="border border-line bg-card p-4">
              <p className="text-sm text-muted">Komposisi sentimen</p>
              <ul className="mt-2 space-y-1 text-base">
                <li><SentimentBadge sentiment="positif" /> {formatPct(data.kpis.sentiment_pct.positif)}</li>
                <li><SentimentBadge sentiment="netral" /> {formatPct(data.kpis.sentiment_pct.netral)}</li>
                <li><SentimentBadge sentiment="negatif" /> {formatPct(data.kpis.sentiment_pct.negatif)}</li>
              </ul>
            </div>
            <Metric
              label="Sentimen bersih"
              value={formatNumber(data.kpis.net_sentiment.value)}
              note="Persen positif dikurangi persen negatif."
              help="Angka positif berarti porsi upside lebih besar daripada downside."
              delta={data.kpis.net_sentiment.delta_points}
              suffix=""
            />
            <Metric label="Isu kritis" value={formatNumber(data.kpis.critical_issues.value)} note="Isu berisiko tinggi yang belum selesai." delta={data.kpis.critical_issues.delta_pct} good="down" />
          </div>
          <section className="mt-6 border border-line bg-card p-4">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-serif text-xl">{trendTitle}</h2>
              <div className="flex gap-1">
                {(['day', 'week', 'month'] as const).map((item) => (
                  <button key={item} className={`h-11 rounded-md px-3 text-sm ${grain === item ? 'bg-navy-900 text-white' : 'border border-line'}`} onClick={() => setGrain(item)}>
                    {item === 'day' ? 'Harian' : item === 'week' ? 'Mingguan' : 'Bulanan'}
                  </button>
                ))}
              </div>
            </div>
            <p className="mb-2 text-sm text-muted">Klik satu hari untuk membuka berita pada tanggal itu.</p>
            <TrendChart data={trend} onPick={openDay} />
          </section>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <StoryPanel title="Upside" note={data.top_upside.window_label} items={data.top_upside.items} />
            <StoryPanel title="Downside" note={data.top_downside.window_label} items={data.top_downside.items} />
          </div>
          <section className="mt-6">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="font-serif text-xl">Saran tindakan</h2>
              <button className="text-base underline" onClick={() => navigate('/saran')}>Buka Pusat Saran</button>
            </div>
            <p className="mt-1 text-sm text-muted">Dihasilkan AI. {advice.data?.disclaimer}</p>
            <p className="text-sm text-muted">Saran diperbarui: {advice.data?.refreshed_at ? `${advice.data.refreshed_at} WIB` : 'belum ada'}.</p>
            <ul className="mt-2 divide-y divide-line border-y border-line">
              {(advice.data?.items || []).map((item) => (
                <li key={item.id} className="flex flex-wrap items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-muted">{item.kind_label} · urgensi {item.urgency} · keyakinan {item.confidence}</p>
                    <p className="line-clamp-2 text-base">{item.title}</p>
                    <p className="text-sm text-muted">{item.insufficient ? 'Data belum cukup, perlu verifikasi.' : item.recommendation}</p>
                  </div>
                  <button className="h-11 rounded-md border border-line px-3 text-sm" onClick={() => navigate('/saran')}>Tinjau</button>
                </li>
              ))}
              {advice.data && advice.data.items.length === 0 && <li className="py-3 text-base text-muted">Belum ada saran dengan bukti pada siklus ini.</li>}
            </ul>
          </section>
        </>
      )}
    </div>
  )
}

function Metric({ label, value, note, help, delta, suffix = '%', good = 'neutral' }: { label: string; value: string; note: string; help?: string; delta?: number | null; suffix?: string; good?: 'up' | 'down' | 'neutral' }) {
  return (
    <div className="border border-line bg-card p-4">
      <p className="text-sm text-muted">{label}{help && <Help text={help} />}</p>
      <p className="mt-1 text-3xl font-medium tabular-nums">{value}</p>
      <p className="mt-1 text-sm text-muted">{delta == null ? 'Tidak ada pembanding' : `${formatSigned(delta, suffix)} vs periode lalu`}</p>
      <p className="mt-1 text-sm text-muted">{note}{good === 'down' ? '' : ''}</p>
    </div>
  )
}

function StoryPanel({ title, note, items }: { title: string; note: string; items: Overview['top_upside']['items'] }) {
  const navigate = useNavigate()
  return (
    <Card>
      <h2 className="font-serif text-xl">{title}</h2>
      <p className="text-sm text-muted">{note}</p>
      {items.length === 0 && <Empty label="Belum ada berita pada jendela ini." />}
      <ul className="mt-2 divide-y divide-line">
        {items.map((item) => (
          <li key={item.id} className="py-3">
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
