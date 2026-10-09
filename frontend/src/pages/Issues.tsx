import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../api'
import { Card, ErrorNote, Loading, PageHeader, StanceBadge } from '../components/Ui'
import { useFilters } from '../filters'
import type { IssueCard } from '../types'

interface Topics {
  words: { text: string; value: number }[]
  hashtags: { tag: string; count: number }[]
  entities: { name: string; count: number }[]
  method_note: string
}

export default function IssuesPage() {
  const filters = useFilters()
  const navigate = useNavigate()
  const issues = useApi<{ items: IssueCard[] }>(`/api/issues?${filters.query}`)
  const topics = useApi<Topics>(`/api/topics?${filters.query}`)
  const [term, setTerm] = useState('')
  const related = useApi<{ items: { text: string; value: number }[] }>(term ? `/api/topics/related?term=${encodeURIComponent(term)}&${filters.query}` : null)
  const max = topics.data?.words[0]?.value || 1

  return (
    <div>
      <PageHeader title="Isu & Tren" description="Kelompok percakapan yang perlu ditinjau. Buka satu isu untuk melihat sumber dan saran." />
      {(issues.loading || topics.loading) && <Loading />}
      {issues.error && <ErrorNote message={issues.error} />}
      {topics.data && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <h2 className="font-medium">Kata yang paling sering muncul</h2>
            <p className="text-xs text-muted">Panjang batang adalah jumlah kemunculan. Klik kata untuk melihat kata yang sering muncul bersamanya. Pangsa nada per kata: [data perlu dilengkapi].</p>
            <ul className="mt-3 space-y-2">
              {topics.data.words.slice(0, 10).map((word) => (
                <li key={word.text}>
                  <button className="grid w-full grid-cols-[8rem_1fr_2.5rem] items-center gap-2 text-left text-sm" onClick={() => setTerm(word.text)}>
                    <span className="truncate">{word.text}</span>
                    <span className="h-2 bg-line" aria-hidden>
                      <span className="block h-2 bg-navy-800" style={{ width: `${(word.value / max) * 100}%` }} />
                    </span>
                    <span className="text-right tabular-nums">{word.value}</span>
                  </button>
                </li>
              ))}
            </ul>
            {term && (
              <p className="mt-3 text-sm">
                Terkait <strong>{term}</strong>: {related.data?.items.map((item) => item.text).join(', ') || 'memuat...'}
              </p>
            )}
          </Card>
          <Card>
            <h2 className="font-medium">Tagar</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {topics.data.hashtags.map((item) => (
                <button key={item.tag} className="rounded-full border border-line px-2 py-1 text-xs" onClick={() => navigate(`/explorer?q=${encodeURIComponent('#' + item.tag)}`)}>
                  #{item.tag} · {item.count}
                </button>
              ))}
            </div>
            <h2 className="mt-5 font-medium">Entitas</h2>
            <ul className="mt-2 space-y-1 text-sm">
              {topics.data.entities.map((item) => (
                <li key={item.name} className="flex justify-between gap-3"><span>{item.name}</span><span className="tabular-nums text-muted">{item.count}</span></li>
              ))}
            </ul>
            <p className="mt-4 text-xs text-muted">{topics.data.method_note}</p>
          </Card>
        </div>
      )}
      <div className="mt-4 grid gap-3">
        {issues.data?.items.map((issue) => (
          <button key={issue.id} className="min-h-11 rounded-md border border-line bg-card p-4 text-left" onClick={() => navigate(`/isu/${issue.id}`)}>
            <div className="flex flex-wrap items-center gap-2">
              <StanceBadge stance={issue.stance} />
              <span className="text-xs text-muted">{issue.category}</span>
              {issue.spike_detected && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-950">Lonjakan</span>}
              {issue.is_critical && <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-900">Kritis</span>}
            </div>
            <h2 className="mt-2 font-semibold">{issue.title}</h2>
            <p className="mt-1 text-sm text-muted">{issue.summary}</p>
            <p className="mt-2 text-xs text-muted">{issue.mention_count} mention · risiko {issue.risk_score} · {issue.quadrant}</p>
          </button>
        ))}
      </div>
    </div>
  )
}
