import { useEffect, useState } from 'react'
import { api, downloadPost } from '../api'
import { useFilters } from '../filters'
import { ErrorNote, inputClass } from './Ui'

interface Slide {
  id: string
  number: number
  section: string
  action_title: string
  visual: string
  message: string
  so_what: string
  data_note: string
}

interface Preview {
  filename: string
  source_line: string
  slides: Slide[]
}

interface Edit {
  action_title: string
  so_what: string
}

export default function DeckDialog({ onClose }: { onClose: () => void }) {
  const filters = useFilters()
  const [version, setVersion] = useState<'lengkap' | 'ringkas'>('lengkap')
  const [appendix, setAppendix] = useState(true)
  const [lang, setLang] = useState<'id' | 'en'>('id')
  const [preview, setPreview] = useState<Preview | null>(null)
  const [edits, setEdits] = useState<Record<string, Edit>>({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancel = false
    const params = new URLSearchParams(filters.query)
    params.set('version', version)
    params.set('appendix', appendix ? 'true' : 'false')
    params.set('lang', lang)
    setPreview(null)
    setError('')
    api<Preview>(`/api/export/deck/preview?${params.toString()}`)
      .then((data) => {
        if (cancel) return
        setPreview(data)
        setEdits(Object.fromEntries(data.slides.map((slide) => [slide.id, { action_title: slide.action_title, so_what: slide.so_what }])))
      })
      .catch((err: Error) => {
        if (!cancel) setError(err.message)
      })
    return () => {
      cancel = true
    }
  }, [filters.query, version, appendix, lang])

  function patch(id: string, field: keyof Edit, value: string) {
    setEdits((current) => ({ ...current, [id]: { ...current[id], [field]: value } }))
  }

  async function download() {
    if (!preview) return
    setBusy(true)
    setError('')
    try {
      await downloadPost('/api/export/deck.pptx', preview.filename, {
        date_from: filters.dateFrom,
        date_to: filters.dateTo,
        platform: filters.platform === 'semua' ? null : filters.platform,
        category: filters.category === 'semua' ? null : filters.category,
        version,
        appendix,
        lang,
        edits: preview.slides.map((slide) => ({
          id: slide.id,
          action_title: edits[slide.id]?.action_title ?? slide.action_title,
          so_what: edits[slide.id]?.so_what ?? slide.so_what,
        })),
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unduhan gagal')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-navy-950/40 p-4" role="dialog" aria-modal="true" aria-labelledby="deck-title">
      <div className="mx-auto mt-6 w-full max-w-3xl rounded-md border border-line bg-card p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="deck-title" className="font-serif text-xl font-medium">Pratinjau briefing</h2>
            <p className="mt-1 text-sm text-muted">Judul dan kotak So what bisa disunting. Angka tetap dari data filter yang aktif.</p>
          </div>
          <button className="h-10 rounded-md border border-line px-3 text-sm" onClick={onClose}>Tutup</button>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <select className={inputClass} value={version} onChange={(event) => setVersion(event.target.value as 'lengkap' | 'ringkas')}>
            <option value="lengkap">Lengkap</option>
            <option value="ringkas">Ringkas, 5 slide</option>
          </select>
          <select className={inputClass} value={lang} onChange={(event) => setLang(event.target.value as 'id' | 'en')}>
            <option value="id">Indonesia</option>
            <option value="en">English</option>
          </select>
          <label className="flex h-11 items-center gap-2 px-1 text-sm">
            <input type="checkbox" checked={appendix} onChange={(event) => setAppendix(event.target.checked)} />
            Sertakan lampiran
          </label>
        </div>
        {error && <div className="mt-3"><ErrorNote message={error} /></div>}
        {!preview && !error && <p className="mt-4 text-sm text-muted">Menyusun pratinjau…</p>}
        {preview && (
          <>
            <p className="mt-3 text-sm text-muted">{preview.source_line}</p>
            <p className="mt-1 text-sm text-muted">Berkas: {preview.filename}</p>
            <ol className="mt-4 grid gap-4">
              {preview.slides.map((slide) => (
                <li key={slide.id} className="border-t border-line pt-3">
                  <p className="text-sm text-muted">{String(slide.number).padStart(2, '0')} · {slide.section} · {slide.visual}</p>
                  <label className="mt-2 grid gap-1 text-sm">
                    Judul kesimpulan
                    <textarea className="min-h-16 rounded-md border border-line bg-card p-2 text-sm" value={edits[slide.id]?.action_title ?? slide.action_title} onChange={(event) => patch(slide.id, 'action_title', event.target.value)} />
                  </label>
                  <p className="mt-2 text-sm">{slide.message}</p>
                  <label className="mt-2 grid gap-1 text-sm">
                    So what
                    <textarea className="min-h-16 rounded-md border border-line bg-card p-2 text-sm" value={edits[slide.id]?.so_what ?? ''} onChange={(event) => patch(slide.id, 'so_what', event.target.value)} />
                  </label>
                  {slide.data_note && <p className="mt-2 text-sm text-muted">{slide.data_note}</p>}
                </li>
              ))}
            </ol>
            <div className="mt-4 flex justify-end">
              <button className="h-11 rounded-md bg-navy-900 px-3 text-sm text-white disabled:opacity-60" disabled={busy} onClick={download}>
                {busy ? 'Menyusun berkas…' : 'Unduh PPT'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
