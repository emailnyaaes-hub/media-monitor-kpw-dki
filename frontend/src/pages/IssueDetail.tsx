import { useEffect, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, useApi } from '../api'
import MentionDrawer from '../components/MentionDrawer'
import { Card, ErrorNote, Loading, PageHeader, QuoteBadge, SourceLink, StanceBadge, StatusBadge, inputClass } from '../components/Ui'
import { AdviceCard, type AdviceItem } from '../components/AdviceCard'
import { useAuth } from '../auth'
import { formatWhen, PLATFORM_LABEL, STATUS_LABEL } from '../format'
import type { IssueDetail as IssueDetailBase } from '../types'
import EvidenceList from '../components/EvidenceList'
import { levelClass, type Evidence } from '../voice'

interface Brief {
  cukup: boolean
  apa: string
  kenapa: {
    pemicu: (Evidence & { catatan?: string }) | null
    hipotesis: { label: string; teks: string }[]
    penguat: string[]
  }
  dampak: { dimensi: string; tingkat: string; alasan: string }[]
  rekomendasi: {
    jenis?: string
    teks: string
    urgensi?: string
    unit?: string
    keyakinan: string
    luar_kewenangan?: boolean
    insufficient: boolean
    alternatif?: { opsi: string; tradeoff: string }[]
  }
  bukti: Evidence[]
  siklus: { tahap: string; alasan: string; eskalasi: boolean; penanda: string }
  narasi: { label: string; jumlah: number; sumber: string[] }[]
  keyakinan?: string
  metode?: string
  disclaimer: string
}

interface IssueDetail extends IssueDetailBase {
  advices?: AdviceItem[]
  advice_disclaimer?: string
  brief?: Brief
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
          {data.brief && <BriefView brief={data.brief} />}
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

function BriefView({ brief }: { brief: Brief }) {
  const rec = brief.rekomendasi
  return (
    <section className="mt-4 rounded-md border border-line bg-card" aria-label="Apa, kenapa, dampak, rekomendasi, bukti">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3 text-sm">
        <span className="font-medium">Siklus isu: {brief.siklus.tahap}</span>
        <span className="text-muted">{brief.siklus.alasan}</span>
        {brief.siklus.eskalasi && <span className="rounded bg-amber-50 px-2 py-0.5 text-xs text-amber-900 dark:bg-amber-950/50 dark:text-amber-200">{brief.siklus.penanda}</span>}
        <span className="ml-auto text-xs text-muted">Keyakinan {brief.keyakinan || rec.keyakinan}</span>
      </div>
      <div className="grid divide-y divide-line lg:grid-cols-2 lg:divide-x lg:divide-y-0">
        <div className="space-y-4 p-4">
          <Step n="1" title="Apa">
            <p>{brief.apa}</p>
            {brief.narasi.length > 0 && <p className="mt-1 text-xs text-muted">Narasi: {brief.narasi.map((item) => `${item.label} (${item.jumlah})`).join(', ')}</p>}
          </Step>
          <Step n="2" title="Kenapa">
            {brief.kenapa.pemicu && (
              <div>
                <p className="text-xs font-medium">Pemicu yang teridentifikasi</p>
                <EvidenceList items={[brief.kenapa.pemicu]} limit={1} />
                <p className="text-xs text-muted">{brief.kenapa.pemicu.catatan}</p>
              </div>
            )}
            {brief.kenapa.hipotesis.map((item) => (
              <p key={item.teks} className="mt-2 border-l-2 border-amber-500 pl-2">
                <span className="mr-1 rounded bg-amber-50 px-1.5 py-0.5 text-xs font-medium text-amber-900 dark:bg-amber-950/50 dark:text-amber-200">{item.label}</span>
                {item.teks}
              </p>
            ))}
            <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-muted">{brief.kenapa.penguat.map((item) => <li key={item}>{item}</li>)}</ul>
          </Step>
          <Step n="3" title="Dampak bagi BI Jakarta">
            <ul className="divide-y divide-line">
              {brief.dampak.map((item) => (
                <li key={item.dimensi} className="py-2">
                  <span className="flex items-center justify-between gap-2">
                    <span className="font-medium">{item.dimensi}</span>
                    <span className={`rounded px-2 py-0.5 text-xs ${levelClass(item.tingkat)}`}>{item.tingkat}</span>
                  </span>
                  <span className="mt-0.5 block text-xs text-muted">{item.alasan}</span>
                </li>
              ))}
            </ul>
          </Step>
        </div>
        <div className="space-y-4 p-4">
          <Step n="4" title="Rekomendasi">
            {rec.insufficient ? (
              <p className="font-medium text-amber-800 dark:text-amber-200">Data belum cukup, perlu verifikasi</p>
            ) : (
              <p>{rec.teks}</p>
            )}
            <dl className="mt-2 grid grid-cols-2 gap-2 text-xs">
              {rec.urgensi && <div><dt className="text-muted">Urgensi</dt><dd><span className={`rounded px-2 py-0.5 ${levelClass(rec.urgensi)}`}>{rec.urgensi}</span></dd></div>}
              {rec.unit && <div><dt className="text-muted">Unit penanggung jawab</dt><dd>{rec.unit}</dd></div>}
              {rec.jenis && <div><dt className="text-muted">Jenis tindakan</dt><dd>{rec.jenis}</dd></div>}
              <div><dt className="text-muted">Keyakinan</dt><dd>{rec.keyakinan}</dd></div>
            </dl>
            {rec.luar_kewenangan && <p className="mt-2 text-xs text-amber-800 dark:text-amber-200">Perlu koordinasi pihak lain.</p>}
            {rec.alternatif && rec.alternatif.length > 0 && (
              <div className="mt-3">
                <p className="text-xs font-medium">Opsi dan trade-off</p>
                <ul className="mt-1 space-y-1 text-xs">
                  {rec.alternatif.map((item) => <li key={item.opsi}><span className="font-medium">{item.opsi}</span> <span className="text-muted">{item.tradeoff}</span></li>)}
                </ul>
              </div>
            )}
          </Step>
          <Step n="5" title={`Bukti (${brief.bukti.length} tautan)`}>
            <EvidenceList items={brief.bukti} limit={8} />
          </Step>
          <p className="text-xs text-muted">{brief.metode} {brief.disclaimer}</p>
        </div>
      </div>
    </section>
  )
}

function Step({ n, title, children }: { n: string; title: string; children: ReactNode }) {
  return (
    <div className="text-sm">
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">{n}. {title}</p>
      {children}
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
