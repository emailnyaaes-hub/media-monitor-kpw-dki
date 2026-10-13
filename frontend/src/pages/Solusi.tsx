import { useState } from 'react'
import { useApi } from '../api'
import EvidenceList from '../components/EvidenceList'
import { Card, Empty, ErrorNote, Loading, PageHeader } from '../components/Ui'
import { useFilters } from '../filters'
import { levelClass, type Evidence } from '../voice'

interface Row {
  id: string
  keluhan: string
  kebutuhan: string
  tindakan: string
  jenis: string
  unit: string
  luar_kewenangan: boolean
  urgensi: string
  keyakinan: string
  jumlah: number
  insufficient: boolean
  bukti: Evidence[]
}

export default function SolusiPage() {
  const filters = useFilters()
  const data = useApi<{ items: Row[]; disclaimer: string }>(`/api/solusi?${filters.query}`)
  const [open, setOpen] = useState<string | null>(null)

  return (
    <div>
      <PageHeader
        title="Keluhan ke Solusi"
        description="Keluhan dan kebutuhan yang terbaca, dipasangkan dengan opsi tindakan dan unit yang perlu dilibatkan. Semua opsi wajib ditinjau manusia."
      />
      {data.loading && <Loading />}
      {data.error && <ErrorNote message={data.error} />}
      {data.data && data.data.items.length === 0 && <Card><Empty label="Belum ada keluhan, kebutuhan, atau hoaks yang terbaca pada rentang ini." /></Card>}
      {data.data && data.data.items.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-line bg-card">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs text-muted">
              <tr>
                <th className="p-3">Keluhan atau kebutuhan</th>
                <th className="p-3">Opsi tindakan</th>
                <th className="p-3">Unit</th>
                <th className="p-3">Urgensi</th>
                <th className="p-3">Keyakinan</th>
                <th className="p-3">Bukti</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.data.items.map((item) => (
                <tr key={item.id} className="align-top">
                  <td className="p-3">
                    <p className="font-medium">{item.keluhan || item.kebutuhan}</p>
                    {item.keluhan && item.kebutuhan && <p className="text-xs text-muted">Kebutuhan: {item.kebutuhan}</p>}
                    <p className="text-xs text-muted tabular-nums">{item.jumlah} konten</p>
                  </td>
                  <td className="max-w-md p-3">
                    <p className={item.insufficient ? 'text-amber-800 dark:text-amber-200' : ''}>{item.tindakan}</p>
                    <p className="mt-1 text-xs text-muted">Jenis: {item.jenis}</p>
                  </td>
                  <td className="p-3">
                    {item.unit}
                    {item.luar_kewenangan && <span className="mt-1 block text-xs text-amber-800 dark:text-amber-200">Perlu koordinasi pihak lain</span>}
                  </td>
                  <td className="p-3"><span className={`rounded px-2 py-0.5 text-xs ${levelClass(item.urgensi)}`}>{item.urgensi}</span></td>
                  <td className="p-3">{item.keyakinan}</td>
                  <td className="p-3">
                    <button className="text-sm underline" onClick={() => setOpen(open === item.id ? null : item.id)}>
                      {open === item.id ? 'Tutup' : `${item.bukti.length} tautan`}
                    </button>
                    {open === item.id && <div className="mt-2 min-w-64"><EvidenceList items={item.bukti} /></div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data.data && <p className="mt-3 text-xs text-muted">Opsi tindakan tidak merekomendasikan perubahan kebijakan moneter. Tidak ada pesan yang dikirim otomatis. {data.data.disclaimer}</p>}
    </div>
  )
}
