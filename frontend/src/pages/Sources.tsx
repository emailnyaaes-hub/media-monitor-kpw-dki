import { useApi } from '../api'
import { Card, ErrorNote, Loading, PageHeader, VerifiedNote } from '../components/Ui'
import { useFilters } from '../filters'
import { formatReach, PLATFORM_LABEL } from '../format'

interface MediaRow {
  name: string
  tier: number
  mentions: number
  reach: number
  positif: number
  negatif: number
  tilt: string
}

interface Influencer {
  handle: string
  name: string
  platform: string
  mentions: number
  reach: number
  negatif: number
  positif: number
  needs_verification: boolean
  verification_note: string
}

export default function SourcesPage() {
  const filters = useFilters()
  const data = useApi<{ media: MediaRow[]; influencers: Influencer[] }>(`/api/sources?${filters.query}`)

  return (
    <div>
      <PageHeader
        title="Sumber dan akun berpengaruh"
        description="Peringkat media dan akun publik yang menyebut BI. Tanda verifikasi adalah indikasi awal, bukan vonis."
      />
      {data.loading && <Loading />}
      {data.error && <ErrorNote message={data.error} />}
      {data.data && (
        <div className="grid gap-4 xl:grid-cols-2">
          <Card className="overflow-x-auto">
            <h2 className="mb-3 font-medium">Media</h2>
            <table className="w-full min-w-[520px] text-left text-sm">
              <thead className="text-xs uppercase text-muted">
                <tr><th className="py-2">Media</th><th>Tier</th><th>Mention</th><th>Jangkauan</th><th>Kecenderungan</th></tr>
              </thead>
              <tbody>
                {data.data.media.map((row) => (
                  <tr key={row.name} className="border-t border-line">
                    <td className="py-2 font-medium">{row.name}</td>
                    <td>{row.tier}</td>
                    <td>{row.mentions}</td>
                    <td>{formatReach(row.reach)}</td>
                    <td>{row.tilt}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <Card className="overflow-x-auto">
            <h2 className="mb-3 font-medium">Akun</h2>
            <table className="w-full min-w-[520px] text-left text-sm">
              <thead className="text-xs uppercase text-muted">
                <tr><th className="py-2">Akun</th><th>Platform</th><th>Mention</th><th>Jangkauan</th><th>Catatan</th></tr>
              </thead>
              <tbody>
                {data.data.influencers.map((row) => (
                  <tr key={row.handle} className="border-t border-line align-top">
                    <td className="py-2">
                      <span className="block font-medium">{row.name}</span>
                      <span className="text-xs text-muted">{row.handle}</span>
                    </td>
                    <td>{PLATFORM_LABEL[row.platform] || row.platform}</td>
                    <td>{row.mentions}</td>
                    <td>{formatReach(row.reach)}</td>
                    <td className="max-w-xs text-xs text-muted">
                      {row.needs_verification ? <VerifiedNote /> : 'Tidak ada indikasi khusus'}
                      {row.verification_note && <span className="mt-1 block">{row.verification_note}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      )}
    </div>
  )
}
