import { useNavigate } from 'react-router-dom'
import { useApi } from '../api'
import { MatrixChart } from '../components/Charts'
import { Card, ErrorNote, Loading, PageHeader, SourceLink, StanceBadge } from '../components/Ui'
import { useFilters } from '../filters'
import { downloadFile } from '../api'
import type { IssueCard } from '../types'

interface Quote {
  title: string
  url: string
}

interface PolicyItem {
  policy: string
  mentions: number
  positif: number
  netral: number
  negatif: number
  aspirations: Quote[]
  criticisms: Quote[]
  relevance_avg: number
}

export default function RadarPage() {
  const filters = useFilters()
  const navigate = useNavigate()
  const radar = useApi<{ items: IssueCard[] }>(`/api/radar?${filters.query}`)
  const feedback = useApi<{ items: PolicyItem[] }>(`/api/policy-feedback?${filters.query}`)

  return (
    <div>
      <PageHeader
        title="Radar dampak kebijakan"
        description="Membantu tim melihat isu mana yang perlu respons lebih dulu. Skor adalah alat baca, bukan keputusan kebijakan."
      />
      {radar.loading && <Loading />}
      {radar.error && <ErrorNote message={radar.error} />}
      {radar.data && (
        <Card>
          <h2 className="font-medium">Matriks dampak dan kecepatan</h2>
          <p className="mb-2 text-xs text-muted">
            Kanan atas: prioritas utama. Kiri atas: rencanakan. Kanan bawah: pantau ketat. Kiri bawah: pantau rutin.
            Warna membedakan upside dan downside.
          </p>
          <MatrixChart items={radar.data.items} />
        </Card>
      )}
      <Card className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="py-2">Isu</th>
              <th>Stance</th>
              <th>Risiko</th>
              <th>Relevansi</th>
              <th>Kuadran</th>
            </tr>
          </thead>
          <tbody>
            {radar.data?.items.map((item) => (
              <tr key={item.id} className="cursor-pointer border-t border-line" onClick={() => navigate(`/isu/${item.id}`)}>
                <td className="py-3 pr-3 font-medium">{item.title}</td>
                <td><StanceBadge stance={item.stance} /></td>
                <td className="tabular-nums">{item.risk_score}</td>
                <td className="tabular-nums">{item.policy_relevance}</td>
                <td>{item.quadrant}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <div className="mt-5 flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Umpan balik kebijakan</h2>
        <button
          className="h-9 rounded-lg border border-line px-3 text-sm"
          onClick={() => downloadFile(`/api/export/laporan.xlsx?${filters.query}`, 'umpan-kebijakan.xlsx')}
        >
          Ekspor Excel
        </button>
      </div>
      <p className="mb-3 text-sm text-muted">Aspirasi dan kritik publik per kebijakan, untuk bahan rapat. Kutipan mengikuti filter yang sedang aktif.</p>
      {feedback.data?.items.map((item) => (
        <Card key={item.policy} className="mb-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="font-medium">{item.policy}</h3>
            <p className="text-xs text-muted">{item.mentions} mention · positif {item.positif}% · negatif {item.negatif}%</p>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <div>
              <p className="text-xs font-semibold uppercase text-emerald-700">Aspirasi</p>
              <ul className="mt-1 space-y-2 text-sm">
                {item.aspirations.map((line) => (
                  <li key={line.url}>
                    <span className="block">{line.title}</span>
                    <SourceLink url={line.url} />
                  </li>
                ))}
              </ul>
              {item.aspirations.length === 0 && <p className="text-sm text-muted">Belum ada cuplikan upside.</p>}
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-red-700">Kritik</p>
              <ul className="mt-1 space-y-2 text-sm">
                {item.criticisms.map((line) => (
                  <li key={line.url}>
                    <span className="block">{line.title}</span>
                    <SourceLink url={line.url} />
                  </li>
                ))}
              </ul>
              {item.criticisms.length === 0 && <p className="text-sm text-muted">Belum ada cuplikan downside.</p>}
            </div>
          </div>
        </Card>
      ))}
    </div>
  )
}
