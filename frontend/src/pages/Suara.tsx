import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../api'
import ChartInsight from '../components/ChartInsight'
import EvidenceList from '../components/EvidenceList'
import { Card, Empty, ErrorNote, Loading, PageHeader, StanceBadge } from '../components/Ui'
import { useFilters } from '../filters'
import type { IssueCard } from '../types'
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

interface Topics {
  words: { text: string; value: number }[]
  hashtags: { tag: string; count: number }[]
  entities: { name: string; count: number }[]
  method_note: string
}

const field = 'h-9 rounded-md border border-line bg-card px-2 text-sm'

export default function SuaraPage() {
  const filters = useFilters()
  const navigate = useNavigate()
  const [topic, setTopic] = useState('')
  const [segment, setSegment] = useState('')
  const [area, setArea] = useState('')
  const [term, setTerm] = useState('')
  const params = new URLSearchParams(filters.query)
  if (topic) params.set('topic', topic)
  if (segment) params.set('segment', segment)
  if (area) params.set('area', area)
  const data = useApi<Snapshot>(`/api/suara?${params.toString()}`)
  const issues = useApi<{ items: IssueCard[] }>(`/api/issues?${filters.query}`)
  const topics = useApi<Topics>(`/api/topics?${filters.query}`)
  const related = useApi<{ items: { text: string; value: number }[] }>(
    term ? `/api/topics/related?term=${encodeURIComponent(term)}&${filters.query}` : null,
  )
  const voiceQuery = new URLSearchParams({ topic, segment, area }).toString()
  const filtered = Boolean(topic || segment || area)
  const max = topics.data?.words[0]?.value || 1

  return (
    <div>
      <PageHeader
        title="Suara Publik"
        description="Apa yang ramai dibicarakan publik, tren kata, narasi, dan kelompok isu yang perlu ditinjau."
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

      {(data.loading || issues.loading || topics.loading) && <Loading />}
      {(data.error || issues.error) && <ErrorNote message={data.error || issues.error} />}

      {topics.data && (
        <div className="mb-4 grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <h2 className="font-medium">Kata yang paling sering muncul</h2>
            <p className="text-xs text-muted">Panjang batang adalah jumlah kemunculan. Klik kata untuk melihat kata yang sering muncul bersamanya.</p>
            <ul className="mt-3 space-y-2">
              {topics.data.words.slice(0, 10).map((word) => (
                <li key={word.text}>
                  <button className="grid w-full grid-cols-[8rem_1fr_2.5rem] items-center gap-2 text-left text-sm" onClick={() => setTerm(word.text)}>
                    <span className="truncate">{word.text}</span>
                    <span className="h-2 bg-line" aria-hidden>
                      <span className="block h-2 bg-navy-800" style={{ width: `${(word.value / max) * 100}%` }} />
                    </span>
                    <span className="text-right tabular-nums">{word.value}</span>
                  </button>
                </li>
              ))}
            </ul>
            {term && (
              <p className="mt-3 text-sm">
                Terkait <strong>{term}</strong>: {related.data?.items.map((item) => item.text).join(', ') || 'memuat...'}
              </p>
            )}
            <ChartInsight chart="kata" className="mt-4" />
          </Card>
          <Card>
            <h2 className="font-medium">Tagar</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {topics.data.hashtags.map((item) => (
                <button key={item.tag} className="rounded-full border border-line px-2 py-1 text-xs" onClick={() => navigate(`/explorer?q=${encodeURIComponent('#' + item.tag)}`)}>
                  #{item.tag} · {item.count}
                </button>
              ))}
            </div>
            <h2 className="mt-5 font-medium">Entitas</h2>
            <ul className="mt-2 space-y-1 text-sm">
              {topics.data.entities.map((item) => (
                <li key={item.name} className="flex justify-between gap-3"><span>{item.name}</span><span className="tabular-nums text-muted">{item.count}</span></li>
              ))}
            </ul>
            <p className="mt-4 text-xs text-muted">{topics.data.method_note}</p>
          </Card>
        </div>
      )}

      {data.data && data.data.total === 0 && <Card className="mb-4"><Empty label="Belum ada konten eksternal untuk pilihan ini. Ubah filter atau rentang tanggal." /></Card>}
      {data.data && data.data.total > 0 && (
        <div className="mb-4 grid gap-4 lg:grid-cols-3">
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

      <section aria-label="Kelompok isu">
        <h2 className="mb-3 text-sm font-bold uppercase tracking-[0.16em]">Kelompok isu</h2>
        <p className="mb-3 text-xs text-muted">Kelompok percakapan yang perlu ditinjau. Buka satu isu untuk melihat sumber dan saran.</p>
        <div className="grid gap-3">
          {(issues.data?.items || []).length === 0 && !issues.loading && (
            <Card><Empty label="Belum ada kelompok isu pada filter ini." /></Card>
          )}
          {issues.data?.items.map((issue) => (
            <button key={issue.id} className="min-h-11 rounded-md border border-line bg-card p-4 text-left" onClick={() => navigate(`/isu/${issue.id}`)}>
              <div className="flex flex-wrap items-center gap-2">
                <StanceBadge stance={issue.stance} />
                <span className="text-xs text-muted">{issue.category}</span>
                {issue.spike_detected && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-950">Lonjakan</span>}
                {issue.is_critical && <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-900">Kritis</span>}
              </div>
              <h3 className="mt-2 font-semibold">{issue.title}</h3>
              <p className="mt-1 text-justify text-sm leading-7 text-muted">{issue.summary}</p>
              <p className="mt-2 text-xs text-muted">{issue.mention_count} mention · risiko {issue.risk_score} · {issue.quadrant}</p>
            </button>
          ))}
        </div>
      </section>
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
