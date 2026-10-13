import { formatWhen } from '../format'
import type { Evidence } from '../voice'

export default function EvidenceList({ items, limit = 5 }: { items: Evidence[]; limit?: number }) {
  if (!items.length) return <p className="text-sm text-muted">Belum ada tautan bukti. Data belum cukup, perlu verifikasi.</p>
  return (
    <ul className="space-y-2">
      {items.slice(0, limit).map((item, index) => (
        <li key={`${item.url}-${index}`} className="text-sm">
          <span className="block text-xs text-muted">
            {item.source}
            {item.published_at ? ` · ${formatWhen(item.published_at)} WIB` : ''}
          </span>
          <a href={item.url} target="_blank" rel="noreferrer" className="text-navy-700 underline dark:text-gold-300">
            {item.title}
          </a>
          <span className="ml-1 text-xs text-muted">· Buka sumber asli</span>
        </li>
      ))}
    </ul>
  )
}
