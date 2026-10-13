import { useState } from 'react'
import { useApi } from '../api'
import ChartInsight from '../components/ChartInsight'
import EvidenceList from '../components/EvidenceList'
import { Card, Empty, ErrorNote, Loading, PageHeader } from '../components/Ui'
import { useFilters } from '../filters'
import { AREAS, SEGMENTS, TOPICS, type Count, type Narrative } from '../voice'

interface Snapshot {
  total: number
  komposisi: { id: string; label: string; jumlah: number; pangsa: number }[]
  topik: Count[]
  segmen: Count[]
  wilayah: Count[]
  narasi: Narrative[]
  topik_ramai: string[]
  ramai_tersedia: boolean
  aturan_ramai: string
  disclaimer: string
  metode: string
}

const field = 'h-9 rounded-md border border-line bg-card px-2 text-sm'

export default function SuaraPage() {
  const filters = useFilters()
  const [topic, setTopic] = useState('')
  const [segment, setSegment] = useState('')
  const [area, setArea] = useState('')
  const params = new URLSearchParams(filters.query)
  if (topic) params.set('topic', topic)
  if (segment) params.set('segment', segment)
  if (area) params.set('area', area)
  const data = useApi<Snapshot>(`/api/suara?${params.toString()}`)
  const voiceQuery = new URLSearchParams({ topic, segment, area }).toString()
  const filtered = Boolean(topic || segment || area)

  return (
    <div>
      <PageHeader
        title="Suara Publik"
        description="Apa yang ramai, dikeluhkan, dipuji, dibutuhkan, dan disalahpahami publik tentang BI, ekonomi, dan sistem pembayaran."
      />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select className={field} value={topic} onChange={(event) => setTopic(event.target.value)} aria-label="Topik">
          <option value="">Semua topik</option>
          {TOPICS.map((item) => <option key={item}>{item}</option>)}
        </select>
        <select className={field} value={segment} onChange={(event) => setSegment(event.target.value)} aria-label="Segmen">
          <option value="">Semua segmen</option>
          {SEGMENTS.map((item) => <option key={item}>{item}</option>)}
        </select>
        <select className={field} value={area} onChange={(event) => setArea(event.target.value)} aria-label="Wilayah">
          <option value="">Semua wilayah</option>
          {AREAS.map((item) => <option key={item}>{item}</option>)}
          <option value="tidak-diketahui">Wilayah tidak diketahui</option>
        </select>
        {filtered && (
          <button className="h-9 rounded-md border border-line px-3 text-sm" onClick={() => { setTopic(''); setSegment(''); setArea('') }}>
            Reset filter
          </button>
        )}
      </div>
      {data.loading && <Loading />}
      {data.error && <ErrorNote message={data.error} />}
      {data.data && data.data.total === 0 && <Card><Empty label="Belum ada konten eksternal untuk pilihan ini. Ubah filter atau rentang tanggal." /></Card>}
      {data.data && data.data.total > 0 && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <h2 className="font-medium">Komposisi suara publik</h2>
            <p className="text-xs text-muted">Dari {data.data.total} konten eksternal. Satu konten bisa masuk lebih dari satu dimensi.</p>
            <ul className="mt-3 space-y-2">
              {data.data.komposisi.map((item) => (
                <li key={item.id} className="grid grid-cols-[11rem_1fr_9rem] items-center gap-2 text-sm">
                  <span>{item.label}</span>
                  <span className="h-2 bg-line" aria-hidden>
                    <span className="block h-2 bg-navy-800" style={{ width: `${item.pangsa}%` }} />
                  </span>
                  <span className="text-right tabular-nums">
                    {item.id === 'ramai' && !data.data?.ramai_tersedia ? 'belum bisa dihitung' : `${item.jumlah} · ${item.pangsa.toLocaleString('id-ID')}%`}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-muted">{data.data.aturan_ramai}</p>
            {data.data.topik_ramai.length > 0 && <p className="mt-1 text-sm">Topik ramai: {data.data.topik_ramai.join(', ')}</p>}
            <ChartInsight chart="suara" extraQuery={voiceQuery} className="mt-4" />
          </Card>
          <Card>
            <h2 className="font-medium">Segmen audiens</h2>
            <p className="text-xs text-muted">Dibaca dari kata di konten. Akun tidak diprofilkan.</p>
            <CountList items={data.data.segmen} />
            <h2 className="mt-4 font-medium">Wilayah</h2>
            <CountList items={data.data.wilayah} />
          </Card>
          <Card className="lg:col-span-3">
            <h2 className="font-medium">Narasi yang terbaca</h2>
            <p className="text-xs text-muted">Narasi dikenali dari pasangan kata pada judul dan cuplikan. Pengusung dicatat sebagai nama media atau kanal, tanpa profil orang.</p>
            {data.data.narasi.length === 0 && <p className="mt-2 text-sm text-muted">Belum ada pola narasi yang cocok pada data ini.</p>}
            <div className="mt-3 grid gap-4 md:grid-cols-2">
              {data.data.narasi.map((item) => (
                <div key={item.label} className="border-t border-line pt-3">
                  <p className="font-medium">{item.label} · <span className="tabular-nums">{item.jumlah}</span> konten</p>
                  <p className="text-xs text-muted">Diangkat oleh: {item.sumber.join(', ')}</p>
                  <div className="mt-2"><EvidenceList items={item.bukti} limit={3} /></div>
                </div>
              ))}
            </div>
          </Card>
          <p className="text-xs text-muted lg:col-span-3">{data.data.metode} {data.data.disclaimer}</p>
        </div>
      )}
    </div>
  )
}

function CountList({ items }: { items: Count[] }) {
  const sorted = [...items].sort((a, b) => b.jumlah - a.jumlah)
  return (
    <ul className="mt-2 divide-y divide-line text-sm">
      {sorted.map((item) => (
        <li key={item.label} className="flex justify-between gap-3 py-1.5">
          <span>{item.label}</span>
          <span className="tabular-nums text-muted">{item.jumlah}</span>
        </li>
      ))}
    </ul>
  )
}
