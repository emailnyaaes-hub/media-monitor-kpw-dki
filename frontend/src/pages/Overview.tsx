import { useEffect, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../api'
import type { AdviceItem } from '../components/AdviceCard'
import { priorityOf } from '../components/AdviceCard'
import { Donut, TrendChart } from '../components/Charts'
import BackToGeneral from '../components/BackToGeneral'
import ChartInsight from '../components/ChartInsight'
import RecommendationDrawer from '../components/RecommendationDrawer'
import { Card, Empty, ErrorNote, Loading, QuoteBadge, RiskBar, SourceLink, StanceBadge } from '../components/Ui'
import { useFilters } from '../filters'
import { formatNumber, formatPct, formatReach, formatSigned, PLATFORM_LABEL, relativeTime } from '../format'
import type { IssueCard, Overview, TrendPoint } from '../types'
import { AlertTriangle, ArrowDown, ArrowUp, Check, Minus } from 'lucide-react'

export default function OverviewPage() {
  const filters = useFilters()
  const navigate = useNavigate()
  const [grain, setGrain] = useState<'day' | 'week' | 'month'>('day')
  const [panel, setPanel] = useState<null | 'komposisi' | 'volume' | 'alert' | 'contoh'>(null)
  const [issue, setIssue] = useState<IssueCard | null>(null)
  const [picked, setPicked] = useState<AdviceItem | null>(null)
  const [tour, setTour] = useState(() => localStorage.getItem('bi-rek-tour') !== '1')
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
    filters.focusDay(day, '/')
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

  const alerts = data?.active_alerts || []
  const suggestions = advice.data?.items || []

  return (
    <div className="flex flex-col gap-2 md:h-[calc(100dvh-12.5rem)] md:overflow-y-auto">
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
          {tour && (
            <div className="flex flex-wrap items-center gap-3 border border-line bg-card px-3 py-2 text-sm">
              <p>1. Baca angka di atas. 2. Klik grafik atau isu untuk rincian. 3. Setujui, edit, atau abaikan rekomendasi. Keputusan tetap di pimpinan.</p>
              <button className="h-8 rounded-md border border-line px-2" onClick={() => { localStorage.setItem('bi-rek-tour', '1'); setTour(false) }}>Mengerti</button>
            </div>
          )}
          <div className="grid grid-cols-3 gap-2">
            <Metric label="Positif, netral, negatif" value={`${formatPct(data.kpis.sentiment_pct.positif)} / ${formatPct(data.kpis.sentiment_pct.netral)} / ${formatPct(data.kpis.sentiment_pct.negatif)}`} onClick={() => setPanel('komposisi')} />
            <Metric label="Volume percakapan" value={formatNumber(data.kpis.total_mention.value)} delta={data.kpis.total_mention.delta_pct} help="Jumlah berita dan unggahan pihak luar pada rentang ini." onClick={() => setPanel('volume')} />
            <Metric label="Alert aktif" value={formatNumber(alerts.length)} onClick={() => setPanel('alert')} />
          </div>
          <div className="grid flex-1 gap-2 lg:grid-cols-5">
            <section className="flex flex-col border border-line bg-card p-3 lg:col-span-3">
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
              <p className="mb-1 text-xs text-muted">Klik satu hari untuk menyaring berita pada tanggal itu. Segitiga menandai lonjakan.</p>
              <BackToGeneral />
              {trend.length === 0 ? <Empty label="Belum ada percakapan pada rentang ini." /> : <TrendChart className="h-52 min-h-0 flex-1 lg:h-auto lg:min-h-[16rem]" data={trend} onPick={openDay} />}
              <ChartInsight chart="trend" granularity={grain} className="mt-2 shrink-0" />
            </section>
            <div className="grid min-h-0 gap-2 lg:col-span-2">
              <section className="min-h-0 overflow-auto border border-line bg-card p-3">
                <h2 className="text-sm font-medium">Perlu perhatian sekarang</h2>
                {attention.length === 0 && <p className="mt-2 text-sm text-muted">Tidak ada isu pada filter ini.</p>}
                <ul className="mt-1 divide-y divide-line">
                  {attention.slice(0, 3).map((item) => (
                    <li key={item.id}>
                      <button className="w-full py-2 text-left" onClick={() => setIssue(item)}>
                        <span className="line-clamp-2 text-sm font-medium">{item.title}</span>
                        <span className="mt-1 flex items-center gap-2 text-xs text-muted"><StanceBadge stance={item.stance} />{item.mention_count} sumber</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
              <section className="min-h-0 overflow-auto border border-line bg-card p-3">
                <div className="flex items-baseline justify-between gap-2">
                  <h2 className="text-sm font-medium">Rekomendasi tindak lanjut</h2>
                  <span className="text-xs text-muted">Disusun otomatis</span>
                </div>
                {suggestions.length === 0 && <p className="mt-2 text-sm text-muted">Belum ada rekomendasi dengan bukti pada siklus ini.</p>}
                <ul className="mt-1 divide-y divide-line">
                  {suggestions.slice(0, 3).map((item) => (
                    <li key={item.id}>
                      <button className="flex w-full items-start gap-2 py-2 text-left" onClick={() => setPicked(item)}>
                        <span className={`mt-0.5 shrink-0 rounded-md border px-1.5 py-0.5 text-xs ${priorityOf(item.urgency).className}`}>{priorityOf(item.urgency).label}</span>
                        <span className="min-w-0">
                          <span className="line-clamp-2 block text-sm">{item.title}</span>
                          <span className="text-xs text-muted">{item.unit}</span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            </div>
          </div>
          {panel && (
            <Overlay title={panelTitle(panel)} onClose={() => setPanel(null)}>
              {panel === 'komposisi' && (
                <div>
                  <Donut positif={data.kpis.sentiment_pct.positif} netral={data.kpis.sentiment_pct.netral} negatif={data.kpis.sentiment_pct.negatif} />
                  <ShareBar label="Periode ini" positif={data.kpis.sentiment_pct.positif} netral={data.kpis.sentiment_pct.netral} negatif={data.kpis.sentiment_pct.negatif} />
                  <ShareBar label="Periode lalu" positif={data.kpis.sentiment_pct.previous.positif} netral={data.kpis.sentiment_pct.previous.netral} negatif={data.kpis.sentiment_pct.previous.negatif} />
                  <p className="mt-2 text-sm text-muted">Pembanding KPw daerah lain dan BI nasional: [data perlu dilengkapi].</p>
                  <ChartInsight chart="komposisi" className="mt-3" />
                </div>
              )}
              {panel === 'volume' && (
                <div>
                  <CategoryShift rows={data.category_shift} />
                  <ChartInsight chart="volume" className="mt-3" />
                </div>
              )}
              {panel === 'alert' && (
                <ul className="divide-y divide-line text-sm">
                  {alerts.length === 0 && <li className="py-2 text-muted">Tidak ada alert aktif.</li>}
                  {alerts.map((item) => (
                    <li key={item.id} className="py-2">
                      <p className="font-medium">{item.title}</p>
                      <p className="text-muted">{item.message}</p>
                      <button className="mt-1 underline" onClick={() => navigate('/alert')}>Buka alert</button>
                    </li>
                  ))}
                </ul>
              )}
              {panel === 'contoh' && (
                <div className="grid gap-3">
                  <StoryPanel title="Nada positif" note={data.top_upside.window_label} items={data.top_upside.items.slice(0, 3)} />
                  <StoryPanel title="Nada negatif" note={data.top_downside.window_label} items={data.top_downside.items.slice(0, 3)} />
                </div>
              )}
            </Overlay>
          )}
          {issue && (
            <Overlay title={issue.title} onClose={() => setIssue(null)}>
              <p className="flex flex-wrap items-center gap-2 text-sm"><StanceBadge stance={issue.stance} /><span>{issue.mention_count} sumber</span><span>{issue.category}</span></p>
              <p className="mt-2 text-sm">Risiko <RiskBar score={issue.risk_score} />. Skor ini menggabungkan nada, kecepatan sebar, dan kredibilitas sumber. Bukan keputusan.</p>
              <div className="mt-3 flex gap-2">
                <button className="h-10 rounded-md bg-navy-900 px-3 text-sm text-white" onClick={() => navigate(`/isu/${issue.id}`)}>Buka isu</button>
                <button className="h-10 rounded-md border border-line px-3 text-sm" onClick={() => { setIssue(null); setPanel('contoh') }}>Contoh pemberitaan</button>
              </div>
            </Overlay>
          )}
          {picked && <RecommendationDrawer item={picked} disclaimer={advice.data?.disclaimer || ''} onClose={() => setPicked(null)} onChanged={advice.reload} />}
        </>
      )}
    </div>
  )
}

function panelTitle(panel: 'komposisi' | 'volume' | 'alert' | 'contoh') {
  if (panel === 'komposisi') return 'Komposisi sentimen'
  if (panel === 'volume') return 'Perubahan volume per topik'
  if (panel === 'alert') return 'Alert aktif'
  return 'Contoh pemberitaan'
}

function Overlay({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="mt-10 max-h-[80vh] w-full max-w-lg overflow-auto border border-line bg-card p-4 duration-200" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-label={title}>
        <div className="mb-3 flex items-start justify-between gap-3">
          <h2 className="text-base font-medium">{title}</h2>
          <button className="h-9 rounded-md border border-line px-3 text-sm" onClick={onClose}>Tutup</button>
        </div>
        {children}
      </div>
    </div>
  )
}

function Metric({ label, value, help, delta, suffix = '%', onClick }: { label: string; value: string; help?: string; delta?: number | null; suffix?: string; onClick?: () => void }) {
  return (
    <button className="border border-line bg-card px-3 py-2 text-left" onClick={onClick} title={help}>
      <p className="text-xs text-muted">{label}</p>
      <p className="text-xl font-medium tabular-nums">{value}</p>
      <p className="flex items-center gap-1 text-xs text-muted">
        {delta == null ? 'Klik untuk rincian' : <><Direction delta={delta} />{formatSigned(delta, suffix)} vs periode lalu</>}
      </p>
    </button>
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
