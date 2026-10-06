import { useState } from 'react'
import { api, useApi } from '../api'
import { useAuth } from '../auth'
import { Card, ErrorNote, Loading, PageHeader, inputClass } from '../components/Ui'

interface Keyword {
  id: number
  term: string
  category: string
  mode: string
  is_active: boolean
}

interface QueryRow {
  id: number
  name: string
  expression: string
  is_active: boolean
}

interface BlockRow {
  id: number
  kind: string
  value: string
  note: string
  is_active: boolean
}

const KIND_LABEL: Record<string, string> = {
  domain: 'Domain',
  account: 'Akun',
  channel: 'Kanal',
}

export default function KeywordsPage() {
  const { user } = useAuth()
  const admin = user?.role === 'admin'
  const data = useApi<{ items: Keyword[]; queries: QueryRow[] }>('/api/keywords')
  const blocks = useApi<{ items: BlockRow[] }>('/api/blocklist')
  const [form, setForm] = useState({ term: '', category: 'Institusi', mode: 'inklusi' })
  const [queryForm, setQueryForm] = useState({ name: '', expression: '"Bank Indonesia" AND NOT lowongan' })
  const [blockForm, setBlockForm] = useState({ kind: 'domain', value: '', note: '' })
  const [sample, setSample] = useState('Bank Indonesia menahan BI-Rate. Ini bukan lowongan.')
  const [testResult, setTestResult] = useState('')
  const [error, setError] = useState('')

  async function addKeyword(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    try {
      await api('/api/keywords', { method: 'POST', body: JSON.stringify({ ...form, is_active: true }) })
      setForm({ ...form, term: '' })
      data.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Gagal menambah')
    }
  }

  async function toggle(row: Keyword) {
    await api(`/api/keywords/${row.id}`, { method: 'PATCH', body: JSON.stringify({ ...row, is_active: !row.is_active }) })
    data.reload()
  }

  async function remove(id: number) {
    await api(`/api/keywords/${id}`, { method: 'DELETE' })
    data.reload()
  }

  async function addQuery(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    try {
      await api('/api/keyword-queries', { method: 'POST', body: JSON.stringify({ ...queryForm, is_active: true }) })
      data.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ekspresi ditolak')
    }
  }

  async function testExpression() {
    setError('')
    try {
      const result = await api<{ matched: boolean }>('/api/keyword-queries/test', {
        method: 'POST',
        body: JSON.stringify({ expression: queryForm.expression, text: sample }),
      })
      setTestResult(result.matched ? 'Teks lolos ekspresi.' : 'Teks tidak lolos ekspresi.')
    } catch (err) {
      setTestResult('')
      setError(err instanceof Error ? err.message : 'Ekspresi tidak valid')
    }
  }

  async function retag() {
    const result = await api<{ updated: number }>('/api/jobs/retag', { method: 'POST' })
    setTestResult(`${result.updated} mention ditandai ulang dengan kamus terbaru.`)
  }

  async function addBlock(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    try {
      await api('/api/blocklist', { method: 'POST', body: JSON.stringify({ ...blockForm, is_active: true }) })
      setBlockForm({ kind: blockForm.kind, value: '', note: '' })
      blocks.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Gagal menambah blokir')
    }
  }

  async function toggleBlock(row: BlockRow) {
    await api(`/api/blocklist/${row.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ ...row, is_active: !row.is_active }),
    })
    blocks.reload()
  }

  async function removeBlock(id: number) {
    await api(`/api/blocklist/${id}`, { method: 'DELETE' })
    blocks.reload()
  }

  const groups = new Map<string, Keyword[]>()
  data.data?.items.forEach((item) => {
    const list = groups.get(item.category) || []
    list.push(item)
    groups.set(item.category, list)
  })

  return (
    <div>
      <PageHeader
        title="Kata kunci"
        description="Inklusi, eksklusi, ekspresi boolean, dan daftar blokir kanal milik Bank Indonesia."
      />
      {data.loading && <Loading />}
      {data.error && <ErrorNote message={data.error} />}
      {error && <div className="mb-3"><ErrorNote message={error} /></div>}
      {testResult && <p className="mb-3 text-sm">{testResult}</p>}
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-3 lg:col-span-2">
          {[...groups.entries()].map(([category, items]) => (
            <Card key={category}>
              <h2 className="font-medium">{category}</h2>
              <div className="mt-2 flex flex-wrap gap-2">
                {items.map((item) => (
                  <span key={item.id} className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs ${item.is_active ? 'border-line' : 'border-dashed opacity-50'}`}>
                    {item.mode === 'eksklusi' ? 'NOT ' : ''}{item.term}
                    {admin && <button onClick={() => toggle(item)} aria-label={`Ubah status ${item.term}`}>{item.is_active ? 'aktif' : 'mati'}</button>}
                    {admin && <button onClick={() => remove(item.id)} aria-label={`Hapus ${item.term}`}>hapus</button>}
                  </span>
                ))}
              </div>
            </Card>
          ))}
        </div>
        <div className="space-y-4">
          {admin && (
            <Card>
              <h2 className="font-medium">Tambah kata</h2>
              <form className="mt-3 grid gap-2" onSubmit={addKeyword}>
                <input className={inputClass} placeholder="Istilah" value={form.term} onChange={(event) => setForm({ ...form, term: event.target.value })} required />
                <input className={inputClass} placeholder="Kategori" value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} />
                <select className={inputClass} value={form.mode} onChange={(event) => setForm({ ...form, mode: event.target.value })}>
                  <option value="inklusi">Inklusi</option>
                  <option value="eksklusi">Eksklusi</option>
                </select>
                <button className="h-10 rounded-lg bg-navy-900 text-sm text-white">Simpan</button>
              </form>
              <button className="mt-3 text-sm underline" onClick={retag}>Terapkan ulang ke data yang sudah tersimpan</button>
            </Card>
          )}
          <Card>
            <h2 className="font-medium">Ekspresi boolean</h2>
            <p className="mt-1 text-xs leading-relaxed text-muted">
              Gunakan AND, OR, NOT, dan kurung. Frasa panjang diberi tanda kutip. Contoh: ("Bank Indonesia" OR QRIS) AND NOT lowongan.
              Kata dalam satu ekspresi digabung sesuai operator. Beberapa ekspresi tersimpan diuji sebagai ATAU: teks cukup lolos satu ekspresi.
            </p>
            <ul className="mt-3 space-y-2 text-xs">
              {data.data?.queries.map((item) => (
                <li key={item.id}>
                  <span className="font-medium">{item.name}</span>
                  <span className="mt-1 block text-muted">{item.expression}</span>
                </li>
              ))}
            </ul>
            <label className="mt-3 grid gap-1 text-xs text-muted">
              Uji ekspresi
              <textarea className="min-h-16 rounded-lg border border-line bg-card p-2 text-sm text-ink" value={queryForm.expression} onChange={(event) => setQueryForm({ ...queryForm, expression: event.target.value })} />
            </label>
            <textarea className="mt-2 min-h-16 w-full rounded-lg border border-line bg-card p-2 text-sm" value={sample} onChange={(event) => setSample(event.target.value)} />
            <button className="mt-2 h-9 rounded-lg border border-line px-3 text-sm" onClick={testExpression}>Uji</button>
            {admin && (
              <form className="mt-3 grid gap-2" onSubmit={addQuery}>
                <input className={inputClass} placeholder="Nama paket" value={queryForm.name} onChange={(event) => setQueryForm({ ...queryForm, name: event.target.value })} />
                <button className="h-10 rounded-lg bg-navy-900 text-sm text-white">Simpan ekspresi</button>
              </form>
            )}
          </Card>
        </div>
      </div>
      <Card className="mt-4">
        <h2 className="font-medium">Daftar blokir kanal Bank Indonesia</h2>
        <p className="mt-1 text-xs leading-relaxed text-muted">
          Domain, akun, dan nama kanal milik BI tidak diambil dan tidak dihitung. Akhirkan akun dengan * bila ingin mencakup variasi, misalnya bank_indonesia*.
          Akun pejabat yang dikelola sebagai kanal resmi bisa ditambahkan di sini. Konten media luar yang hanya mengutip BI tetap tampil dengan label Mengutip BI.
        </p>
        {blocks.error && <div className="mt-2"><ErrorNote message={blocks.error} /></div>}
        <ul className="mt-3 divide-y divide-line text-sm">
          {blocks.data?.items.map((item) => (
            <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span>
                <span className="text-xs text-muted">{KIND_LABEL[item.kind] || item.kind}</span>
                <span className={`ml-2 ${item.is_active ? '' : 'line-through opacity-50'}`}>{item.value}</span>
                {item.note && <span className="ml-2 text-xs text-muted">{item.note}</span>}
              </span>
              {admin && (
                <span className="flex gap-2 text-xs">
                  <button onClick={() => toggleBlock(item)}>{item.is_active ? 'nonaktifkan' : 'aktifkan'}</button>
                  <button onClick={() => removeBlock(item.id)}>hapus</button>
                </span>
              )}
            </li>
          ))}
        </ul>
        {admin && (
          <form className="mt-3 grid gap-2 md:grid-cols-4" onSubmit={addBlock}>
            <select className={inputClass} value={blockForm.kind} onChange={(event) => setBlockForm({ ...blockForm, kind: event.target.value })}>
              <option value="domain">Domain</option>
              <option value="account">Akun</option>
              <option value="channel">Kanal</option>
            </select>
            <input className={inputClass} placeholder="bi.go.id atau @akun" value={blockForm.value} onChange={(event) => setBlockForm({ ...blockForm, value: event.target.value })} required />
            <input className={inputClass} placeholder="Catatan" value={blockForm.note} onChange={(event) => setBlockForm({ ...blockForm, note: event.target.value })} />
            <button className="h-10 rounded-lg bg-navy-900 text-sm text-white">Tambah blokir</button>
          </form>
        )}
      </Card>
    </div>
  )
}
