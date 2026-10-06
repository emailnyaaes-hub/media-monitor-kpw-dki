import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, useApi } from '../api'
import { useAuth } from '../auth'
import { Card, ErrorNote, Loading, PageHeader, inputClass } from '../components/Ui'

interface Config {
  weights: Record<string, number>
  thresholds: Record<string, number>
  notes: string
}

const WEIGHT_LABEL: Record<string, string> = {
  sentiment: 'Sentimen',
  reach: 'Jangkauan',
  velocity: 'Kecepatan sebar',
  source: 'Kredibilitas sumber',
  actor: 'Keterlibatan tokoh',
}

export default function SettingsPage() {
  const { user } = useAuth()
  const admin = user?.role === 'admin'
  const remote = useApi<{ config: Config; classify_prompt: string; summary_prompt: string }>('/api/nlp/config')
  const audit = useApi<{ items: { actor: string; action: string; created_at: string; entity_type: string }[] }>(admin ? '/api/audit' : null)
  const dss = useApi<{ min_sources: number; urgent_risk: number; credibility_weight: number; tone: string }>('/api/dss/config')
  const [weights, setWeights] = useState<Record<string, number> | null>(null)
  const [dssForm, setDssForm] = useState<{ min_sources: number; urgent_risk: number; credibility_weight: number; tone: string } | null>(null)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')

  useEffect(() => {
    if (remote.data) setWeights(remote.data.config.weights)
  }, [remote.data])

  useEffect(() => {
    if (dss.data) setDssForm(dss.data)
  }, [dss.data])

  async function saveDss() {
    if (!dssForm) return
    setError('')
    setSaved('')
    try {
      await api('/api/dss/config', { method: 'PUT', body: JSON.stringify(dssForm) })
      setSaved('Parameter saran tersimpan dan saran disusun ulang dari data yang ada.')
      dss.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Gagal menyimpan parameter saran')
    }
  }
  async function save() {
    if (!weights || !remote.data) return
    setError('')
    setSaved('')
    try {
      await api('/api/nlp/config', {
        method: 'PUT',
        body: JSON.stringify({ weights, thresholds: remote.data.config.thresholds }),
      })
      setSaved('Bobot tersimpan. Skor baru memakai bobot ini. Skor lama tidak dihitung ulang.')
      remote.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Gagal menyimpan')
    }
  }

  return (
    <div>
      <PageHeader
        title="Pengaturan"
        description="Bobot risiko, parameter saran, dan halaman kerja yang tidak masuk menu utama."
      />
      <nav className="mb-4 flex flex-wrap gap-3 text-base">
        <Link className="underline" to="/sentimen">Sentimen</Link>
        <Link className="underline" to="/sumber">Status sumber</Link>
        <Link className="underline" to="/alert">Alert</Link>
        <Link className="underline" to="/kata-kunci">Kata kunci dan daftar blokir</Link>
      </nav>
      {remote.loading && <Loading />}
      {remote.error && <ErrorNote message={remote.error} />}
      {error && <div className="mb-3"><ErrorNote message={error} /></div>}
      {saved && <p className="mb-3 text-sm">{saved}</p>}
      {remote.data && weights && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <h2 className="font-medium">Bobot risiko reputasi</h2>
            <p className="mt-1 text-xs text-muted">{remote.data.config.notes}</p>
            <div className="mt-3 grid gap-3">
              {Object.entries(weights).map(([key, value]) => (
                <label key={key} className="grid gap-1 text-sm">
                  {WEIGHT_LABEL[key] || key}
                  <input
                    className={inputClass}
                    type="number"
                    min={0}
                    max={1}
                    step={0.05}
                    disabled={!admin}
                    value={value}
                    onChange={(event) => setWeights({ ...weights, [key]: Number(event.target.value) })}
                  />
                </label>
              ))}
            </div>
            <p className="mt-2 text-xs text-muted">Jumlah saat ini: {Object.values(weights).reduce((sum, value) => sum + value, 0).toFixed(2)}. Dekatkan ke 1,00.</p>
            {admin && <button className="mt-3 h-10 rounded-lg bg-navy-900 px-4 text-sm text-white" onClick={save}>Simpan bobot</button>}
          </Card>
          <Card>
            <h2 className="font-medium">Prompt klasifikasi</h2>
            <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-canvas p-3 text-xs leading-relaxed">{remote.data.classify_prompt}</pre>
            <h2 className="mt-4 font-medium">Prompt ringkasan isu</h2>
            <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-canvas p-3 text-xs leading-relaxed">{remote.data.summary_prompt}</pre>
          </Card>
          {admin && audit.data && (
            <Card className="lg:col-span-2">
              <h2 className="font-medium">Jejak audit terbaru</h2>
              <ul className="mt-2 space-y-1 text-sm">
                {audit.data.items.length === 0 && <li className="text-muted">Belum ada perubahan.</li>}
                {audit.data.items.map((item, index) => (
                  <li key={`${item.created_at}-${index}`}>{item.created_at} · {item.actor} · {item.action} · {item.entity_type}</li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}
      {dssForm && (
        <Card className="mt-4">
          <h2 className="font-medium">Parameter Saran AI</h2>
          <p className="mt-1 text-xs text-muted">Ambang sumber, ambang risiko untuk urgensi Segera, bobot kredibilitas pada urutan prioritas, dan nada draf pesan. Perubahan menyusun ulang saran dari data yang sudah ada.</p>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <label className="grid gap-1 text-sm">Ambang minimal jumlah sumber
              <input className={inputClass} type="number" min={1} disabled={!admin} value={dssForm.min_sources} onChange={(event) => setDssForm({ ...dssForm, min_sources: Number(event.target.value) })} />
            </label>
            <label className="grid gap-1 text-sm">Ambang risk score untuk Segera
              <input className={inputClass} type="number" min={0} max={100} disabled={!admin} value={dssForm.urgent_risk} onChange={(event) => setDssForm({ ...dssForm, urgent_risk: Number(event.target.value) })} />
            </label>
            <label className="grid gap-1 text-sm">Bobot kredibilitas media
              <input className={inputClass} type="number" min={0} step={0.1} disabled={!admin} value={dssForm.credibility_weight} onChange={(event) => setDssForm({ ...dssForm, credibility_weight: Number(event.target.value) })} />
            </label>
            <label className="grid gap-1 text-sm">Gaya bahasa draf
              <input className={inputClass} disabled={!admin} value={dssForm.tone} onChange={(event) => setDssForm({ ...dssForm, tone: event.target.value })} />
            </label>
          </div>
          {admin && <button className="mt-3 h-10 rounded-lg bg-navy-900 px-4 text-sm text-white" onClick={saveDss}>Simpan parameter saran</button>}
        </Card>
      )}
    </div>
  )
}
