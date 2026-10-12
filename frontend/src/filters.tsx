import { createContext, useContext, useMemo, useRef, useState } from 'react'
import { isoDate } from './format'

interface Snapshot {
  dateFrom: string
  dateTo: string
  platform: string
  category: string
  returnTo: string
}

interface Filters {
  dateFrom: string
  dateTo: string
  platform: string
  category: string
  narrowed: boolean
  setDateFrom: (value: string) => void
  setDateTo: (value: string) => void
  setPlatform: (value: string) => void
  setCategory: (value: string) => void
  setPreset: (days: number) => void
  reset: () => void
  focusDay: (day: string, returnTo: string) => void
  backToGeneral: () => Snapshot | null
  apply: (next: { dateFrom: string; dateTo: string; platform: string; category: string }) => void
  query: string
}

const FilterContext = createContext<Filters | null>(null)

function initialRange() {
  const stored = sessionStorage.getItem('bi-filters')
  if (stored) {
    try {
      const parsed = JSON.parse(stored) as { dateFrom: string; dateTo: string; platform: string; category: string }
      if (parsed.dateFrom && parsed.dateTo) return parsed
    } catch {
      /* abaikan sesi rusak */
    }
  }
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - 29)
  return { dateFrom: isoDate(start), dateTo: isoDate(end), platform: 'semua', category: 'semua' }
}

export function FilterProvider({ children }: { children: React.ReactNode }) {
  const [dateFrom, setDateFrom] = useState(initialRange().dateFrom)
  const [dateTo, setDateTo] = useState(initialRange().dateTo)
  const [platform, setPlatform] = useState(initialRange().platform)
  const [category, setCategory] = useState(initialRange().category)
  const [narrowed, setNarrowed] = useState(false)
  const general = useRef<Snapshot | null>(null)

  function clearGeneral() {
    general.current = null
    setNarrowed(false)
  }

  const value = useMemo<Filters>(() => {
    const params = new URLSearchParams()
    params.set('date_from', dateFrom)
    params.set('date_to', dateTo)
    if (platform !== 'semua') params.set('platform', platform)
    if (category !== 'semua') params.set('category', category)
    sessionStorage.setItem('bi-filters', JSON.stringify({ dateFrom, dateTo, platform, category }))
    return {
      dateFrom,
      dateTo,
      platform,
      category,
      narrowed,
      setDateFrom,
      setDateTo,
      setPlatform,
      setCategory,
      setPreset(days: number) {
        clearGeneral()
        const end = new Date()
        const start = new Date()
        start.setDate(end.getDate() - (days - 1))
        setDateFrom(isoDate(start))
        setDateTo(isoDate(end))
      },
      reset() {
        clearGeneral()
        const end = new Date()
        const start = new Date()
        start.setDate(end.getDate() - 29)
        setDateFrom(isoDate(start))
        setDateTo(isoDate(end))
        setPlatform('semua')
        setCategory('semua')
      },
      focusDay(day: string, returnTo: string) {
        if (!general.current) {
          general.current = { dateFrom, dateTo, platform, category, returnTo }
          setNarrowed(true)
        }
        setDateFrom(day)
        setDateTo(day)
      },
      backToGeneral() {
        const saved = general.current
        general.current = null
        setNarrowed(false)
        if (!saved) return null
        setDateFrom(saved.dateFrom)
        setDateTo(saved.dateTo)
        setPlatform(saved.platform)
        setCategory(saved.category)
        return saved
      },
      apply(next) {
        setDateFrom(next.dateFrom)
        setDateTo(next.dateTo)
        setPlatform(next.platform)
        setCategory(next.category)
      },
      query: params.toString(),
    }
  }, [dateFrom, dateTo, platform, category, narrowed])

  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>
}

export function useFilters() {
  const value = useContext(FilterContext)
  if (!value) throw new Error('FilterProvider belum terpasang')
  return value
}
