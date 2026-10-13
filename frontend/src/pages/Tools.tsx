import { useState } from 'react'
import { useApi } from '../api'
import { Card, ErrorNote, Loading, PageHeader } from '../components/Ui'

interface ToolsMap {
  diadopsi: { teknik: string; penerapan: string; sumber: string; tautan: string }[]
  ditolak: { teknik: string; alasan: string }[]
  matriks: {
    nama: string
    fungsi: string
    data: string
    pemilik: string
    kekuatan: string
    batas: string
    posisi: string
    status: string
    sumber: string
  }[]
  pertanyaan: string[]
  asumsi: string[]
  skoring: string[]
  disclaimer: string
}

const TABS = ['Gap analysis', 'Riset pendekatan', 'Pertanyaan internal', 'Aturan dan asumsi'] as const

function statusClass(status: string) {
  if (status === 'Terverifikasi publik') return 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200'
  if (status === 'Perlu konfirmasi internal') return 'bg-amber-50 text-amber-900 dark:bg-amber-950/50 dark:text-amber-200'
  return 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200'
}

export default function ToolsPage() {
  const data = useApi<ToolsMap>('/api/peta-tools')
  const [tab, setTab] = useState<(typeof TABS)[number]>('Gap analysis')

  return (
    <div>
      <PageHeader
        title="Peta Tools BI"
        description="Posisi dashboard terhadap mekanisme yang sudah ada. Fungsi yang sudah dipenuhi alat lain dirujuk, bukan dibangun ulang."
      />
      <div className="mb-4 flex flex-wrap gap-1 border-b border-line" role="tablist">
        {TABS.map((item) => (
          <button
            key={item}
            role="tab"
            aria-selected={tab === item}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${tab === item ? 'border-navy-900 font-medium dark:border-gold-500' : 'border-transparent text-muted'}`}
            onClick={() => setTab(item)}
          >
            {item}
          </button>
        ))}
      </div>
      {data.loading && <Loading />}
      {data.error && <ErrorNote message={data.error} />}
      {data.data && tab === 'Gap analysis' && (
        <div className="overflow-x-auto rounded-md border border-line bg-card">
          <table className="w-full min-w-[1100px] text-sm">
            <thead className="border-b border-line text-left text-xs text-muted">
              <tr>
                {['Tools/mekanisme', 'Fungsi', 'Data yang dihasilkan', 'Pemilik/unit', 'Kekuatan', 'Keterbatasan', 'Posisi dashboard', 'Status'].map((head) => (
                  <th key={head} className="p-3">{head}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.data.matriks.map((row) => (
                <tr key={row.nama} className="align-top">
                  <td className="p-3 font-medium">
                    {row.nama}
                    {row.sumber && <a className="mt-1 block text-xs font-normal text-navy-700 underline dark:text-gold-300" href={row.sumber} target="_blank" rel="noreferrer">Buka sumber asli</a>}
                  </td>
                  <td className="p-3">{row.fungsi}</td>
                  <td className="p-3">{row.data}</td>
                  <td className="p-3">{row.pemilik}</td>
                  <td className="p-3">{row.kekuatan}</td>
                  <td className="p-3">{row.batas}</td>
                  <td className="p-3">{row.posisi}</td>
                  <td className="p-3"><span className={`rounded px-2 py-0.5 text-xs ${statusClass(row.status)}`}>{row.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data.data && tab === 'Riset pendekatan' && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <h2 className="font-medium">Teknik yang diadopsi</h2>
            <ul className="mt-2 divide-y divide-line">
              {data.data.diadopsi.map((item) => (
                <li key={item.teknik} className="py-3 text-sm">
                  <p className="font-medium">{item.teknik}</p>
                  <p className="mt-1">Penerapan di BI Jakarta: {item.penerapan}</p>
                  <a className="mt-1 block text-xs text-navy-700 underline dark:text-gold-300" href={item.tautan} target="_blank" rel="noreferrer">{item.sumber}</a>
                </li>
              ))}
            </ul>
          </Card>
          <Card>
            <h2 className="font-medium">Teknik yang ditolak</h2>
            <ul className="mt-2 divide-y divide-line">
              {data.data.ditolak.map((item) => (
                <li key={item.teknik} className="py-3 text-sm">
                  <p className="font-medium">{item.teknik}</p>
                  <p className="mt-1 text-muted">{item.alasan}</p>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      )}
      {data.data && tab === 'Pertanyaan internal' && (
        <Card>
          <h2 className="font-medium">Pertanyaan untuk Kehumasan dan unit terkait</h2>
          <p className="text-xs text-muted">Dashboard tidak punya akses ke sistem internal BI. Jawaban di sini yang menentukan apakah sebuah fungsi duplikasi, pelengkap, atau pengganti.</p>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm">
            {data.data.pertanyaan.map((item) => <li key={item}>{item}</li>)}
          </ol>
        </Card>
      )}
      {data.data && tab === 'Aturan dan asumsi' && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <h2 className="font-medium">Aturan skoring</h2>
            <ul className="mt-2 list-disc space-y-2 pl-5 text-sm">{data.data.skoring.map((item) => <li key={item}>{item}</li>)}</ul>
          </Card>
          <Card>
            <h2 className="font-medium">Asumsi dan keterbatasan</h2>
            <ul className="mt-2 list-disc space-y-2 pl-5 text-sm">{data.data.asumsi.map((item) => <li key={item}>{item}</li>)}</ul>
          </Card>
        </div>
      )}
      {data.data && <p className="mt-3 text-xs text-muted">{data.data.disclaimer}</p>}
    </div>
  )
}
