import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, useApi } from '../api'
import MentionDrawer from '../components/MentionDrawer'
import { Card, ErrorNote, Loading, PageHeader, QuoteBadge, SourceLink, StanceBadge, StatusBadge, inputClass } from '../components/Ui'
import { AdviceCard, type AdviceItem } from '../components/AdviceCard'
import { useAuth } from '../auth'
import { formatWhen, PLATFORM_LABEL, STATUS_LABEL } from '../format'
import type { IssueDetail as IssueDetailBase } from '../types'

interface IssueDetail extends IssueDetailBase {
  advices?: AdviceItem[]
  advice_disclaimer?: string
}

const STATUSES = ['baru', 'ditinjau', 'dieskalasi', 'ditangani', 'selesai']

export default function IssueDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const canEdit = user?.role === 'admin' || user?.role === 'analis'
  const issue = useApi<IssueDetail>(id ? `/api/issues/${id}` : null)
  const [openId, setOpenId] = useState<number | null>(null)
  const [note, setNote] = useState('')
  const [pic, setPic] = useState('')
  const data = issue.data

  useEffect(() => {
    if (!data) return
    setNote(data.analyst_note)
    setPic(data.pic)
  }, [data])

  async function save(status?: string) {
    if (!data) return
    await api(`/api/issues/${data.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status: status || data.status, pic, analyst_note: note }),
    })
    issue.reload()
  }

  return (
    <div>
      <button className="mb-3 text-base text-muted underline" onClick={() => navigate('/isu')}>Kembali ke Isu & Tren</button>
      {issue.loading && <Loading />}
      {issue.error && <ErrorNote message={issue.error} />}
      {data && (
        <>
          <PageHeader title={data.title} description={data.summary} />
          <div className="mb-4 flex flex-wrap gap-2">
            <StanceBadge stance={data.stance} />
            <StatusBadge status={data.status} />
            <span className="text-sm text-muted">{data.quadrant}</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-4">
            <Metric label="Risiko reputasi" value={String(data.risk_score)} />
            <Metric label="Relevansi kebijakan" value={String(data.policy_relevance)} />
            <Metric label="Kecepatan sebar" value={String(data.spread_velocity)} />
            <Metric label="Dampak" value={data.impact_level} />
          </div>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <Card>
              <h2 className="font-medium">Ringkasan bacaan</h2>
              <p className="mt-1 text-xs text-muted">{data.ai_note}</p>
              <Block title="Apa yang terjadi" body={data.ai_what} />
              <Block title="Siapa yang bicara" body={data.ai_who} />
              <Block title="Sentimen" body={data.ai_sentiment} />
              <Block title="Potensi dampak persepsi" body={data.ai_impact} />
              <Block title="Saran respons komunikasi" body={data.ai_recommendation} />
            </Card>
            <Card>
              <h2 className="font-medium">Penanganan isu</h2>
              <div className="mt-3 flex flex-wrap gap-1">
                {STATUSES.map((status) => (
                  <button key={status} disabled={!canEdit} className={`rounded-full px-2 py-1 text-xs ${data.status === status ? 'bg-navy-900 text-white' : 'border border-line'}`} onClick={() => save(status)}>
                    {STATUS_LABEL[status]}
                  </button>
                ))}
              </div>
              <input className={`${inputClass} mt-3 w-full`} disabled={!canEdit} value={pic} placeholder="PIC" onChange={(event) => setPic(event.target.value)} />
              <textarea className="mt-2 min-h-24 w-full rounded-lg border border-line bg-card p-2 text-sm" disabled={!canEdit} value={note} onChange={(event) => setNote(event.target.value)} />
              {canEdit && <button className="mt-3 h-10 rounded-lg bg-navy-900 px-4 text-sm text-white" onClick={() => save()}>Simpan catatan</button>}
              <p className="mt-4 text-xs text-muted">{data.timeline_note}</p>
              <ol className="mt-3 space-y-3 border-l border-line pl-4">
                {data.timeline.map((item) => (
                  <li key={item.id}>
                    <button className="text-left" onClick={() => setOpenId(item.id)}>
                      <span className="text-xs text-muted">{formatWhen(item.published_at)} · {item.source_name} · {PLATFORM_LABEL[item.platform]}</span>
                      <span className="flex items-center gap-2 text-sm font-medium"><QuoteBadge show={item.quotes_bi} />{item.title}</span>
                    </button>
                    <SourceLink url={item.url} />
                  </li>
                ))}
              </ol>
            </Card>
          </div>
          {data.advices && data.advices.length > 0 && (
            <div className="mt-4 grid gap-3">
              <h2 className="font-medium">Saran terkait</h2>
              <p className="text-xs text-muted">{data.advice_disclaimer}</p>
              {data.advices.map((item) => <AdviceCard key={item.id} item={item} onChanged={issue.reload} />)}
            </div>
          )}
        </>
      )}
      {openId && <MentionDrawer id={openId} onClose={() => setOpenId(null)} onSaved={issue.reload} />}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-card p-3">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 text-xl font-semibold capitalize">{value}</p>
    </div>
  )
}

function Block({ title, body }: { title: string; body: string }) {
  return (
    <div className="mt-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</p>
      <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed">{body}</p>
    </div>
  )
}
