import { useMemo, useState } from 'react'
import { api, downloadPost } from '../api'
import { Card, ErrorNote, PageHeader } from '../components/Ui'

interface Finding {
  start: number
  end: number
  kalimat: string
  kategori: string
  risiko: 'Tinggi' | 'Sedang' | 'Rendah' | string
  masalah: string
  dasar_hukum: string
  saran: string
  alasan: string
  accepted: boolean
}

interface ReviewResult {
  disclaimer: string
  original: string
  revised: string
  findings: Finding[]
  score: number
  status: string
  counts: Record<string, number>
  error?: string
  method?: string
  saved?: boolean
}

const RISKS = {
  Tinggi: 'border-red-300 bg-red-50',
  Sedang: 'border-amber-300 bg-amber-50',
  Rendah: 'border-sky-300 bg-sky-50',
}

export default function ReviewPage() {
  const [kind, setKind] = useState('siaran')
  const [platform, setPlatform] = useState('Instagram')
  const [text, setText] = useState('')
  const [topic, setTopic] = useState('')
  const [audience, setAudience] = useState('')
  const [releaseDate, setReleaseDate] = useState('')
  const [save, setSave] = useState(false)
  const [result, setResult] = useState<ReviewResult | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState('')
  const [history, setHistory] = useState<{ id: number; created_at: string; kind: string; platform: string; score: number; status: string }[]>([])

  const revised = useMemo(() => (result ? applyLocal(result.original, result.findings) : ''), [result])

  async function submit() {
    setLoading(true)
    setError('')
    setNotice('')
    try {
      const data = await api<ReviewResult>('/api/review', {
        method: 'POST',
        body: JSON.stringify({ kind, platform, text, topic, audience, release_date: releaseDate, save }),
      })
      setResult(data)
      if (data.error) setError(data.error)
      else {
        setNotice(save ? 'Draf disimpan karena Anda mencentang simpan riwayat.' : 'Draf tidak disimpan di server.')
        if (save) void loadHistory()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Review gagal')
    } finally {
      setLoading(false)
    }
  }

  async function loadHistory() {
    try {
      const data = await api<{ items: typeof history }>('/api/reviews')
      setHistory(data.items)
    } catch {
      setHistory([])
    }
  }

  async function openSaved(id: number) {
    setError('')
    try {
      const data = await api<ReviewResult>(`/api/reviews/${id}`)
      setResult(data)
      setNotice('Membuka draf yang pernah Anda setujui untuk disimpan.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Riwayat gagal dibuka')
    }
  }

  function update(index: number, patch: Partial<Finding>) {
    if (!result) return
    const findings = result.findings.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item))
    setResult({ ...result, findings })
  }

  async function exportDocx() {
    if (!result) return
    await downloadPost('/api/review/export.docx', 'review-konten.docx', {
      original: result.original,
      revised,
      findings: result.findings,
      score: result.score,
      status: result.status,
    })
  }

  return (
    <div>
      <PageHeader
        title="Review Konten"
        description="Periksa draf siaran pers atau caption sebelum terbit. Ini alat bantu, bukan keputusan Unit Hukum."
      />
      <Card className="mb-4">
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm">Jenis
            <select className="mt-1 h-10 w-full rounded-lg border border-line bg-card px-2" value={kind} onChange={(event) => setKind(event.target.value)}>
              <option value="siaran">Siaran Pers</option>
              <option value="caption">Caption Sosmed</option>
            </select>
          </label>
          <label className="text-sm">Platform
            <select className="mt-1 h-10 w-full rounded-lg border border-line bg-card px-2" value={platform} onChange={(event) => setPlatform(event.target.value)} disabled={kind !== 'caption'}>
              {['Instagram', 'X', 'LinkedIn', 'Facebook', 'TikTok'].map((name) => <option key={name}>{name}</option>)}
            </select>
          </label>
          <label className="text-sm">Topik
            <input className="mt-1 h-10 w-full rounded-lg border border-line px-2" value={topic} onChange={(event) => setTopic(event.target.value)} />
          </label>
          <label className="text-sm">Target audiens
            <input className="mt-1 h-10 w-full rounded-lg border border-line px-2" value={audience} onChange={(event) => setAudience(event.target.value)} />
          </label>
          <label className="text-sm">Tanggal rilis rencana
            <input type="date" className="mt-1 h-10 w-full rounded-lg border border-line px-2" value={releaseDate} onChange={(event) => setReleaseDate(event.target.value)} />
          </label>
        </div>
        <label className="mt-3 block text-sm">Draf
          <textarea className="mt-1 min-h-40 w-full rounded-lg border border-line p-3 text-sm" value={text} onChange={(event) => setText(event.target.value)} placeholder="Tempel draf di sini" />
        </label>
        <label className="mt-2 block text-sm">
          <input className="mr-2" type="file" accept=".txt,text/plain" onChange={async (event) => {
            const file = event.target.files?.[0]
            if (!file) return
            if (!file.name.endsWith('.txt')) {
              setError('Unggah .txt. Untuk .docx atau .pdf, salin teksnya ke kotak draf.')
              return
            }
            setText(await file.text())
          }} />
          Unggah .txt (docx/pdf: salin teksnya)
        </label>
        <label className="mt-3 flex items-start gap-2 text-sm">
          <input type="checkbox" checked={save} onChange={(event) => setSave(event.target.checked)} />
          Simpan riwayat di server. Tanpa centang, draf tidak disimpan.
        </label>
        <button className="mt-3 h-10 rounded-lg bg-navy-900 px-4 text-sm text-white disabled:opacity-60" disabled={loading || text.trim().length < 20} onClick={() => void submit()}>
          {loading ? 'Meninjau…' : 'Review Sekarang'}
        </button>
        <p className="mt-3 text-sm text-muted">Hasil review adalah alat bantu AI dan tidak menggantikan review resmi oleh Unit Hukum/Kepatuhan. Draf yang belum dirilis tidak disimpan kecuali Anda mencentang kotak di atas.</p>
      </Card>
      <Card className="mb-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-medium">Riwayat yang disimpan</h2>
          <button className="text-sm underline" onClick={() => void loadHistory()}>Muat riwayat</button>
        </div>
        {history.length === 0 ? <p className="mt-2 text-sm text-muted">Belum ada, atau belum dimuat. Hanya draf yang Anda setujui yang muncul di sini.</p> : (
          <ul className="mt-2 space-y-1 text-sm">
            {history.map((item) => (
              <li key={item.id}>
                <button className="underline" onClick={() => void openSaved(item.id)}>
                  {item.created_at} · {item.kind}{item.platform ? ` ${item.platform}` : ''} · skor {item.score} · {item.status}
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
      {error && <ErrorNote message={error} />}
      {notice && <p className="mb-3 text-sm" role="status">{notice}</p>}
      {result && !result.error && (
        <div>
          <Card className="mb-4">
            <p className="text-sm">{result.disclaimer}</p>
            <p className="mt-2 text-2xl font-bold">{result.score}<span className="text-base font-normal text-muted"> / 100 · {result.status}</span></p>
            <p className="mt-1 text-sm text-muted">
              Ambigu {result.counts.ambigu || 0} · Regulasi {result.counts.regulasi || 0} · Gaya {result.counts.gaya || 0} · Reputasi {result.counts.reputasi || 0}
              {result.method ? ` · ${result.method}` : ''}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button className="h-10 rounded-lg border border-line px-3 text-sm" onClick={() => setResult({ ...result, findings: result.findings.map((item) => ({ ...item, accepted: true })) })}>Terapkan semua saran</button>
              <button className="h-10 rounded-lg border border-line px-3 text-sm" onClick={() => void navigator.clipboard.writeText(revised)}>Salin versi final</button>
              <button className="h-10 rounded-lg border border-line px-3 text-sm" onClick={() => void exportDocx()}>Unduh .docx</button>
            </div>
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <h2 className="font-medium">Teks asli</h2>
              <Highlighted text={result.original} findings={result.findings} />
              <h2 className="mt-4 font-medium">Versi revisi</h2>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">{revised}</p>
            </Card>
            <div className="grid gap-3">
              {result.findings.length === 0 && <Card><p className="text-sm">Tidak ada temuan aturan pada draf ini. Tetap minta Unit Hukum meninjau sebelum terbit.</p></Card>}
              {result.findings.map((item, index) => (
                <article key={`${item.start}-${index}`} className={`rounded-md border p-3 text-sm ${RISKS[item.risiko as keyof typeof RISKS] || 'border-line'}`}>
                  <p className="font-medium">{item.kategori} · {item.risiko} {item.accepted ? '· diterima' : '· ditolak'}</p>
                  <p className="mt-2">{item.kalimat}</p>
                  <p className="mt-2">{item.masalah}</p>
                  <p className="mt-2 text-muted">{item.dasar_hukum}</p>
                  <p className="mt-2"><span className="font-medium">Saran: </span>{item.saran}</p>
                  <p className="mt-1"><span className="font-medium">Alasan: </span>{item.alasan}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button className="h-9 rounded border border-line px-2" onClick={() => update(index, { accepted: true })}>Terima</button>
                    <button className="h-9 rounded border border-line px-2" onClick={() => update(index, { accepted: false })}>Tolak</button>
                    <button className="h-9 rounded border border-line px-2" onClick={() => {
                      const next = window.prompt('Edit saran', item.saran)
                      if (next) update(index, { saran: next, accepted: true })
                    }}>Edit manual</button>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Highlighted({ text, findings }: { text: string; findings: Finding[] }) {
  const pieces: { text: string; className: string }[] = []
  let cursor = 0
  const marks = [...findings].sort((a, b) => a.start - b.start)
  for (const item of marks) {
    if (item.start < cursor || item.end > text.length) continue
    if (item.start > cursor) pieces.push({ text: text.slice(cursor, item.start), className: '' })
    const className = item.risiko === 'Tinggi' ? 'bg-red-200' : item.kategori === 'gaya' ? 'bg-sky-200' : 'bg-amber-200'
    pieces.push({ text: text.slice(item.start, item.end), className })
    cursor = item.end
  }
  if (cursor < text.length) pieces.push({ text: text.slice(cursor), className: '' })
  return <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">{pieces.map((piece, index) => <mark key={index} className={piece.className || 'bg-transparent'}>{piece.text}</mark>)}</p>
}

function applyLocal(original: string, findings: Finding[]) {
  const accepted = findings.filter((item) => item.accepted && item.saran).sort((a, b) => b.start - a.start)
  let text = original
  for (const item of accepted) {
    if (item.start >= 0 && item.end <= text.length && item.start < item.end) {
      text = text.slice(0, item.start) + item.saran + text.slice(item.end)
    }
  }
  return text
}
