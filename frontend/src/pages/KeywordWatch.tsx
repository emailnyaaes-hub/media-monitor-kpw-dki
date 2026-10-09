import { FormEvent, useEffect, useState } from 'react'
import { api, downloadFile, useApi } from '../api'
import { Donut, KeywordBars, KeywordLines } from '../components/Charts'
import MentionDrawer from '../components/MentionDrawer'
import { Empty, ErrorNote, SentimentBadge, SourceLink } from '../components/Ui'
import { useAuth } from '../auth'
import { useFilters } from '../filters'
import { formatDay, formatNumber, formatPct, formatSigned } from '../format'
import type { MentionCard } from '../types'

interface WatchKeyword {
  id: number
  term: string
  category: string
  color: string
  is_active: boolean
  count?: number
}

interface WatchPayload {
  catalog: WatchKeyword[]
  keywords: WatchKeyword[]
  kpis: {
    total: number
    previous: number
    delta: number
    delta_pct: number | null
    top_keyword: { term: string; count: number } | null
    sentiment_pct: { positif: number; netral: number; negatif: number }
  }
  trend: { points: Record<string, string | number>[]; series: { term: string; color: string }[] }
  volumes: WatchKeyword[]
  sources: { name: string; count: number; platform: string }[]
  cowords: { text: string; value: number }[]
  heatmap: { days: string[]; hours: number[]; cells: number[][] }
  alerts: { kind: string; title: string; detail: string; marker?: string }[]
  fx: { available: boolean; note: string }
}

const GROUPS = ['Valuta asing', 'Regulasi/Industri', 'Dompet digital/Fintech']
const TABS = ['Grafik', 'Berita', 'Detail'] as const
const NAVY = '#0B1F3A'
const field = 'h-9 rounded-md border border-line bg-card px-2 text-sm'

export default function KeywordWatchPage() {
  const filters = useFilters()
  const { user } = useAuth()
  const writer = user?.role === 'admin' || user?.role === 'analis'
  const [tab, setTab] = useState<(typeof TABS)[number]>('Grafik')
  const [keyword, setKeyword] = useState('')
  const [group, setGroup] = useState('semua')
  const [grain, setGrain] = useState<'day' | 'week' | 'month'>('day')
  const [sentiment, setSentiment] = useState('')
  const [q, setQ] = useState('')
  const [sort, setSort] = useState('terbaru')
  const [page, setPage] = useState(1)
  const [weekday, setWeekday] = useState<number | null>(null)
  const [hour, setHour] = useState<number | null>(null)
  const [openId, setOpenId] = useState<number | null>(null)
  const [more, setMore] = useState(false)
  const [term, setTerm] = useState('')
  const [category, setCategory] = useState(GROUPS[0])
  const [error, setError] = useState('')

  const catalogQuery = useApi<WatchPayload>(`/api/keyword-watch?grain=${grain}&${filters.query}`)
  const catalog = (catalogQuery.data?.catalog || []).filter((item) => item.is_active)
  const visible = catalog.filter((item) => group === 'semua' || item.category === group)
  const selected = keyword && visible.some((item) => item.term === keyword) ? [keyword] : visible.map((item) => item.term)

  const watchParams = new URLSearchParams(filters.query)
  watchParams.set('grain', grain)
  if (selected.length) watchParams.set('terms', selected.join(','))
  const watch = useApi<WatchPayload>(catalogQuery.data ? `/api/keyword-watch?${watchParams.toString()}` : null)

  const tableParams = new URLSearchParams(filters.query)
  if (selected.length) tableParams.set('keywords', selected.join(','))
  if (sentiment) tableParams.set('sentiment', sentiment)
  if (q) tableParams.set('q', q)
  if (weekday !== null) tableParams.set('weekday', String(weekday))
  if (hour !== null) tableParams.set('hour', String(hour))
  tableParams.set('sort', sort)
  tableParams.set('page', String(page))
  tableParams.set('page_size', '8')
  const table = useApi<{ total: number; items: MentionCard[] }>(catalogQuery.data ? `/api/mentions?${tableParams.toString()}` : null)
  const data = watch.data
  const pages = Math.max(1, Math.ceil((table.data?.total || 0) / 8))
  const linePoints = (data?.trend.points || []).map((point) => {
    const total = (data?.trend.series || []).reduce((sum, item) => sum + Number(point[item.term] || 0), 0)
    return { date: point.date, Jumlah: total }
  })
  const ranked = [...(data?.volumes || [])].sort((a, b) => (b.count || 0) - (a.count || 0))
  const change = !data
    ? ''
    : data.kpis.previous < 5
      ? `${data.kpis.delta > 0 ? 'naik' : data.kpis.delta < 0 ? 'turun' : 'tetap'} ${formatNumber(Math.abs(data.kpis.delta))} dari periode lalu`
      : `${formatSigned(data.kpis.delta_pct || 0, '%')} dari periode lalu`

  useEffect(() => {
    setPage(1)
  }, [keyword, sentiment, q, weekday, hour, sort, group, filters.query])

  function resetLocal() {
    setKeyword('')
    setGroup('semua')
    setSentiment('')
    setQ('')
    setSort('terbaru')
    setWeekday(null)
    setHour(null)
    setPage(1)
    setTab('Grafik')
    filters.reset()
  }

  function openDay(date?: string) {
    if (!date || grain !== 'day') return
    const day = String(date).slice(0, 10)
    filters.setDateFrom(day)
    filters.setDateTo(day)
  }

  async function addTerm(event: FormEvent) {
    event.preventDefault()
    setError('')
    try {
      await api('/api/keywords', {
        method: 'POST',
        body: JSON.stringify({ term, category, mode: 'inklusi', is_active: true }),
      })
      setKeyword(term)
      setTerm('')
      catalogQuery.reload()
      watch.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Gagal menambah kata')
    }
  }

  async function removeTerm(row: WatchKeyword) {
    setError('')
    try {
      await api(`/api/keywords/${row.id}`, { method: 'DELETE' })
      if (keyword === row.term) setKeyword('')
      catalogQuery.reload()
      watch.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Gagal menghapus kata')
    }
  }

  return (
    <div className="flex flex-col gap-2 md:h-[calc(100dvh-12.5rem)] md:overflow-hidden">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="mr-1 text-base font-medium">Pantauan kata</h1>
        <button className={field} onClick={() => filters.setPreset(1)}>Hari ini</button>
        <button className={field} onClick={() => filters.setPreset(7)}>7 hari</button>
        <button className={field} onClick={() => filters.setPreset(30)}>30 hari</button>
        <select className={field} value={keyword} onChange={(event) => setKeyword(event.target.value)} aria-label="Kata">
          <option value="">Semua kata</option>
          {visible.map((item) => <option key={item.id} value={item.term}>{item.term}</option>)}
        </select>
        <select className={field} value={sentiment} onChange={(event) => setSentiment(event.target.value)} aria-label="Sentimen">
          <option value="">Semua suasana</option>
          <option value="positif">Positif</option>
          <option value="netral">Netral</option>
          <option value="negatif">Negatif</option>
        </select>
        <button className={field} onClick={() => setMore((value) => !value)} aria-expanded={more}>Filter lanjutan</button>
        {(keyword || sentiment || q || weekday !== null) && <button className="text-sm underline" onClick={resetLocal}>Reset filter</button>}
        <button className="ml-auto h-9 rounded-md bg-navy-900 px-3 text-sm text-white" onClick={() => downloadFile(`/api/export/mentions.csv?${tableParams.toString()}`, 'berita-kata-kunci.csv')}>Unduh CSV</button>
      </div>
      {more && (
        <div className="flex flex-wrap items-end gap-2 border border-line bg-card p-2">
          <label className="grid gap-1 text-xs text-muted">
            Kelompok
            <select className={field} value={group} onChange={(event) => { setGroup(event.target.value); setKeyword('') }}>
              <option value="semua">Semua</option>
              {GROUPS.map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
          <label className="grid gap-1 text-xs text-muted">
            Cari judul
            <input className={field} value={q} onChange={(event) => setQ(event.target.value)} />
          </label>
          <label className="grid gap-1 text-xs text-muted">
            Urutan
            <select className={field} value={sort} onChange={(event) => setSort(event.target.value)}>
              <option value="terbaru">Terbaru</option>
              <option value="risiko">Perlu perhatian</option>
              <option value="jangkauan">Paling tersebar</option>
            </select>
          </label>
          <button className={field} onClick={() => downloadFile(`/api/export/mentions.xlsx?${tableParams.toString()}`, 'berita-kata-kunci.xlsx')}>Unduh Excel</button>
          {writer && (
            <form className="flex flex-wrap items-end gap-2" onSubmit={addTerm}>
              <label className="grid gap-1 text-xs text-muted">
                Kata baru
                <input className={field} value={term} onChange={(event) => setTerm(event.target.value)} required />
              </label>
              <select className={field} value={category} onChange={(event) => setCategory(event.target.value)} aria-label="Kelompok kata baru">
                {GROUPS.map((item) => <option key={item}>{item}</option>)}
              </select>
              <button className="h-9 rounded-md border border-line px-3 text-sm">Tambah</button>
            </form>
          )}
          {writer && (
            <label className="grid gap-1 text-xs text-muted">
              Hapus kata
              <select className={field} defaultValue="" onChange={(event) => {
                const row = visible.find((item) => item.term === event.target.value)
                event.target.value = ''
                if (row) removeTerm(row)
              }}>
                <option value="">Pilih kata</option>
                {visible.map((item) => <option key={item.id} value={item.term}>{item.term}</option>)}
              </select>
            </label>
          )}
        </div>
      )}
      {(error || catalogQuery.error || watch.error) && <ErrorNote message={error || catalogQuery.error || watch.error} />}
      <div className="flex gap-1 border-b border-line">
        {TABS.map((item) => (
          <button key={item} className={`h-9 px-3 text-sm ${tab === item ? 'border-b-2 border-navy-900 font-medium' : 'text-muted'}`} onClick={() => setTab(item)}>
            {item}
          </button>
        ))}
      </div>

      {tab === 'Grafik' && data && (
        <div className="flex min-h-0 flex-1 flex-col gap-2">
          <div className="grid grid-cols-2 gap-2 xl:grid-cols-4">
            <Stat label="Jumlah berita" value={formatNumber(data.kpis.total)} />
            <Stat label="Naik atau turun" value={data.kpis.previous < 5 ? formatSigned(data.kpis.delta) : formatSigned(data.kpis.delta_pct || 0, '%')} note={change} />
            <Stat label="Paling sering disebut" value={data.kpis.top_keyword?.term || 'Belum ada'} note={data.kpis.top_keyword ? `${formatNumber(data.kpis.top_keyword.count)} berita` : ''} />
            <Stat label="Suasana berita" value={`${formatPct(data.kpis.sentiment_pct.positif)} positif`} note={`netral ${formatPct(data.kpis.sentiment_pct.netral)} · negatif ${formatPct(data.kpis.sentiment_pct.negatif)}`} />
          </div>
          <div className="grid min-h-0 flex-1 gap-2 lg:grid-cols-5">
            <section className="flex min-h-[11rem] flex-col border border-line bg-card p-3 lg:col-span-3">
              <div className="mb-1 flex items-center justify-between gap-2">
                <h2 className="text-sm font-medium">Banyak dibicarakan</h2>
                <div className="flex gap-1">
                  {(['day', 'week', 'month'] as const).map((item) => (
                    <button key={item} className={`h-7 rounded-md px-2 text-xs ${grain === item ? 'bg-navy-900 text-white' : 'border border-line'}`} onClick={() => setGrain(item)}>
                      {item === 'day' ? 'Harian' : item === 'week' ? 'Mingguan' : 'Bulanan'}
                    </button>
                  ))}
                </div>
              </div>
              {linePoints.length === 0 ? <Empty label="Tidak ada berita pada rentang ini." /> : <KeywordLines className="h-44 min-h-0 flex-1 lg:h-auto" data={linePoints} series={[{ term: 'Jumlah', color: NAVY }]} onPick={(_term, date) => openDay(date)} />}
            </section>
            <section className="flex min-h-[11rem] flex-col border border-line bg-card p-3 lg:col-span-2">
              <h2 className="mb-1 text-sm font-medium">Urutan kata</h2>
              {ranked.every((item) => !item.count) ? <Empty label="Tidak ada kata yang cocok." /> : <KeywordBars className="h-44 min-h-0 flex-1 lg:h-auto" data={ranked.map((item) => ({ term: item.term, count: item.count || 0, color: NAVY }))} onPick={(value) => { setKeyword(value); setTab('Berita') }} />}
            </section>
          </div>
        </div>
      )}

      {tab === 'Berita' && data && (
        <section className="min-h-0 flex-1 overflow-auto border border-line bg-card px-3 py-2">
            <div className="mb-1 flex items-center justify-between gap-2">
              <h2 className="text-sm font-medium">Berita terbaru</h2>
              <span className="text-xs text-muted">{formatNumber(table.data?.total || 0)} berita</span>
            </div>
            {table.data && table.data.items.length === 0 && (
              <div className="py-3">
                <Empty label="Tidak ada berita untuk filter ini." />
                <button className="mt-2 text-sm underline" onClick={resetLocal}>Reset filter</button>
              </div>
            )}
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-muted">
                <tr>
                  <th className="py-1 pr-2">Tanggal</th>
                  <th className="pr-2">Judul</th>
                  <th className="hidden pr-2 md:table-cell">Sumber</th>
                  <th className="hidden pr-2 sm:table-cell">Kata</th>
                  <th className="pr-2">Suasana</th>
                  <th className="hidden md:table-cell">Tautan</th>
                </tr>
              </thead>
              <tbody>
                {table.data?.items.map((item) => (
                  <tr key={item.id} className="cursor-pointer border-t border-line" onClick={() => setOpenId(item.id)}>
                    <td className="whitespace-nowrap py-1.5 pr-2">{formatDay(item.published_at)}</td>
                    <td className="max-w-[16rem] truncate pr-2"><Highlight text={item.title} terms={selected} /></td>
                    <td className="hidden truncate pr-2 md:table-cell">{item.source_name}</td>
                    <td className="hidden truncate pr-2 sm:table-cell">{detected(item, selected).join(', ') || '—'}</td>
                    <td className="pr-2"><SentimentBadge sentiment={item.sentiment} /></td>
                    <td className="hidden md:table-cell" onClick={(event) => event.stopPropagation()}><SourceLink url={item.url} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-1 flex items-center gap-2 text-xs">
              <button className="h-8 rounded-md border border-line px-2" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>Sebelumnya</button>
              <span>{page} / {pages}</span>
              <button className="h-8 rounded-md border border-line px-2" disabled={page >= pages} onClick={() => setPage((value) => value + 1)}>Berikutnya</button>
            </div>
        </section>
      )}

      {tab === 'Detail' && data && (
        <div className="grid min-h-0 flex-1 gap-2 overflow-auto lg:grid-cols-2">
          <section className="border border-line bg-card p-3">
            <h2 className="text-sm font-medium">Suasana berita</h2>
            <Donut
              positif={data.kpis.sentiment_pct.positif}
              netral={data.kpis.sentiment_pct.netral}
              negatif={data.kpis.sentiment_pct.negatif}
              onPick={(name) => { setSentiment(name.toLowerCase()); setTab('Berita') }}
            />
            <ul className="space-y-1 text-sm">
              {data.alerts.map((item) => <li key={item.title}>{plainAlert(item.title)}</li>)}
            </ul>
          </section>
          <section className="border border-line bg-card p-3">
            <h2 className="mb-2 text-sm font-medium">Dari mana beritanya</h2>
            <ul className="space-y-2">
              {data.sources.map((item) => {
                const max = Math.max(1, ...data.sources.map((row) => row.count))
                return (
                  <li key={item.name} className="grid grid-cols-[9rem_1fr_2.5rem] items-center gap-2 text-sm">
                    <span>{item.name}</span>
                    <span className="h-2 bg-line"><span className="block h-2 bg-navy-900" style={{ width: `${(item.count / max) * 100}%` }} /></span>
                    <span className="text-right tabular-nums">{formatNumber(item.count)}</span>
                  </li>
                )
              })}
              {data.sources.length === 0 && <Empty label="Belum ada sumber pada rentang ini." />}
            </ul>
            <h2 className="mb-1 mt-4 text-sm font-medium">Kata yang sering muncul bersama</h2>
            <div className="flex flex-wrap gap-x-3 gap-y-1">
              {data.cowords.slice(0, 12).map((word) => (
                <button key={word.text} className="text-sm text-navy-900 underline" onClick={() => { setQ(word.text); setTab('Berita') }}>{word.text}</button>
              ))}
            </div>
            <p className="mt-4 text-sm">{data.fx.note}</p>
          </section>
        </div>
      )}

      {!data && !catalogQuery.error && <p className="text-sm text-muted">Memuat berita…</p>}
      {openId !== null && <MentionDrawer id={openId} onClose={() => setOpenId(null)} onSaved={() => table.reload()} />}
    </div>
  )
}

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="border border-line bg-card px-3 py-2">
      <p className="text-xs text-muted">{label}</p>
      <p className="truncate text-xl font-medium tabular-nums">{value}</p>
      {note && <p className="truncate text-xs text-muted">{note}</p>}
    </div>
  )
}

function plainAlert(title: string) {
  return title
    .replace('mention', 'berita')
    .replace('rata-rata harian', 'rata-rata per hari')
}

function detected(item: MentionCard, terms: string[]) {
  const known = new Set((item.keyword_matches || []).map((value) => value.toLowerCase()))
  const title = item.title.toLowerCase()
  return terms.filter((itemTerm) => known.has(itemTerm.toLowerCase()) || title.includes(itemTerm.toLowerCase()))
}

function Highlight({ text, terms }: { text: string; terms: string[] }) {
  const usable = terms.filter(Boolean).slice(0, 12)
  if (!usable.length) return <>{text}</>
  const pattern = new RegExp(usable.map((item) => item.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'ig')
  const parts = text.split(pattern)
  const hits = new Set(usable.map((item) => item.toLowerCase()))
  return (
    <>
      {parts.map((part, index) => (
        hits.has(part.toLowerCase())
          ? <mark key={index} className="bg-gold-100 px-0.5 text-ink">{part}</mark>
          : <span key={index}>{part}</span>
      ))}
    </>
  )
}
