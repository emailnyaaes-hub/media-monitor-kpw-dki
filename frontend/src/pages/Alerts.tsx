import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, useApi } from '../api'
import { useAuth } from '../auth'
import { Card, ErrorNote, Loading, PageHeader, SeverityBadge, inputClass } from '../components/Ui'
import { formatWhen } from '../format'
import type { AlertItem, Severity } from '../types'

interface Rule {
  id: number
  name: string
  rule_type: string
  threshold: number
  window_hours: number
  severity: Severity
  keyword: string
  channel: string
  is_active: boolean
}

const TYPES = [
  ['negative_growth', 'Kenaikan mention negatif (%)'],
  ['keyword_count', 'Jumlah kemunculan kata'],
  ['tier1_downside', 'Jumlah downside media tier-1'],
  ['kpw_negative', 'Jumlah mention negatif KPw'],
  ['volume_spike', 'Volume mention pada jendela'],
]

export default function AlertsPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const data = useApi<{ items: AlertItem[]; rules: Rule[]; channel_note: string }>('/api/alerts')
  const [message, setMessage] = useState('')
  const [form, setForm] = useState({
    name: 'Aturan baru',
    rule_type: 'keyword_count',
    threshold: 3,
    window_hours: 24,
    severity: 'waspada',
    keyword: '',
    channel: 'dashboard',
    is_active: true,
  })

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

  async function run(path: string) {
    setMessage('')
    const result = await api<Record<string, number>>(path, { method: 'POST' })
    setMessage(JSON.stringify(result))
    data.reload()
  }

  return (
    <div>
      <PageHeader title="Alert dan notifikasi" description="Aturan yang memantau lonjakan negatif, kata sensitif, dan liputan media arus utama."       />
      {data.loading && <Loading />}
      {data.error && <ErrorNote message={data.error} />}
      {message && <p className="mb-3 text-sm">{message}</p>}
      {user?.role === 'admin' && (
        <div className="mb-4 flex flex-wrap gap-2">
          <button className="h-9 rounded-lg border border-line px-3 text-sm" onClick={() => run('/api/jobs/evaluate-alerts')}>Evaluasi aturan</button>
        </div>
      )}
      <div className="grid gap-4 xl:grid-cols-2">
        <div className="space-y-3">
          {data.data?.items.map((item) => (
            <Card key={item.id} className={item.is_read ? 'opacity-70' : ''}>
              <div className="flex items-start justify-between gap-3">
                <SeverityBadge severity={item.severity} />
                <span className="text-xs text-muted">{formatWhen(item.triggered_at)}</span>
              </div>
              <h2 className="mt-2 font-medium">{item.title}</h2>
              <p className="mt-1 text-sm text-muted">{item.message}</p>
              <div className="mt-3 flex gap-2">
                {item.issue_id && <button className="text-sm underline" onClick={() => navigate(`/isu/${item.issue_id}`)}>Buka isu</button>}
                {!item.is_read && user?.role !== 'pimpinan' && <button className="text-sm underline" onClick={() => markRead(item.id)}>Tandai dibaca</button>}
              </div>
            </Card>
          ))}
        </div>
        <div>
          <Card>
            <h2 className="font-medium">Aturan</h2>
            <p className="mt-1 text-xs text-muted">{data.data?.channel_note}</p>
            <ul className="mt-3 divide-y divide-line text-sm">
              {data.data?.rules.map((rule) => (
                <li key={rule.id} className="flex items-center justify-between gap-3 py-3">
                  <span>
                    <span className="block font-medium">{rule.name}</span>
                    <span className="text-xs text-muted">{rule.rule_type} · ambang {rule.threshold} · {rule.window_hours} jam · kanal {rule.channel}</span>
                  </span>
                  {user?.role === 'admin' ? (
                    <button className="text-xs underline" onClick={() => toggle(rule)}>{rule.is_active ? 'Aktif' : 'Nonaktif'}</button>
                  ) : (
                    <span className="text-xs">{rule.is_active ? 'Aktif' : 'Nonaktif'}</span>
                  )}
                </li>
              ))}
            </ul>
          </Card>
          {user?.role === 'admin' && (
            <Card className="mt-4">
              <h2 className="font-medium">Aturan baru</h2>
              <form className="mt-3 grid gap-2" onSubmit={createRule}>
                <input className={inputClass} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
                <select className={inputClass} value={form.rule_type} onChange={(event) => setForm({ ...form, rule_type: event.target.value })}>
                  {TYPES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
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
                <input className={inputClass} placeholder="Kata kunci, bila jenisnya jumlah kata" value={form.keyword} onChange={(event) => setForm({ ...form, keyword: event.target.value })} />
                <button className="h-10 rounded-lg bg-navy-900 text-sm text-white">Simpan aturan</button>
              </form>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
