import { useNavigate } from 'react-router-dom'
import { useApi } from '../api'
import { Card, ErrorNote, Kpi, Loading, PageHeader, StanceBadge } from '../components/Ui'
import { useFilters } from '../filters'
import { formatNumber, formatPct } from '../format'
import type { IssueCard } from '../types'

interface Kpw {
  kpis: { total_mention: number; net_sentiment: number; reach: number; sentiment_pct: { positif: number; netral: number; negatif: number } }
  areas: { name: string; count: number }[]
  issues: IssueCard[]
  map_note: string
}

const POSITIONS: Record<string, { x: number; y: number }> = {
  'Jakarta Utara': { x: 150, y: 48 },
  'Kepulauan Seribu': { x: 48, y: 28 },
  'Jakarta Barat': { x: 70, y: 120 },
  'Jakarta Pusat': { x: 168, y: 118 },
  'Jakarta Timur': { x: 250, y: 130 },
  'Jakarta Selatan': { x: 168, y: 190 },
}

export default function KpwPage() {
  const filters = useFilters()
  const navigate = useNavigate()
  const data = useApi<Kpw>(`/api/kpw?${filters.query}`)
  const maxArea = Math.max(1, ...(data.data?.areas.map((item) => item.count) || [1]))

  return (
    <div>
      <PageHeader
        title="Monitoring KPw DKI"
        description="Pemberitaan dan percakapan pihak luar tentang KPw DKI Jakarta dan isu ekonomi lokal Jakarta."
      />
      {data.loading && <Loading />}
      {data.error && <ErrorNote message={data.error} />}
      {data.data && (
        <>
          <div className="grid gap-3 md:grid-cols-3">
            <Kpi label="Mention KPw" value={formatNumber(data.data.kpis.total_mention)} hint="Hanya pemberitaan dan percakapan pihak luar." />
            <Kpi label="Sentimen bersih" value={formatNumber(data.data.kpis.net_sentiment)} hint={`${formatPct(data.data.kpis.sentiment_pct.positif)} positif · ${formatPct(data.data.kpis.sentiment_pct.negatif)} negatif`} />
            <Kpi label="Jangkauan" value={data.data.kpis.reach ? formatNumber(data.data.kpis.reach) : 'tidak tersedia'} hint="RSS tidak menyertakan jangkauan resmi." />
          </div>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <Card>
              <h2 className="font-medium">Sebaran wilayah</h2>
              <p className="text-xs text-muted">{data.data.map_note}</p>
              <svg viewBox="0 0 320 240" className="mt-2 w-full" role="img" aria-label="Peta skematik Jakarta">
                <rect x="8" y="8" width="304" height="224" rx="16" className="fill-canvas stroke-line" />
                {Object.entries(POSITIONS).map(([name, pos]) => {
                  const count = data.data?.areas.find((item) => item.name === name)?.count || 0
                  const radius = 16 + (count / maxArea) * 22
                  return (
                    <g key={name}>
                      <circle cx={pos.x} cy={pos.y} r={radius} fill="#1E4A7A" opacity={count ? 0.85 : 0.25} />
                      <text x={pos.x} y={pos.y + radius + 12} textAnchor="middle" fontSize="9" fill="currentColor">{name.replace('Jakarta ', '')} ({count})</text>
                    </g>
                  )
                })}
              </svg>
            </Card>
          </div>
          <div className="mt-4 grid gap-3">
            {data.data.issues.map((issue) => (
              <button key={issue.id} className="rounded-md border border-line bg-card p-4 text-left" onClick={() => navigate(`/isu/${issue.id}`)}>
                <StanceBadge stance={issue.stance} />
                <span className="mt-2 block font-medium">{issue.title}</span>
                <span className="text-xs text-muted">{issue.mention_count} mention · {issue.category}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
