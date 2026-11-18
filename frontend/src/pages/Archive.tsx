import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../api'
import MentionBrief from '../components/MentionBrief'
import MentionDrawer from '../components/MentionDrawer'
import { Card, Empty, ErrorNote, Loading, PageHeader, QuoteBadge, SentimentBadge, SourceLink, StanceBadge } from '../components/Ui'
import { useFilters } from '../filters'
import { formatDay, formatWhen, isoDate, PLATFORM_LABEL, relativeTime } from '../format'
import type { MentionCard } from '../types'

interface ArchiveDaySummary {
  date: string
  total: number
  berita: number
  sosial: number
  negatif: number
  positif: number
  titles: string[]
}

interface ArchiveDaysPayload {
  date_from: string
  date_to: string
  day_count: number
  mention_total: number
  days: ArchiveDaySummary[]
}

interface ArchiveDayPayload {
  date: string
  total: number
  items: MentionCard[]
}

function todayIso() {
  return isoDate(new Date())
}

export default function ArchivePage() {
  const filters = useFilters()
  const navigate = useNavigate()
  const [selected, setSelected] = useState(todayIso())
  const [openId, setOpenId] = useState<number | null>(null)

  const daysQuery = useMemo(() => {
    const params = new URLSearchParams(filters.query)
    return params.toString()
  }, [filters.query])

  const days = useApi<ArchiveDaysPayload>(`/api/archive/days?${daysQuery}`)
  const dayPayload = useApi<ArchiveDayPayload>(selected ? `/api/archive/day?day=${encodeURIComponent(selected)}&${daysQuery}` : null)

  const list = days.data?.days || []
  const active = list.find((item) => item.date === selected) || null

  function pick(day: string) {
    setSelected(day)
  }

  function openInExplorer(day: string) {
    filters.focusDay(day, '/arsip')
    navigate('/explorer')
  }

  return (
    <div className="mx-auto max-w-6xl pb-16 md:pb-0">
      <PageHeader
        title="Arsip Historis"
        description="Baca ulang konten per tanggal. Semua berita dan unggahan yang sudah masuk DANITA tetap tersimpan dan bisa dibuka lagi kapan saja."
      />

      {days.loading && <Loading />}
      {days.error && <ErrorNote message={days.error} />}

      {days.data && (
        <p className="mb-4 text-sm text-muted">
          {days.data.mention_total} konten · {days.data.day_count} hari aktif · rentang {formatDay(days.data.date_from)} – {formatDay(days.data.date_to)}
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-[0.95fr_1.35fr]">
        <Card className="max-h-[70vh] overflow-y-auto">
          <h2 className="font-medium">Kalender arsip</h2>
          <p className="mt-1 text-xs text-muted">Pilih tanggal untuk melihat berita hari itu.</p>
          {list.length === 0 && !days.loading && (
            <Empty label="Belum ada arsip pada rentang ini" hint="Perluas filter tanggal di atas, atau jalankan pembaruan data." />
          )}
          <ul className="mt-3 divide-y divide-line">
            {list.map((item) => {
              const on = item.date === selected
              return (
                <li key={item.date}>
                  <button
                    className={`w-full px-1 py-3 text-left transition ${on ? 'bg-navy-900/5 dark:bg-white/5' : 'hover:bg-black/[0.02] dark:hover:bg-white/[0.03]'}`}
                    onClick={() => pick(item.date)}
                  >
                    <div className="flex items-baseline justify-between gap-3">
                      <span className={`text-sm font-semibold ${on ? 'text-navy-900 dark:text-white' : ''}`}>{formatDay(item.date)}</span>
                      <span className="text-xs text-muted">{item.total} konten</span>
                    </div>
                    <p className="mt-1 text-xs text-muted">
                      Berita {item.berita} · Sosial {item.sosial}
                      {item.negatif > 0 ? ` · Negatif ${item.negatif}` : ''}
                    </p>
                    {item.titles[0] && <p className="mt-1 line-clamp-1 text-sm">{item.titles[0]}</p>}
                  </button>
                </li>
              )
            })}
          </ul>
        </Card>

        <div>
          <Card>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h2 className="font-medium">{selected ? formatDay(selected) : 'Pilih tanggal'}</h2>
                <p className="mt-1 text-xs text-muted">
                  {active
                    ? `${active.total} konten · berita ${active.berita} · sosial ${active.sosial}`
                    : dayPayload.data
                      ? `${dayPayload.data.total} konten`
                      : 'Konten hari ini akan tampil di sini.'}
                </p>
              </div>
              <button className="text-sm underline" onClick={() => openInExplorer(selected)}>
                Buka di Jelajah
              </button>
            </div>
          </Card>

          {dayPayload.loading && <div className="mt-3"><Loading /></div>}
          {dayPayload.error && <div className="mt-3"><ErrorNote message={dayPayload.error} /></div>}
          {dayPayload.data && dayPayload.data.items.length === 0 && (
            <div className="mt-3"><Empty label="Tidak ada konten pada tanggal ini" hint="Coba tanggal lain di kalender kiri." /></div>
          )}

          <ul className="mt-3 space-y-3">
            {(dayPayload.data?.items || []).map((item) => (
              <li key={item.id}>
                <Card>
                  <button className="w-full text-left" onClick={() => setOpenId(item.id)}>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                      <span>{item.source_name}</span>
                      <span>·</span>
                      <span>{PLATFORM_LABEL[item.platform] || item.platform}</span>
                      <span>·</span>
                      <span title={`${formatWhen(item.published_at)} WIB`}>{relativeTime(item.published_at)}</span>
                    </div>
                    <p className="mt-2 text-base font-semibold leading-snug">
                      <QuoteBadge show={item.quotes_bi} /> {item.title}
                    </p>
                    <MentionBrief text={item.brief} className="mt-1 text-muted" />
                    <div className="mt-2 flex flex-wrap gap-2">
                      <SentimentBadge sentiment={item.sentiment} />
                      <StanceBadge stance={item.stance} />
                    </div>
                  </button>
                  <SourceLink url={item.url} />
                </Card>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <MentionDrawer mentionId={openId} onClose={() => setOpenId(null)} />
    </div>
  )
}
