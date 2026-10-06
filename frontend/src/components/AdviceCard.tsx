import { useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import { formatWhen } from '../format'
import { QuoteBadge, SourceLink } from './Ui'

export interface AdviceEvidence {
  mention_id: number
  title: string
  source_name: string
  published_at: string
  url: string
  quotes_bi?: boolean
  needs_verification?: boolean
}

export interface AdviceItem {
  id: number
  kind: string
  kind_label: string
  title: string
  situation: string
  who: string
  recommendation: string
  channel: string
  urgency: string
  reason: string
  impact_follow: string
  impact_ignore: string
  alternatives: { option: string; tradeoff: string }[]
  confidence: string
  source_count: number
  source_diversity: number
  evidence: AdviceEvidence[]
  facts: string[]
  inferences: string[]
  public_voice: string
  unit: string
  draft_points: string
  needs_verification: boolean
  insufficient: boolean
  status: string
  analyst_note: string
  useful: boolean | null
  feedback_reason: string
  issue_id: number | null
  category: string
  generated_at: string | null
  change_note: string
  disclaimer: string
  timeline?: { id: number; status: string; note: string; created_at: string; source_count: number }[]
}

const URGENCY: Record<string, string> = { rendah: 'Rendah', sedang: 'Sedang', tinggi: 'Tinggi', segera: 'Segera' }
const STATUS: Record<string, string> = {
  baru: 'Baru',
  diterima: 'Diterima',
  ditolak: 'Ditolak',
  ditunda: 'Ditunda',
  selesai: 'Selesai',
  kedaluwarsa: 'Kedaluwarsa',
  diperbarui: 'Diperbarui',
  data_belum_cukup: 'Data belum cukup',
}
const CONFIDENCE: Record<string, string> = { rendah: 'Rendah', sedang: 'Sedang', tinggi: 'Tinggi' }

export function AdviceCard({ item, onChanged }: { item: AdviceItem; onChanged?: () => void }) {
  const { user } = useAuth()
  const canEdit = user?.role === 'admin' || user?.role === 'analis'
  const [draft, setDraft] = useState(item.draft_points)
  const [note, setNote] = useState(item.analyst_note)
  const [reason, setReason] = useState('')
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState('')

  async function send(action: string, extra: Record<string, unknown> = {}) {
    setError('')
    try {
      await api(`/api/advices/${item.id}/actions`, {
        method: 'POST',
        body: JSON.stringify({ action, analyst_note: note, draft_points: draft, feedback_reason: reason, ...extra }),
      })
      setEditing(false)
      onChanged?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Gagal menyimpan')
    }
  }

  return (
    <article className="rounded-md border border-line bg-card p-4">
      <p className="text-sm text-muted">Dihasilkan AI</p>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded-full bg-navy-900 px-2 py-0.5 text-white">{item.kind_label}</span>
        <span className="rounded-full border border-line px-2 py-0.5">Urgensi {URGENCY[item.urgency] || item.urgency}</span>
        <span className="rounded-full border border-line px-2 py-0.5">{STATUS[item.status] || item.status}</span>
        <span className="text-muted">Keyakinan {CONFIDENCE[item.confidence] || item.confidence}</span>
      </div>
      <h3 className="mt-2 font-medium">{item.title}</h3>
      {item.insufficient && <p className="mt-2 text-sm font-medium">Data belum cukup, perlu verifikasi.</p>}
      {item.needs_verification && <p className="mt-2 text-sm">Konten berpenanda verifikasi. Cek fakta sebelum direspons.</p>}
      <p className="mt-2 text-sm">{item.situation}</p>
      <p className="mt-2 text-sm"><span className="font-medium">Rekomendasi. </span>{item.recommendation}</p>
      {item.channel && <p className="text-sm text-muted">Kanal: {item.channel}</p>}
      <p className="mt-2 text-sm"><span className="font-medium">Alasan. </span>{item.reason}</p>
      <p className="mt-2 text-sm"><span className="font-medium">Jika ditindaklanjuti. </span>{item.impact_follow}</p>
      <p className="text-sm"><span className="font-medium">Jika diabaikan. </span>{item.impact_ignore}</p>
      <div className="mt-2 text-sm">
        <p className="font-medium">Opsi lain</p>
        <ul className="mt-1 list-disc pl-5">
          {item.alternatives.map((alt) => (
            <li key={alt.option}><span className="font-medium">{alt.option}.</span> {alt.tradeoff}</li>
          ))}
        </ul>
      </div>
      <p className="mt-2 text-xs text-muted">{item.source_count} sumber · {item.source_diversity} media atau akun berbeda · unit {item.unit}</p>
      <div className="mt-3 grid gap-2 text-sm md:grid-cols-3">
        <div>
          <p className="text-xs font-medium uppercase text-muted">Fakta dari sumber</p>
          <ul className="mt-1 list-disc pl-4">{item.facts.map((fact) => <li key={fact}>{fact}</li>)}</ul>
        </div>
        <div>
          <p className="text-xs font-medium uppercase text-muted">Inferensi AI</p>
          <ul className="mt-1 list-disc pl-4">{item.inferences.length === 0 && <li>Tidak ada inferensi karena data belum cukup.</li>}{item.inferences.map((line) => <li key={line}>{line}</li>)}</ul>
        </div>
        <div>
          <p className="text-xs font-medium uppercase text-muted">Opini atau emosi publik</p>
          <p className="mt-1">{item.public_voice || 'Tidak tertandai.'}</p>
        </div>
      </div>
      {item.draft_points && <pre className="mt-3 whitespace-pre-wrap rounded-lg bg-canvas p-3 text-sm">{item.draft_points}</pre>}
      <div className="mt-3">
        <details>
          <summary className="cursor-pointer text-sm">Bukti pendukung ({item.evidence.length})</summary>
          <ul className="mt-2 space-y-2">
            {item.evidence.map((ev) => (
              <li key={ev.url}>
                <span className="text-sm text-muted" title={ev.published_at}>{ev.source_name} · {formatWhen(ev.published_at)} WIB</span>
                <span className="line-clamp-2 flex items-center gap-2 text-base"><QuoteBadge show={ev.quotes_bi} />{ev.title}</span>
                <SourceLink url={ev.url} />
              </li>
            ))}
          </ul>
        </details>
      </div>
      {item.change_note && <p className="mt-2 text-xs text-muted">{item.change_note}</p>}
      {item.timeline && item.timeline.length > 0 && (
        <ol className="mt-3 space-y-1 border-l border-line pl-3 text-xs text-muted">
          {item.timeline.map((step) => (
            <li key={step.id}>{formatWhen(step.created_at)} · {STATUS[step.status] || step.status} · {step.note}</li>
          ))}
        </ol>
      )}
      {canEdit && (
        <div className="mt-3 flex flex-wrap gap-2">
          <button className="h-11 rounded-md bg-navy-900 px-3 text-sm text-white" onClick={() => send('terima')}>Terima</button>
          <button className="h-11 rounded-md border border-line px-3 text-sm" onClick={() => send('tolak')}>Tolak</button>
          <button className="h-11 rounded-md border border-line px-3 text-sm" onClick={() => send('tunda')}>Tunda</button>
          <button className="h-11 rounded-md border border-line px-3 text-sm" onClick={() => setEditing((value) => !value)}>Edit</button>
          <button className="h-9 rounded-lg border border-line px-3 text-sm" onClick={() => send('umpan', { useful: true })}>Saran berguna</button>
          <button className="h-9 rounded-lg border border-line px-3 text-sm" onClick={() => send('umpan', { useful: false })}>Tidak berguna</button>
        </div>
      )}
      {editing && canEdit && (
        <div className="mt-3 grid gap-2">
          <textarea className="min-h-24 rounded-lg border border-line p-2 text-sm" value={draft} onChange={(event) => setDraft(event.target.value)} />
          <textarea className="min-h-16 rounded-lg border border-line p-2 text-sm" placeholder="Catatan analis" value={note} onChange={(event) => setNote(event.target.value)} />
          <input className="h-10 rounded-lg border border-line px-2 text-sm" placeholder="Alasan penolakan, bila ada" value={reason} onChange={(event) => setReason(event.target.value)} />
          <button className="h-9 w-fit rounded-lg bg-navy-900 px-3 text-sm text-white" onClick={() => send('edit')}>Simpan suntingan</button>
        </div>
      )}
      {error && <p className="mt-2 text-sm text-red-700">{error}</p>}
    </article>
  )
}
