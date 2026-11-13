import { useMemo, useState } from 'react'
import { api, downloadPost } from '../api'
import { Card, ErrorNote, PageHeader } from '../components/Ui'

interface Finding {
  start: number
  end: number
  span_start?: number
  span_end?: number
  kalimat: string
  kategori: string
  risiko: 'Tinggi' | 'Sedang' | 'Rendah' | string
  masalah: string
  dasar_hukum: string
  saran: string
  alasan: string
  hapus?: string
  tambah?: string
  accepted: boolean
}

interface TrackPiece {
  tipe: 'teks' | 'hapus' | 'tambah'
  isi: string
  kategori?: string
  alasan?: string
}

interface ReviewResult {
  disclaimer: string
  original: string
  revised: string
  findings: Finding[]
  score: number
  status: string
  counts: Record<string, number>
  track?: TrackPiece[]
  error?: string
  method?: string
  uu_corpus?: string
  pendekatan?: string
  saved?: boolean
}

const RISKS = {
  Tinggi: 'border-red-300 bg-red-50',
  Sedang: 'border-amber-300 bg-amber-50',
  Rendah: 'border-sky-300 bg-sky-50',
}

const KATEGORI_LABEL: Record<string, string> = {
  regulasi: 'Peraturan (UU)',
  kata_baku: 'Kata baku',
  kejelasan: 'Kejelasan',
  reputasi: 'Reputasi kebijakan',
  implikasi_hukum: 'Implikasi hukum',
  ambigu: 'Kejelasan',
  gaya: 'Kata baku',
}

const FILTER_TABS = ['semua', 'regulasi', 'implikasi_hukum', 'kata_baku', 'kejelasan'] as const
type FilterTab = (typeof FILTER_TABS)[number]

export default function ReviewPage() {
  const [text, setText] = useState('')
  const [save, setSave] = useState(false)
  const [result, setResult] = useState<ReviewResult | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState('')
  const [filter, setFilter] = useState<FilterTab>('semua')
  const [history, setHistory] = useState<{ id: number; created_at: string; kind: string; platform: string; score: number; status: string }[]>([])

  const revised = useMemo(() => (result ? applyLocal(result.original, result.findings) : ''), [result])

  const visibleFindings = useMemo(() => {
    if (!result) return []
    if (filter === 'semua') return result.findings
    return result.findings.filter((item) => normalizeKategori(item.kategori) === filter)
  }, [result, filter])

  const trackPieces = useMemo(() => {
    if (!result) return [] as TrackPiece[]
    return buildTrackLocal(result.original, result.findings)
  }, [result])

  async function submit() {
    setLoading(true)
    setError('')
    setNotice('')
    try {
      const data = await api<ReviewResult>('/api/review', {
        method: 'POST',
        body: JSON.stringify({ kind: 'siaran', text, save }),
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
        description="Periksa draf dari tiga sudut: kepatuhan UU, kata baku Indonesia, dan kejelasan kata. Saran ditampilkan ala track changes beserta alasan."
      />
      <Card className="mb-4">
        <label className="block text-sm">Draf
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
            {result.pendekatan ? (
              <p className="mt-2 rounded-lg border border-line bg-card px-3 py-2 text-xs text-muted">{result.pendekatan}</p>
            ) : null}
            <p className="mt-2 text-2xl font-bold">{result.score}<span className="text-base font-normal text-muted"> / 100 · {result.status}</span></p>
            <p className="mt-1 text-sm text-muted">
              UU / regulasi {result.counts.regulasi || 0} · Implikasi hukum {result.counts.implikasi_hukum || 0} · Kata baku {result.counts.kata_baku || 0} · Kejelasan {result.counts.kejelasan || 0}
              {(result.counts.reputasi || 0) > 0 ? ` · Reputasi ${result.counts.reputasi}` : ''}
              {result.method ? ` · ${result.method}` : ''}
              {result.uu_corpus ? (
                <span className="block text-xs text-muted">{result.uu_corpus}</span>
              ) : null}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button className="h-10 rounded-lg border border-line px-3 text-sm" onClick={() => setResult({ ...result, findings: result.findings.map((item) => ({ ...item, accepted: true })) })}>Terapkan semua saran</button>
              <button className="h-10 rounded-lg border border-line px-3 text-sm" onClick={() => void navigator.clipboard.writeText(revised)}>Salin versi final</button>
              <button className="h-10 rounded-lg border border-line px-3 text-sm" onClick={() => void exportDocx()}>Unduh .docx</button>
            </div>
          </Card>
          <div className="mb-3 flex flex-wrap gap-2">
            {FILTER_TABS.map((tab) => (
              <button
                key={tab}
                type="button"
                className={`h-9 rounded-lg border px-3 text-sm ${filter === tab ? 'border-navy-900 bg-navy-900 text-white' : 'border-line'}`}
                onClick={() => setFilter(tab)}
              >
                {tab === 'semua' ? 'Semua temuan' : KATEGORI_LABEL[tab]}
              </button>
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <h2 className="font-medium">Track changes (saran diterima)</h2>
              <TrackChanges pieces={trackPieces} />
              <h2 className="mt-4 font-medium">Teks asli (penanda risiko)</h2>
              <Highlighted text={result.original} findings={result.findings} />
              <h2 className="mt-4 font-medium">Versi revisi</h2>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">{revised}</p>
            </Card>
            <div className="grid gap-3">
              {visibleFindings.length === 0 && <Card><p className="text-sm">Tidak ada temuan pada filter ini. Tetap minta Unit Hukum meninjau sebelum terbit.</p></Card>}
              {visibleFindings.map((item) => {
                const index = result.findings.indexOf(item)
                return (
                  <article key={`${item.start}-${index}`} className={`rounded-md border p-3 text-sm ${RISKS[item.risiko as keyof typeof RISKS] || 'border-line'}`}>
                    <p className="font-medium">{KATEGORI_LABEL[normalizeKategori(item.kategori)] || item.kategori} · {item.risiko} {item.accepted ? '· diterima' : '· ditolak'}</p>
                    {(item.hapus || item.tambah) && (
                      <p className="mt-2 rounded border border-line bg-card p-2 leading-relaxed">
                        <del className="text-red-700 decoration-red-700">{item.hapus || item.kalimat}</del>
                        {' '}
                        <ins className="font-medium text-emerald-800 underline decoration-emerald-700">{item.tambah ?? item.saran}</ins>
                      </p>
                    )}
                    <p className="mt-2 text-muted">{item.kalimat}</p>
                    <p className="mt-2">{item.masalah}</p>
                    <p className="mt-2 text-muted">{item.dasar_hukum}</p>
                    <p className="mt-2"><span className="font-medium">Saran: </span>{item.saran}</p>
                    <p className="mt-1"><span className="font-medium">Alasan: </span>{item.alasan}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button className="h-9 rounded border border-line px-2" onClick={() => update(index, { accepted: true })}>Terima</button>
                      <button className="h-9 rounded border border-line px-2" onClick={() => update(index, { accepted: false })}>Tolak</button>
                      <button className="h-9 rounded border border-line px-2" onClick={() => {
                        const next = window.prompt('Edit teks sisipan (tambah)', item.tambah ?? item.saran)
                        if (next != null) update(index, { tambah: next, saran: next, accepted: true })
                      }}>Edit manual</button>
                    </div>
                  </article>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function TrackChanges({ pieces }: { pieces: TrackPiece[] }) {
  if (!pieces.length) {
    return <p className="mt-2 text-sm text-muted">Tidak ada perubahan otomatis. Terima saran di panel kanan untuk melihat track changes.</p>
  }
  return (
    <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">
      {pieces.map((piece, index) => {
        if (piece.tipe === 'hapus') {
          return <del key={index} className="bg-red-100 text-red-900 line-through decoration-red-700">{piece.isi}</del>
        }
        if (piece.tipe === 'tambah') {
          return <ins key={index} className="bg-emerald-100 text-emerald-900 underline decoration-emerald-700">{piece.isi}</ins>
        }
        return <span key={index}>{piece.isi}</span>
      })}
    </p>
  )
}

function Highlighted({ text, findings }: { text: string; findings: Finding[] }) {
  const pieces: { text: string; className: string }[] = []
  let cursor = 0
  const marks = [...findings].sort((a, b) => a.start - b.start)
  for (const item of marks) {
    if (item.start < cursor || item.end > text.length) continue
    if (item.start > cursor) pieces.push({ text: text.slice(cursor, item.start), className: '' })
    const cat = normalizeKategori(item.kategori)
    const className =
      item.risiko === 'Tinggi' ? 'bg-red-200'
        : cat === 'implikasi_hukum' ? 'bg-rose-200'
          : cat === 'regulasi' ? 'bg-violet-200'
          : cat === 'kata_baku' ? 'bg-sky-200'
            : 'bg-amber-200'
    pieces.push({ text: text.slice(item.start, item.end), className })
    cursor = item.end
  }
  if (cursor < text.length) pieces.push({ text: text.slice(cursor), className: '' })
  return <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">{pieces.map((piece, index) => <mark key={index} className={piece.className || 'bg-transparent'}>{piece.text}</mark>)}</p>
}

function normalizeKategori(kategori: string) {
  const k = (kategori || '').toLowerCase()
  if (k === 'gaya') return 'kata_baku'
  if (k === 'ambigu') return 'kejelasan'
  return k
}

function buildTrackLocal(original: string, findings: Finding[]): TrackPiece[] {
  const regions = findings
    .filter((item) => item.accepted)
    .map((item) => {
      const start = item.span_start ?? item.start
      const end = item.span_end ?? item.end
      const hapus = item.hapus ?? original.slice(start, end)
      let tambah = item.tambah
      if (tambah == null && start === item.start && end === item.end) tambah = item.saran
      return { start, end, hapus, tambah }
    })
    .filter((r) => r.hapus || r.tambah)
    .sort((a, b) => a.start - b.start)

  const pieces: TrackPiece[] = []
  let cursor = 0
  for (const region of regions) {
    if (region.start < cursor) continue
    if (region.start > cursor) pieces.push({ tipe: 'teks', isi: original.slice(cursor, region.start) })
    if (region.hapus) pieces.push({ tipe: 'hapus', isi: region.hapus })
    if (region.tambah) pieces.push({ tipe: 'tambah', isi: region.tambah })
    cursor = Math.max(cursor, region.end)
  }
  if (cursor < original.length) pieces.push({ tipe: 'teks', isi: original.slice(cursor) })
  return pieces
}

function applyLocal(original: string, findings: Finding[]) {
  const accepted = findings.filter((item) => item.accepted).sort((a, b) => (b.span_start ?? b.start) - (a.span_start ?? a.start))
  let text = original
  for (const item of accepted) {
    const start = item.span_start ?? item.start
    const end = item.span_end ?? item.end
    let tambah = item.tambah
    if (tambah == null) {
      if (start === item.start && end === item.end) tambah = item.saran
      else continue
    }
    if (start >= 0 && end <= text.length && start < end) {
      text = text.slice(0, start) + tambah + text.slice(end)
    } else if (start >= 0 && end <= text.length && start === end && tambah !== undefined) {
      text = text.slice(0, start) + tambah + text.slice(end)
    }
  }
  return text
}
