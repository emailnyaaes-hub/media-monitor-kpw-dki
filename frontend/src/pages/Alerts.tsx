import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, useApi } from '../api'
import { useAuth } from '../auth'
import { Card, Empty, ErrorNote, Loading, PageHeader, SeverityBadge, inputClass } from '../components/Ui'
import { formatWhen } from '../format'
import type { AlertItem, Severity } from '../types'

interface Rule {
  id: number
  name: string
  rule_type: string
  rule_label?: string
  why?: string
  threshold: number
  window_hours: number
  severity: Severity
  keyword: string
  channel: string
  is_active: boolean
}

interface EwsBoard {
  level: 'tenang' | 'pantau' | 'waspada' | 'kritis' | string
  label: string
  summary: string
  unread: number
  by_severity: { kritis: number; waspada: number; info: number }
  focus: { id: number; title: string; severity: Severity; rule_type: string; action: string }[]
  watchpoints: { id: number; name: string; label: string; why: string; severity: Severity; threshold: number; window_hours: number }[]
  updated_at: string
}

interface AlertsPayload {
  items: AlertItem[]
  rules: Rule[]
  channel_note: string
  unread: number
  ews: EwsBoard
}

const TYPES = [
  ['high_risk', 'Tumpukan skor risiko tinggi'],
  ['hoax_spread', 'Pola bahasa hoaks'],
  ['social_amplify', 'Amplifikasi sosial negatif'],
  ['currency_stress', 'Tekanan narasi rupiah/kurs'],
  ['quote_pressure', 'Kutipan BI bernada negatif'],
  ['cross_channel', 'Isu menyeberang berita ↔ sosial'],
  ['tier1_downside', 'Downside media tier-1'],
  ['kpw_negative', 'Mention negatif KPw'],
  ['narrative_growth', 'Narasi yang tumbuh'],
  ['complaint_growth', 'Kenaikan keluhan (%)'],
  ['unverified_burst', 'Konten belum terverifikasi'],
  ['negative_growth', 'Kenaikan mention negatif (%)'],
  ['keyword_count', 'Jumlah kemunculan kata'],
  ['volume_spike', 'Volume mention pada jendela'],
]

const LEVEL_STYLE: Record<string, string> = {
  tenang: 'border-emerald-300/60 bg-emerald-50 text-emerald-950 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-100',
  pantau: 'border-sky-300/60 bg-sky-50 text-sky-950 dark:border-sky-800 dark:bg-sky-950/30 dark:text-sky-100',
  waspada: 'border-amber-300/70 bg-amber-50 text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-50',
  kritis: 'border-red-400/70 bg-red-50 text-red-950 dark:border-red-800 dark:bg-red-950/40 dark:text-red-50',
}

export default function AlertsPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const data = useApi<AlertsPayload>('/api/alerts')
  const [message, setMessage] = useState('')
  const [form, setForm] = useState({
    name: 'Aturan EWS baru',
    rule_type: 'social_amplify',
    threshold: 3,
    window_hours: 24,
    severity: 'waspada',
    keyword: '',
    channel: 'dashboard',
    is_active: true,
  })

  const ews = data.data?.ews
  const items = data.data?.items || []

  async function markRead(id: number) {
    await api(`/api/alerts/${id}/read`, { method: 'PATCH' })
    data.reload()
  }

  async function toggle(rule: Rule) {
    await api(`/api/alert-rules/${rule.id}`, { method: 'PATCH', body: JSON.stringify({ ...rule, is_active: !rule.is_active }) })
    data.reload()
  }

  async function createRule(event: React.FormEvent) {
    event.preventDefault()
    await api('/api/alert-rules', { method: 'POST', body: JSON.stringify(form) })
    data.reload()
  }

  async function runEvaluate() {
    setMessage('')
    const result = await api<{ created: number }>('/api/jobs/evaluate-alerts', { method: 'POST' })
    setMessage(result.created > 0 ? `${result.created} sinyal EWS baru dipicu.` : 'Tidak ada aturan yang terpicu saat ini.')
    data.reload()
  }

  return (
    <div className="mx-auto max-w-6xl pb-16 md:pb-0">
      <PageHeader
        title="EWS — Early Warning System"
        description="Papan peringatan dini reputasi dan narasi untuk KPw BI DKI: deteksi lonjakan, hoaks, tekanan kurs, amplifikasi sosial, lalu usulkan tindakan yang masuk kewenangan komunikasi."
      />
      {data.loading && <Loading />}
      {data.error && <ErrorNote message={data.error} />}
      {message && <p className="mb-3 text-sm text-muted">{message}</p>}

      {ews && (
        <section className={`reveal mb-5 rounded-xl border px-4 py-4 md:px-5 ${LEVEL_STYLE[ews.level] || LEVEL_STYLE.pantau}`}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] opacity-80">Status situasional</p>
              <h2 className="mt-1 text-xl font-bold tracking-tight md:text-2xl">{ews.label}</h2>
              <p className="mt-2 max-w-3xl text-sm leading-relaxed opacity-90">{ews.summary}</p>
            </div>
            <div className="text-right text-xs opacity-80">
              <p>{ews.unread} belum dibaca</p>
              <p className="mt-1">Kritis {ews.by_severity.kritis} · Waspada {ews.by_severity.waspada} · Info {ews.by_severity.info}</p>
              <p className="mt-1">Diperbarui {formatWhen(ews.updated_at)}</p>
            </div>
          </div>
          {ews.focus.length > 0 && (
            <div className="mt-4 grid gap-2 md:grid-cols-2">
              {ews.focus.map((item) => (
                <div key={item.id} className="rounded-lg border border-black/10 bg-white/50 p-3 text-sm dark:border-white/10 dark:bg-black/20">
                  <div className="flex items-center justify-between gap-2">
                    <SeverityBadge severity={item.severity} />
                  </div>
                  <p className="mt-2 font-medium">{item.title}</p>
                  <p className="mt-1 text-xs opacity-80">Langkah: {item.action}</p>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {user?.role === 'admin' && (
        <div className="mb-4 flex flex-wrap gap-2">
          <button className="h-9 rounded-lg border border-line px-3 text-sm" onClick={() => void runEvaluate()}>
            Evaluasi EWS sekarang
          </button>
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-[0.14em] text-muted">Sinyal aktif</h2>
          {items.length === 0 && <Empty label="Belum ada sinyal EWS" hint="Jalankan evaluasi atau tunggu siklus pengambilan data." />}
          {items.map((item) => (
            <Card key={item.id} className={`reveal ${item.is_read ? 'opacity-70' : ''}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <SeverityBadge severity={item.severity} />
                  {item.rule_label && <span className="text-[11px] uppercase tracking-wide text-muted">{item.rule_label}</span>}
                </div>
                <span className="shrink-0 text-xs text-muted">{formatWhen(item.triggered_at)}</span>
              </div>
              <h3 className="mt-2 text-base font-semibold">{item.title}</h3>
              {item.why && <p className="mt-2 text-sm text-muted"><span className="font-medium text-ink">Mengapa penting · </span>{item.why}</p>}
              <p className="mt-2 text-sm leading-relaxed text-muted">{item.message}</p>
              {item.action && (
                <div className="mt-3 rounded-md border border-line bg-paper/60 px-3 py-2 text-sm dark:bg-white/5">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">Tindakan disarankan{item.owner ? ` · ${item.owner}` : ''}</p>
                  <p className="mt-1">{item.action}</p>
                </div>
              )}
              <div className="mt-3 flex flex-wrap gap-3">
                {item.issue_id && (
                  <button className="text-sm underline" onClick={() => navigate(`/isu/${item.issue_id}`)}>
                    Buka isu terkait
                  </button>
                )}
                <button className="text-sm underline" onClick={() => navigate('/explorer')}>
                  Cek di Jelajah
                </button>
                {!item.is_read && user?.role !== 'pimpinan' && (
                  <button className="text-sm underline" onClick={() => void markRead(item.id)}>
                    Tandai ditinjau
                  </button>
                )}
              </div>
            </Card>
          ))}
        </div>

        <div className="space-y-4">
          <Card>
            <h2 className="font-medium">Radar pemantauan</h2>
            <p className="mt-1 text-xs text-muted">{data.data?.channel_note}</p>
            <ul className="mt-3 divide-y divide-line text-sm">
              {(data.data?.rules || []).map((rule) => (
                <li key={rule.id} className="py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <span className="block font-medium">{rule.name}</span>
                      <span className="mt-0.5 block text-xs text-muted">
                        {rule.rule_label || rule.rule_type} · ambang {rule.threshold} · {rule.window_hours} jam
                      </span>
                      {rule.why && <span className="mt-1 block text-xs text-muted">{rule.why}</span>}
                    </div>
                    {user?.role === 'admin' ? (
                      <button className="shrink-0 text-xs underline" onClick={() => void toggle(rule)}>
                        {rule.is_active ? 'Aktif' : 'Nonaktif'}
                      </button>
                    ) : (
                      <span className="shrink-0 text-xs">{rule.is_active ? 'Aktif' : 'Nonaktif'}</span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </Card>

          {user?.role === 'admin' && (
            <Card>
              <h2 className="font-medium">Aturan EWS baru</h2>
              <form className="mt-3 grid gap-2" onSubmit={createRule}>
                <input className={inputClass} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
                <select className={inputClass} value={form.rule_type} onChange={(event) => setForm({ ...form, rule_type: event.target.value })}>
                  {TYPES.map(([id, label]) => (
                    <option key={id} value={id}>{label}</option>
                  ))}
                </select>
                <div className="grid grid-cols-2 gap-2">
                  <input className={inputClass} type="number" value={form.threshold} onChange={(event) => setForm({ ...form, threshold: Number(event.target.value) })} />
                  <input className={inputClass} type="number" value={form.window_hours} onChange={(event) => setForm({ ...form, window_hours: Number(event.target.value) })} />
                </div>
                <select className={inputClass} value={form.severity} onChange={(event) => setForm({ ...form, severity: event.target.value })}>
                  <option value="info">Info</option>
                  <option value="waspada">Waspada</option>
                  <option value="kritis">Kritis</option>
                </select>
                <input
                  className={inputClass}
                  placeholder="Kata kunci (hanya untuk jenis jumlah kata)"
                  value={form.keyword}
                  onChange={(event) => setForm({ ...form, keyword: event.target.value })}
                />
                <button className="h-10 rounded-lg bg-navy-900 text-sm text-white dark:bg-gold-500 dark:text-navy-950">Simpan aturan</button>
              </form>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
