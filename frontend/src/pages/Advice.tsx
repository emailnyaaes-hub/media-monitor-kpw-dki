import { useState } from 'react'
import { api, useApi } from '../api'
import { AdviceCard, type AdviceItem } from '../components/AdviceCard'
import DeckDialog from '../components/DeckDialog'
import { Card, ErrorNote, Loading, PageHeader, SourceLink, inputClass } from '../components/Ui'
import { formatWhen } from '../format'

interface Payload {
  refreshed_at: string | null
  disclaimer: string
  items: AdviceItem[]
}

const URGENCY = ['', 'segera', 'tinggi', 'sedang', 'rendah']
const KINDS = ['', 'respons', 'prioritas', 'kebijakan', 'peluang', 'mitigasi']
const STATUSES = ['', 'baru', 'diperbarui', 'diterima', 'ditolak', 'ditunda', 'selesai', 'data_belum_cukup', 'kedaluwarsa']

export default function AdvicePage() {
  const [urgency, setUrgency] = useState('')
  const [kind, setKind] = useState('')
  const [status, setStatus] = useState('')
  const [unit, setUnit] = useState('')
  const query = new URLSearchParams()
  if (urgency) query.set('urgency', urgency)
  if (kind) query.set('kind', kind)
  if (status) query.set('status', status)
  if (unit) query.set('unit', unit)
  const data = useApi<Payload>(`/api/advices?${query.toString()}`)
  const [question, setQuestion] = useState('Ringkas kritik publik soal BI-Rate minggu ini')
  const [askResult, setAskResult] = useState<{ status: string; answer: string; evidence: { title: string; source_name: string; url: string }[] } | null>(null)
  const [sim, setSim] = useState<{ status: string; answer?: string; disclaimer: string; measured?: { total: number; negatif: number; positif: number; netral: number; catatan: string }; options?: { option: string; estimate: string; tradeoff: string; label: string }[]; evidence?: { title: string; url: string; source_name: string }[] } | null>(null)
  const [error, setError] = useState('')
  const [deckOpen, setDeckOpen] = useState(false)

  async function askNow(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    try {
      setAskResult(await api('/api/dss/ask', { method: 'POST', body: JSON.stringify({ question }) }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Pertanyaan gagal')
    }
  }

  function openHtml(path: string) {
    const token = localStorage.getItem('bi-token')
    fetch(path, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => response.text())
      .then((html) => {
        const frame = window.open('', '_blank')
        if (!frame) return
        frame.document.write(html)
        frame.document.close()
      })
  }

  async function simulate() {
    setError('')
    try {
      setSim(await api('/api/dss/simulate', { method: 'POST', body: JSON.stringify({ issue_id: null }) }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Simulasi gagal')
    }
  }

  return (
    <div>
      <PageHeader
        title="Pusat Saran"
        description="Pendukung keputusan untuk kehumasan. Tidak ada pernyataan yang dikirim otomatis."
      />
      <p className="mb-3 rounded-lg border border-line bg-gold-100 px-3 py-2 text-sm text-navy-900">{data.data?.disclaimer}</p>
      <p className="mb-4 text-sm text-muted">Saran diperbarui: {data.data?.refreshed_at ? `${formatWhen(data.data.refreshed_at)} WIB` : 'belum ada siklus'}</p>
      <div className="mb-4 flex flex-wrap gap-2">
        <button className="h-10 rounded-lg border border-line px-3 text-sm" onClick={() => setDeckOpen(true)}>Briefing PPTX</button>
        <button className="h-10 rounded-lg border border-line px-3 text-sm" onClick={() => openHtml('/api/export/briefing.html')}>Briefing cetak</button>
        <button className="h-10 rounded-lg border border-line px-3 text-sm" onClick={() => openHtml('/api/export/masukan-kebijakan.html')}>Masukan kebijakan</button>
      </div>
      <div className="mb-4 grid gap-2 md:grid-cols-4">
        <select className={inputClass} value={urgency} onChange={(event) => setUrgency(event.target.value)}>
          {URGENCY.map((item) => <option key={item} value={item}>{item ? `Urgensi ${item}` : 'Semua urgensi'}</option>)}
        </select>
        <select className={inputClass} value={kind} onChange={(event) => setKind(event.target.value)}>
          {KINDS.map((item) => <option key={item} value={item}>{item || 'Semua jenis'}</option>)}
        </select>
        <select className={inputClass} value={status} onChange={(event) => setStatus(event.target.value)}>
          {STATUSES.map((item) => <option key={item} value={item}>{item || 'Semua status'}</option>)}
        </select>
        <input className={inputClass} placeholder="Unit, mis. Kehumasan" value={unit} onChange={(event) => setUnit(event.target.value)} />
      </div>
      {data.loading && <Loading />}
      {data.error && <ErrorNote message={data.error} />}
      {error && <div className="mb-3"><ErrorNote message={error} /></div>}
      <div className="grid gap-3">
        {data.data?.items.map((item) => <AdviceCard key={item.id} item={item} onChanged={data.reload} />)}
        {data.data && data.data.items.length === 0 && <p className="text-sm text-muted">Tidak ada saran pada filter ini.</p>}
      </div>
      {deckOpen && <DeckDialog onClose={() => setDeckOpen(false)} />}
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="font-medium">Tanya AI</h2>
          <p className="mt-1 text-xs text-muted">Jawaban hanya dari konten eksternal yang sudah tersimpan.</p>
          <form className="mt-3 grid gap-2" onSubmit={askNow}>
            <textarea className="min-h-20 rounded-lg border border-line p-2 text-sm" value={question} onChange={(event) => setQuestion(event.target.value)} />
            <button className="h-10 rounded-lg bg-navy-900 text-sm text-white">Tanya</button>
          </form>
          {askResult && (
            <div className="mt-3 text-sm">
              {askResult.status === 'data_belum_cukup' && <p className="font-medium">Data belum cukup, perlu verifikasi.</p>}
              <p className="whitespace-pre-wrap">{askResult.answer}</p>
              <ul className="mt-2 space-y-2">
                {askResult.evidence.map((item) => (
                  <li key={item.url}>{item.source_name}: {item.title}<SourceLink url={item.url} /></li>
                ))}
              </ul>
            </div>
          )}
        </Card>
        <Card>
          <h2 className="font-medium">Bagaimana jika</h2>
          <p className="mt-1 text-xs text-muted">Perbandingan opsi. Label estimasi bukan ramalan angka.</p>
          <button className="mt-3 h-10 rounded-lg border border-line px-3 text-sm" onClick={() => simulate()}>Bandingkan opsi pada 14 hari terakhir</button>
          {sim && (
            <div className="mt-3 text-sm">
              <p>{sim.disclaimer}</p>
              {sim.status === 'data_belum_cukup' && <p className="mt-2 font-medium">{sim.answer}</p>}
              {sim.measured && <p className="mt-2">Terukur: {sim.measured.total} konten, {sim.measured.positif} positif, {sim.measured.netral} netral, {sim.measured.negatif} negatif. {sim.measured.catatan}</p>}
              <ul className="mt-2 space-y-2">
                {sim.options?.map((item) => (
                  <li key={item.option}><span className="font-medium">{item.option}.</span> {item.estimate} {item.tradeoff} <span className="text-xs text-muted">{item.label}</span></li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
