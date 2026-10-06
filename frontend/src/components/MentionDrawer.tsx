import { X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import { formatReach, formatWhen, PLATFORM_LABEL, STATUS_LABEL } from '../format'
import type { MentionDetail } from '../types'
import { ErrorNote, HumanNote, QuoteBadge, SentimentBadge, SourceLink, StanceBadge, StatusBadge, VerifiedNote, inputClass } from './Ui'

const STATUSES = ['baru', 'ditinjau', 'dieskalasi', 'ditangani', 'selesai']
const CATEGORIES = [
  'Kebijakan Moneter', 'Sistem Pembayaran', 'Rupiah/Kurs', 'Inflasi', 'Perbankan/Kredit',
  'Pengedaran Uang', 'Reputasi/Kelembagaan', 'Hoaks/Penipuan', 'Kegiatan KPw DKI', 'Ekonomi Jakarta', 'Lainnya',
]

export default function MentionDrawer({ id, onClose, onSaved }: { id: number; onClose: () => void; onSaved: () => void }) {
  const { user } = useAuth()
  const canEdit = user?.role === 'admin' || user?.role === 'analis'
  const [item, setItem] = useState<MentionDetail | null>(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ sentiment: '', stance: '', category: '', status: '', pic: '', analyst_note: '' })

  useEffect(() => {
    let cancel = false
    api<MentionDetail>(`/api/mentions/${id}`)
      .then((data) => {
        if (cancel) return
        setItem(data)
        setForm({
          sentiment: data.sentiment,
          stance: data.stance,
          category: data.category,
          status: data.status,
          pic: data.pic,
          analyst_note: data.analyst_note,
        })
      })
      .catch((err: Error) => { if (!cancel) setError(err.message) })
    return () => { cancel = true }
  }, [id])

  async function save() {
    setSaving(true)
    setError('')
    try {
      const next = await api<MentionDetail>(`/api/mentions/${id}`, { method: 'PATCH', body: JSON.stringify(form) })
      setItem(next)
      onSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Gagal menyimpan')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button className="absolute inset-0 bg-navy-950/50" aria-label="Tutup detail" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-xl flex-col overflow-y-auto bg-card p-5 border-l border-line">
        <div className="flex items-start justify-between gap-3">
          <p className="text-xs uppercase tracking-wide text-muted">Detail mention</p>
          <button onClick={onClose} aria-label="Tutup" className="grid h-8 w-8 place-items-center rounded-lg border border-line"><X size={16} /></button>
        </div>
        {error && <div className="mt-3"><ErrorNote message={error} /></div>}
        {!item && !error && <p className="mt-6 text-sm text-muted">Memuat detail...</p>}
        {item && (
          <div className="mt-3 space-y-4">
            <h2 className="flex items-center gap-2 text-lg font-semibold leading-snug"><QuoteBadge show={item.quotes_bi} />{item.title}</h2>
            <div className="flex flex-wrap gap-2">
              <StanceBadge stance={item.stance} />
              <SentimentBadge sentiment={item.sentiment} />
              <StatusBadge status={item.status} />
              {item.human_corrected && <HumanNote />}
              {item.needs_verification && <VerifiedNote />}
            </div>
            <p className="text-sm leading-relaxed">{item.text}</p>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div><dt className="text-xs text-muted">Sumber</dt><dd>{item.source_name} · tier {item.source_tier}</dd></div>
              <div><dt className="text-xs text-muted">Platform</dt><dd>{PLATFORM_LABEL[item.platform] || item.platform}</dd></div>
              <div><dt className="text-xs text-muted">Akun</dt><dd>{item.author_name} {item.author_handle}</dd></div>
              <div><dt className="text-xs text-muted">Waktu (WIB)</dt><dd>{formatWhen(item.published_at)}</dd></div>
              <div><dt className="text-xs text-muted">Jangkauan</dt><dd>{formatReach(item.reach_estimate)}</dd></div>
              <div><dt className="text-xs text-muted">Engagement</dt><dd>{item.likes || item.shares || item.comments ? `${item.likes} suka · ${item.shares} sebar · ${item.comments} komentar` : 'tidak tersedia'}</dd></div>
              <div><dt className="text-xs text-muted">Keyakinan AI</dt><dd>{Math.round(item.confidence * 100)}%</dd></div>
              <div><dt className="text-xs text-muted">Risiko / relevansi</dt><dd>{item.risk_score} / {item.policy_relevance}</dd></div>
            </dl>
            <p className="rounded-lg bg-canvas p-3 text-sm leading-relaxed">{item.rationale}</p>
            <div className="flex flex-wrap gap-1">
              {item.policy_tags.map((tag) => <span key={tag} className="rounded-full bg-navy-900/5 px-2 py-0.5 text-xs dark:bg-white/10">{tag}</span>)}
              {item.keyword_matches.slice(0, 8).map((tag) => <span key={tag} className="rounded-full border border-line px-2 py-0.5 text-xs">{tag}</span>)}
            </div>
            <SourceLink url={item.url} />
            <div className="grid gap-3 border-t border-line pt-4">
              <p className="text-sm font-medium">Alur penanganan</p>
              <div className="flex flex-wrap gap-1">
                {STATUSES.map((status) => (
                  <button
                    key={status}
                    disabled={!canEdit}
                    onClick={() => setForm({ ...form, status })}
                    className={`rounded-full px-2 py-1 text-xs ${form.status === status ? 'bg-navy-900 text-white dark:bg-gold-500 dark:text-navy-950' : 'border border-line'}`}
                  >
                    {STATUS_LABEL[status]}
                  </button>
                ))}
              </div>
              <div className="grid gap-2 md:grid-cols-3">
                <select className={inputClass} disabled={!canEdit} value={form.sentiment} onChange={(event) => setForm({ ...form, sentiment: event.target.value })}>
                  <option value="positif">Positif</option>
                  <option value="netral">Netral</option>
                  <option value="negatif">Negatif</option>
                </select>
                <select className={inputClass} disabled={!canEdit} value={form.stance} onChange={(event) => setForm({ ...form, stance: event.target.value })}>
                  <option value="upside">Upside</option>
                  <option value="netral">Netral</option>
                  <option value="downside">Downside</option>
                </select>
                <select className={inputClass} disabled={!canEdit} value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })}>
                  {CATEGORIES.map((itemName) => <option key={itemName}>{itemName}</option>)}
                </select>
              </div>
              <input className={inputClass} disabled={!canEdit} placeholder="PIC" value={form.pic} onChange={(event) => setForm({ ...form, pic: event.target.value })} />
              <textarea className="min-h-20 rounded-lg border border-line bg-card p-2 text-sm" disabled={!canEdit} placeholder="Catatan analis" value={form.analyst_note} onChange={(event) => setForm({ ...form, analyst_note: event.target.value })} />
              {canEdit ? (
                <button className="h-10 rounded-lg bg-navy-900 text-sm font-medium text-white dark:bg-gold-500 dark:text-navy-950" onClick={save} disabled={saving}>
                  {saving ? 'Menyimpan...' : 'Simpan koreksi'}
                </button>
              ) : (
                <p className="text-xs text-muted">Peran pimpinan dapat melihat, tetapi tidak mengubah label.</p>
              )}
            </div>
            {item.audit.length > 0 && (
              <div>
                <p className="text-sm font-medium">Jejak audit</p>
                <ul className="mt-2 space-y-2 text-xs text-muted">
                  {item.audit.map((entry, index) => (
                    <li key={`${entry.created_at}-${index}`}>{formatWhen(entry.created_at)} · {entry.actor} · {entry.action}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </aside>
    </div>
  )
}
