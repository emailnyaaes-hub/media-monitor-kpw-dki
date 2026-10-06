import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { downloadFile, useApi } from '../api'
import MentionDrawer from '../components/MentionDrawer'
import { Card, Empty, ErrorNote, Loading, PageHeader, QuoteBadge, SentimentBadge, SourceLink, StanceBadge, StatusBadge, inputClass } from '../components/Ui'
import { useFilters } from '../filters'
import { formatWhen, PLATFORM_LABEL, relativeTime, SOURCES, STATUS_LABEL } from '../format'
import type { MentionCard } from '../types'

export default function ExplorerPage() {
  const filters = useFilters()
  const [params, setParams] = useSearchParams()
  const [q, setQ] = useState(params.get('q') || '')
  const [sentiment, setSentiment] = useState('')
  const [stance, setStance] = useState('')
  const [status, setStatus] = useState('')
  const [source, setSource] = useState('')
  const [minRisk, setMinRisk] = useState('')
  const [sort, setSort] = useState('terbaru')
  const [page, setPage] = useState(1)
  const [density, setDensity] = useState<'nyaman' | 'ringkas'>(() => (localStorage.getItem('bi-density') === 'ringkas' ? 'ringkas' : 'nyaman'))
  const [openId, setOpenId] = useState<number | null>(params.get('m') ? Number(params.get('m')) : null)

  useEffect(() => {
    const mention = params.get('m')
    if (mention) setOpenId(Number(mention))
    const query = params.get('q')
    if (query) setQ(query)
  }, [params])

  const query = new URLSearchParams(filters.query)
  if (q) query.set('q', q)
  if (sentiment) query.set('sentiment', sentiment)
  if (stance) query.set('stance', stance)
  if (status) query.set('status', status)
  if (source) query.set('source', source)
  if (minRisk) query.set('min_risk', minRisk)
  query.set('sort', sort)
  query.set('page', String(page))
  query.set('page_size', '15')

  const data = useApi<{ total: number; items: MentionCard[] }>(`/api/mentions?${query.toString()}`)
  const pages = Math.max(1, Math.ceil((data.data?.total || 0) / 15))

  return (
    <div>
      <PageHeader title="Jelajah Berita" description="Cari berita dan unggahan, lalu buka sumber aslinya." />
      <Card className="mb-4">
        <div className="grid gap-2 md:grid-cols-4">
          <input className={inputClass} placeholder="Cari judul atau teks" value={q} onChange={(event) => { setQ(event.target.value); setPage(1) }} />
          <select className={inputClass} value={sentiment} onChange={(event) => { setSentiment(event.target.value); setPage(1) }}>
            <option value="">Semua sentimen</option>
            <option value="positif">Positif</option>
            <option value="netral">Netral</option>
            <option value="negatif">Negatif</option>
          </select>
          <select className={inputClass} value={stance} onChange={(event) => { setStance(event.target.value); setPage(1) }}>
            <option value="">Semua stance</option>
            <option value="upside">Upside</option>
            <option value="netral">Netral</option>
            <option value="downside">Downside</option>
          </select>
          <select className={inputClass} value={status} onChange={(event) => { setStatus(event.target.value); setPage(1) }}>
            <option value="">Semua status</option>
            {Object.entries(STATUS_LABEL).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
          </select>
          <select className={inputClass} value={source} onChange={(event) => { setSource(event.target.value); setPage(1) }}>
            <option value="">Semua media</option>
            {SOURCES.map((item) => <option key={item}>{item}</option>)}
          </select>
          <input className={inputClass} type="number" min={0} max={100} placeholder="Risiko minimum" value={minRisk} onChange={(event) => { setMinRisk(event.target.value); setPage(1) }} />
          <select className={inputClass} value={sort} onChange={(event) => setSort(event.target.value)}>
            <option value="terbaru">Terbaru</option>
            <option value="risiko">Risiko tertinggi</option>
            <option value="jangkauan">Jangkauan tertinggi</option>
          </select>
          <button className="h-9 rounded-lg border border-line text-sm" onClick={() => downloadFile(`/api/export/mentions.csv?${query.toString()}`, 'mention.csv')}>
            Unduh CSV
          </button>
        </div>
      </Card>
      {data.loading && <Loading />}
      {data.error && <ErrorNote message={data.error} />}
      {data.data && data.data.items.length === 0 && <Empty label="Belum ada berita untuk filter ini. Coba perluas rentang tanggal." />}
      {data.data && data.data.items.length > 0 && (
        <Card className="overflow-x-auto">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-muted">{data.data.total} berita</p>
            <div className="flex gap-1">
              {(['nyaman', 'ringkas'] as const).map((item) => (
                <button key={item} className={`h-11 rounded-md px-3 text-sm capitalize ${density === item ? 'bg-navy-900 text-white' : 'border border-line'}`} onClick={() => { setDensity(item); localStorage.setItem('bi-density', item) }}>
                  {item === 'nyaman' ? 'Nyaman' : 'Ringkas'}
                </button>
              ))}
            </div>
          </div>
          <ul className="divide-y divide-line md:hidden">
            {data.data.items.map((item) => (
              <li key={item.id} className="py-3">
                <button className="text-left" onClick={() => { setOpenId(item.id); setParams({ m: String(item.id) }) }}>
                  <span className="text-sm text-muted" title={`${formatWhen(item.published_at)} WIB`}>{item.source_name} · {relativeTime(item.published_at)}</span>
                  <span className="line-clamp-2 mt-1 block text-base">{item.title}</span>
                </button>
                <SourceLink url={item.url} />
              </li>
            ))}
          </ul>
          <table className={`hidden w-full min-w-[860px] text-left md:table ${density === 'ringkas' ? 'text-sm' : 'text-base'}`}>
            <thead className="sticky top-0 bg-card text-sm text-muted">
              <tr>
                <th className="py-2 pr-3">Waktu</th><th className="pr-3">Judul</th><th className="pr-3">Sumber</th><th className="pr-3">Stance</th><th className="pr-3">Sentimen</th><th className="pr-3">Risiko</th><th className="pr-3">Status</th><th>Tautan</th>
              </tr>
            </thead>
            <tbody>
              {data.data.items.map((item) => (
                <tr key={item.id} className="cursor-pointer border-t border-line" onClick={() => { setOpenId(item.id); setParams({ m: String(item.id) }) }}>
                  <td className={`${density === 'ringkas' ? 'py-2' : 'py-3'} whitespace-nowrap pr-3`} title={`${formatWhen(item.published_at)} WIB`}>{relativeTime(item.published_at)}</td>
                  <td className="max-w-md pr-3"><span className="line-clamp-2"><QuoteBadge show={item.quotes_bi} /> {item.title}</span></td>
                  <td className="pr-3">{item.source_name}<span className="block text-sm text-muted">{PLATFORM_LABEL[item.platform]}</span></td>
                  <td className="pr-3"><StanceBadge stance={item.stance} /></td>
                  <td className="pr-3"><SentimentBadge sentiment={item.sentiment} /></td>
                  <td className="pr-3 tabular-nums" title="Skor risiko menggabungkan nada, kecepatan sebar, dan kredibilitas sumber.">{item.risk_score}</td>
                  <td className="pr-3"><StatusBadge status={item.status} /></td>
                  <td><SourceLink url={item.url} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-3 flex items-center justify-between text-base">
            <button className="h-11 rounded-md border border-line px-3" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Sebelumnya</button>
            <span>Halaman {page} dari {pages}</span>
            <button className="h-11 rounded-md border border-line px-3" disabled={page >= pages} onClick={() => setPage((value) => value + 1)}>Berikutnya</button>
          </div>
        </Card>
      )}
      {openId && (
        <MentionDrawer
          id={openId}
          onClose={() => { setOpenId(null); params.delete('m'); setParams(params) }}
          onSaved={data.reload}
        />
      )}
    </div>
  )
}
