import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, useApi } from '../api'
import { StackedCategories } from '../components/Charts'
import MentionDrawer from '../components/MentionDrawer'
import { Card, ErrorNote, HumanNote, Loading, PageHeader, QuoteBadge, SentimentBadge, SourceLink, StanceBadge } from '../components/Ui'
import { useFilters } from '../filters'
import { formatWhen, PLATFORM_LABEL } from '../format'
import type { MentionCard } from '../types'

interface Breakdown {
  items: { category: string; total: number; positif: number; netral: number; negatif: number; net_sentiment: number }[]
}

interface ClassifyResult {
  sentiment: string
  stance: string
  confidence: number
  category: string
  rationale: string
  risk_score: number
  policy_tags: string[]
}

export default function SentimentPage() {
  const filters = useFilters()
  const navigate = useNavigate()
  const breakdown = useApi<Breakdown>(`/api/sentiment/breakdown?${filters.query}`)
  const mentions = useApi<{ items: MentionCard[] }>(`/api/mentions?page_size=12&sort=terbaru&${filters.query}`)
  const [openId, setOpenId] = useState<number | null>(null)
  const [text, setText] = useState('QRIS bikin dagang di pasar Jakarta lebih gampang, tapi biaya merchant-nya masih kerasa berat.')
  const [result, setResult] = useState<ClassifyResult | null>(null)
  const [error, setError] = useState('')

  async function classify() {
    setError('')
    try {
      setResult(await api<ClassifyResult>('/api/classify', { method: 'POST', body: JSON.stringify({ text }) }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Gagal menguji')
    }
  }

  return (
    <div>
      <PageHeader
        title="Sentimen dan upside / downside"
        description="Klasifikasi tiap konten, alasan singkat, dan ruang koreksi analis. Mesin MVP memakai leksikon bahasa Indonesia; antarmukanya siap diganti IndoBERT atau LLM."
      />
      {breakdown.loading && <Loading />}
      {breakdown.error && <ErrorNote message={breakdown.error} />}
      {breakdown.data && (
        <Card>
          <h2 className="mb-2 font-medium">Sebaran per subkategori</h2>
          <StackedCategories data={breakdown.data.items} />
        </Card>
      )}
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card>
          <h2 className="font-medium">Konten terbaru</h2>
          <div className="mt-2 divide-y divide-line">
            {mentions.data?.items.map((item) => (
              <div key={item.id} className="py-3">
                <button className="block w-full text-left" onClick={() => setOpenId(item.id)}>
                  <span className="flex flex-wrap items-center gap-2">
                    <StanceBadge stance={item.stance} />
                    <SentimentBadge sentiment={item.sentiment} />
                    <span className="text-xs text-muted">keyakinan {Math.round(item.confidence * 100)}%</span>
                  </span>
                  <span className="mt-1 flex items-center gap-2 text-sm font-medium"><QuoteBadge show={item.quotes_bi} />{item.title}</span>
                  <span className="text-xs text-muted">{item.category} · {item.source_name} · {PLATFORM_LABEL[item.platform]} · {formatWhen(item.published_at)}</span>
                  {item.confidence >= 0.99 && <span className="mt-1 block"><HumanNote /></span>}
                </button>
                <SourceLink url={item.url} />
              </div>
            ))}
          </div>
          <button className="mt-3 text-sm underline" onClick={() => navigate('/explorer')}>Buka seluruh mention</button>
        </Card>
        <Card>
          <h2 className="font-medium">Uji teks</h2>
          <p className="mt-1 text-xs text-muted">Tempel judul atau unggahan. Hasil tidak disimpan sampai masuk lewat connector.</p>
          <textarea className="mt-3 min-h-32 w-full rounded-lg border border-line bg-card p-3 text-sm" value={text} onChange={(event) => setText(event.target.value)} />
          <button className="mt-3 h-10 rounded-lg bg-navy-900 px-4 text-sm text-white dark:bg-gold-500 dark:text-navy-950" onClick={classify}>Klasifikasikan</button>
          {error && <p className="mt-2 text-sm text-red-700">{error}</p>}
          {result && (
            <div className="mt-4 space-y-2 text-sm">
              <div className="flex gap-2">
                <StanceBadge stance={result.stance as 'upside'} />
                <SentimentBadge sentiment={result.sentiment as 'positif'} />
              </div>
              <p>Keyakinan {Math.round(result.confidence * 100)}% · {result.category} · risiko {result.risk_score}</p>
              <p className="rounded-lg bg-canvas p-3">{result.rationale}</p>
              <p className="text-xs text-muted">Kebijakan: {result.policy_tags.join(', ') || 'tidak terdeteksi'}</p>
            </div>
          )}
        </Card>
      </div>
      {openId && <MentionDrawer id={openId} onClose={() => setOpenId(null)} onSaved={mentions.reload} />}
    </div>
  )
}
