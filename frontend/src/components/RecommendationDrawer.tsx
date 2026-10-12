import { useEffect, useState } from 'react'
import { api } from '../api'
import { AdviceItem, priorityOf } from './AdviceCard'
import { SourceLink } from './Ui'
import { useAuth } from '../auth'

export default function RecommendationDrawer({
  item,
  disclaimer,
  onClose,
  onChanged,
}: {
  item: AdviceItem
  disclaimer: string
  onClose: () => void
  onChanged?: () => void
}) {
  const { user } = useAuth()
  const canDecide = user?.role === 'admin' || user?.role === 'analis' || user?.role === 'pimpinan'
  const [draft, setDraft] = useState(item.draft_points)
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState('')
  const priority = priorityOf(item.urgency)

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  async function send(action: string) {
    setError('')
    try {
      await api(`/api/advices/${item.id}/actions`, {
        method: 'POST',
        body: JSON.stringify({ action, draft_points: draft }),
      })
      setEditing(false)
      onChanged?.()
      if (action !== 'edit') onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Gagal menyimpan keputusan')
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/40" onClick={onClose}>
      <aside className="h-full w-full max-w-md overflow-auto border-l border-line bg-card p-4 duration-200" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-label="Rekomendasi tindak lanjut">
        <div className="flex items-start justify-between gap-3">
          <p className="text-sm text-muted">Rekomendasi tindak lanjut · Disusun otomatis</p>
          <button className="h-9 shrink-0 rounded-md border border-line px-3 text-sm" onClick={onClose}>Tutup</button>
        </div>
        <h2 className="mt-2 text-base font-medium">{item.title}</h2>
        <p className="mt-2 flex flex-wrap gap-2 text-sm">
          <span className={`rounded-md border px-2 py-0.5 ${priority.className}`}>{priority.label}</span>
          <span>Unit: {item.unit || 'belum ditetapkan'}</span>
          <span>Keyakinan {item.confidence}</span>
        </p>
        {item.insufficient && <p className="mt-3 text-sm font-medium">Data belum cukup, perlu verifikasi. Tidak ada aksi yang dipaksakan.</p>}
        <p className="mt-3 text-sm"><span className="font-medium">Yang terjadi. </span>{item.situation}</p>
        <p className="mt-2 text-sm"><span className="font-medium">Alasan dari data. </span>{item.reason}</p>
        <p className="mt-2 text-sm"><span className="font-medium">Saran. </span>{item.recommendation}</p>
        <p className="mt-2 text-sm"><span className="font-medium">Indikator keberhasilan. </span>{item.impact_follow}</p>
        <p className="mt-2 text-sm"><span className="font-medium">Jika diabaikan. </span>{item.impact_ignore}</p>
        {item.inferences.length > 0 && (
          <p className="mt-2 text-sm text-muted">Asumsi: {item.inferences[0]}</p>
        )}
        <div className="mt-3">
          <p className="text-sm font-medium">Draf pesan, siap diedit</p>
          {editing ? (
            <textarea className="mt-1 min-h-28 w-full border border-line p-2 text-sm" value={draft} onChange={(event) => setDraft(event.target.value)} />
          ) : (
            <p className="mt-1 whitespace-pre-wrap text-sm">{draft || 'Belum ada draf. Data belum cukup untuk menyusun pesan.'}</p>
          )}
        </div>
        <div className="mt-3">
          <p className="text-sm font-medium">Dasar data ({item.source_count} sumber, {item.source_diversity} media atau akun)</p>
          <ul className="mt-1 space-y-2">
            {item.evidence.slice(0, 5).map((row) => (
              <li key={row.url} className="text-sm">
                {row.source_name}: {row.title}
                <SourceLink url={row.url} />
              </li>
            ))}
          </ul>
        </div>
        <p className="mt-3 text-xs text-muted">{disclaimer}</p>
        {canDecide && (
          <div className="mt-3 flex flex-wrap gap-2">
            <button className="h-10 rounded-md bg-navy-900 px-3 text-sm text-white" onClick={() => send('setujui')}>Setujui</button>
            <button className="h-10 rounded-md border border-line px-3 text-sm" onClick={() => (editing ? send('edit') : setEditing(true))}>{editing ? 'Simpan suntingan' : 'Edit'}</button>
            <button className="h-10 rounded-md border border-line px-3 text-sm" onClick={() => send('abaikan')}>Abaikan</button>
          </div>
        )}
        {error && <p className="mt-2 text-sm text-red-800">{error}</p>}
      </aside>
    </div>
  )
}
