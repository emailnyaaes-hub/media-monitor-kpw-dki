import { useEffect, useState } from 'react'
import { api, downloadFile } from '../api'
import { Card, Empty, ErrorNote, Loading, StanceBadge } from '../components/Ui'
import { useFilters } from '../filters'
import { formatDay, formatSigned } from '../format'

interface LinkItem {
  source_name: string
  title: string
  url: string
  published_at: string
}

interface IssueRow {
  rank: number
  key: string
  title: string
  stance: 'upside' | 'netral' | 'downside'
  mix: { positif: number; netral: number; negatif: number }
  volume: number
  delta_pct: number | null
  province: string
  summary: string
  links: LinkItem[]
}

interface Payload {
  items: IssueRow[]
  method: string
  updated_at?: string
  cached?: boolean
  province_options: string[]
  provinces: string[]
}

const TABS = [
  { id: 'nasional', label: 'Top 10 Isu Nasional' },
  { id: 'dki', label: 'Top 10 Isu KPw DKI Jakarta' },
  { id: 'lainnya', label: 'Top 10 Isu KPw Provinsi Lain' },
] as const

export default function ExecutivePage() {
  const filters = useFilters()
  const [scope, setScope] = useState<(typeof TABS)[number]['id']>('nasional')
  const [province, setProvince] = useState('')
  const [open, setOpen] = useState<string | null>(null)
  const [data, setData] = useState<Payload | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState('')

  const query = `${filters.query}&scope=${scope}${province ? `&province=${encodeURIComponent(province)}` : ''}`

  useEffect(() => {
    let cancel = false
    setLoading(true)
    setError('')
    api<Payload>(`/api/executive?${query}`)
      .then((result) => { if (!cancel) setData(result) })
      .catch((err: unknown) => { if (!cancel) setError(err instanceof Error ? err.message : 'Gagal memuat ringkasan') })
      .finally(() => { if (!cancel) setLoading(false) })
    return () => { cancel = true }
  }, [query])

  async function printReport() {
    const headers = new Headers()
    const token = localStorage.getItem('bi-token')
    if (token) headers.set('Authorization', `Bearer ${token}`)
    const response = await fetch(`/api/executive/laporan.html?${filters.query}`, { headers })
    if (!response.ok) {
      setError('Cetak PDF gagal. Muat ulang halaman lalu coba lagi.')
      return
    }
    const html = await response.text()
    const popup = window.open('', '_blank')
    if (!popup) {
      setError('Izinkan pop-up untuk mencetak PDF.')
      return
    }
    popup.document.write(html)
    popup.document.close()
    popup.focus()
    popup.print()
  }

  async function refresh() {
    setLoading(true)
    setError('')
    try {
      const result = await api<Payload>(`/api/executive/refresh?${query}`, { method: 'POST' })
      setData(result)
      setNotice('Ringkasan diperbarui dari data tersimpan.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Gagal memuat ringkasan')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="mb-3">
        <h2 className="text-base font-medium">Top 10 isu</h2>
        <p className="text-sm text-muted">Sepuluh isu teratas untuk pimpinan. Ringkasan dan tautan hanya berasal dari berita yang sudah tersimpan.</p>
      </div>
      <div className="mb-4 flex flex-wrap gap-2" role="tablist" aria-label="Cakupan isu">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={scope === tab.id}
            className={`h-10 rounded-lg px-3 text-sm ${scope === tab.id ? 'bg-navy-900 text-white' : 'border border-line'}`}
            onClick={() => {
              setScope(tab.id)
              setProvince('')
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {scope === 'lainnya' && (
          <label className="text-sm">
            Provinsi
            <select className="ml-2 h-10 rounded-lg border border-line bg-card px-2" value={province} onChange={(event) => setProvince(event.target.value)} aria-label="Filter provinsi">
              <option value="">Semua provinsi</option>
              {(data?.province_options || []).map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          </label>
        )}
        <button className="h-10 rounded-lg border border-line px-3 text-sm" onClick={() => void refresh()}>Perbarui ringkasan</button>
        <button className="h-10 rounded-lg border border-line px-3 text-sm" onClick={() => downloadFile(`/api/executive/export.xlsx?${filters.query}`, 'executive-summary.xlsx')}>Unduh Excel</button>
        <button className="h-10 rounded-lg border border-line px-3 text-sm" onClick={() => void printReport()}>Cetak PDF</button>
      </div>
      {notice && <p className="mb-3 text-sm text-emerald-800" role="status">{notice}</p>}
      <p className="mb-3 text-sm text-muted">Periode mengikuti filter tanggal di atas. Arahkan kursor ke badge untuk komposisi sentimen.</p>
      {loading && <Loading />}
      {error && <ErrorNote message={`${error} Periksa rentang tanggal atau muat ulang.`} />}
      {!loading && !error && data && data.items.length === 0 && (
        <Empty label="Belum ada isu dengan minimal dua tautan pada cakupan ini. Perlebar tanggal atau tekan Perbarui sekarang di header." />
      )}
      {data && data.items.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="hidden w-full min-w-[720px] text-left text-sm md:table">
            <thead>
              <tr className="border-b border-line text-muted">
                <th className="py-2 pr-3">Peringkat</th>
                <th className="py-2 pr-3">Judul isu</th>
                <th className="py-2 pr-3">Sentimen</th>
                <th className="py-2 pr-3">Volume</th>
                {scope === 'lainnya' && <th className="py-2 pr-3">Provinsi</th>}
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <IssueLine key={item.key} item={item} scope={scope} open={open === item.key} onToggle={() => setOpen(open === item.key ? null : item.key)} />
              ))}
            </tbody>
          </table>
          <div className="grid gap-3 md:hidden">
            {data.items.map((item) => (
              <article key={item.key} className="rounded-md border border-line p-3">
                <p className="text-xs text-muted">Peringkat {item.rank}{item.province ? ` · ${item.province}` : ''}</p>
                <h2 className="mt-1 font-medium">{item.title}</h2>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <StanceBadge stance={item.stance} />
                  <span title={`Positif ${item.mix.positif}% · Netral ${item.mix.netral}% · Negatif ${item.mix.negatif}%`}>{item.volume} mention {item.delta_pct === null ? '' : formatSigned(item.delta_pct)}</span>
                </div>
                <p className="mt-2 text-sm leading-relaxed">{item.summary}</p>
                <LinkList links={item.links} />
              </article>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted">{data.method} {data.updated_at ? `Diperbarui ${data.updated_at}.` : ''}</p>
        </Card>
      )}
    </div>
  )
}

function IssueLine({ item, scope, open, onToggle }: { item: IssueRow; scope: string; open: boolean; onToggle: () => void }) {
  return (
    <>
      <tr className="border-b border-line">
        <td className="py-3 pr-3">{item.rank}</td>
        <td className="py-3 pr-3">
          <button className="text-left font-medium text-navy-900 underline-offset-2 hover:underline dark:text-white" aria-expanded={open} onClick={onToggle}>
            {item.title}
          </button>
        </td>
        <td className="py-3 pr-3">
          <span title={`Positif ${item.mix.positif}% · Netral ${item.mix.netral}% · Negatif ${item.mix.negatif}%`}>
            <StanceBadge stance={item.stance} />
          </span>
        </td>
        <td className="py-3 pr-3">{item.volume} {item.delta_pct === null ? '' : <span className="text-muted">({formatSigned(item.delta_pct)})</span>}</td>
        {scope === 'lainnya' && <td className="py-3 pr-3">{item.province || '—'}</td>}
      </tr>
      {open && (
        <tr className="border-b border-line">
          <td colSpan={scope === 'lainnya' ? 5 : 4} className="bg-slate-50 px-3 py-3 dark:bg-slate-900/40">
            <p className="max-w-3xl text-sm leading-relaxed">{item.summary}</p>
            <LinkList links={item.links} />
          </td>
        </tr>
      )}
    </>
  )
}

function LinkList({ links }: { links: LinkItem[] }) {
  return (
    <ul className="mt-2 space-y-1 text-sm">
      {links.map((link) => (
        <li key={link.url}>
          <a className="text-sky-800 underline dark:text-sky-300" href={link.url} target="_blank" rel="noreferrer">
            {link.source_name}: {link.title}
          </a>
          <span className="text-muted"> · {formatDay(link.published_at)}</span>
        </li>
      ))}
    </ul>
  )
}
