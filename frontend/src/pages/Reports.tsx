import { downloadFile, useApi } from '../api'
import { Card, ErrorNote, Loading, PageHeader, QuoteBadge, SourceLink } from '../components/Ui'
import { useFilters } from '../filters'
import type { IssueCard, Overview } from '../types'

interface Report {
  paragraphs: string[]
  disclaimer: string
  issues: IssueCard[]
  sources?: { id: number; title: string; source_name: string; url: string; published_at: string; quotes_bi?: boolean }[]
  overview: Overview
}

export default function ReportsPage() {
  const filters = useFilters()
  const report = useApi<Report>(`/api/reports/summary?${filters.query}`)

  function openPrint() {
    const token = localStorage.getItem('bi-token')
    fetch(`/api/export/laporan.html?${filters.query}`, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => response.text())
      .then((html) => {
        const frame = window.open('', '_blank')
        if (!frame) return
        frame.document.write(html)
        frame.document.close()
      })
  }

  return (
    <div>
      <PageHeader title="Laporan" description="Ringkasan harian sampai bulanan mengikuti rentang tanggal di atas. PDF lewat cetak peramban, angka lengkap lewat Excel."       />
      <div className="mb-4 flex flex-wrap gap-2">
        <button className="h-10 rounded-lg bg-navy-900 px-4 text-sm text-white" onClick={openPrint}>Pratinjau cetak / PDF</button>
        <button className="h-10 rounded-lg border border-line px-4 text-sm" onClick={() => downloadFile(`/api/export/laporan.xlsx?${filters.query}`, 'laporan-media-monitor.xlsx')}>Unduh Excel</button>
        <button className="h-10 rounded-lg border border-line px-4 text-sm" onClick={() => downloadFile(`/api/export/laporan.pptx?${filters.query}`, 'laporan-media-monitor.pptx')}>Unduh PPTX</button>
        <button className="h-10 rounded-lg border border-line px-4 text-sm" onClick={() => downloadFile(`/api/export/mentions.csv?${filters.query}`, 'mention.csv')}>Unduh CSV mention</button>
      </div>
      {report.loading && <Loading />}
      {report.error && <ErrorNote message={report.error} />}
      {report.data && (
        <Card>
          <h2 className="font-medium">Ringkasan untuk pimpinan</h2>
          {report.data.paragraphs.map((line) => <p key={line} className="mt-3 text-sm leading-relaxed">{line}</p>)}
          <ol className="mt-4 list-decimal space-y-2 pl-5 text-sm">
            {report.data.issues.map((issue) => (
              <li key={issue.id}>{issue.title} — {issue.stance}, risiko {issue.risk_score}, {issue.quadrant}.</li>
            ))}
          </ol>
          <h3 className="mt-4 font-medium">Sumber</h3>
          <ul className="mt-2 space-y-2 text-sm">
            {(report.data.sources || []).map((item) => (
              <li key={item.id}>
                <span className="flex items-center gap-2">{item.source_name}: {item.title} <QuoteBadge show={item.quotes_bi} /></span>
                <SourceLink url={item.url} />
              </li>
            ))}
          </ul>
          <p className="mt-4 rounded-lg bg-gold-100 p-3 text-xs leading-relaxed text-navy-900">{report.data.disclaimer}</p>
        </Card>
      )}
    </div>
  )
}
