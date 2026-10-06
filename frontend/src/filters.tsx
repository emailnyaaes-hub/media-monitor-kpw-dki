import { createContext, useContext, useMemo, useState } from 'react'
import { isoDate } from './format'

interface Filters {
  dateFrom: string
  dateTo: string
  platform: string
  category: string
  setDateFrom: (value: string) => void
  setDateTo: (value: string) => void
  setPlatform: (value: string) => void
  setCategory: (value: string) => void
  setPreset: (days: number) => void
  reset: () => void
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
      setDateFrom,
      setDateTo,
      setPlatform,
      setCategory,
      setPreset(days: number) {
        const end = new Date()
        const start = new Date()
        start.setDate(end.getDate() - (days - 1))
        setDateFrom(isoDate(start))
        setDateTo(isoDate(end))
      },
      reset() {
        const end = new Date()
        const start = new Date()
        start.setDate(end.getDate() - 29)
        setDateFrom(isoDate(start))
        setDateTo(isoDate(end))
        setPlatform('semua')
        setCategory('semua')
      },
      apply(next) {
        setDateFrom(next.dateFrom)
        setDateTo(next.dateTo)
        setPlatform(next.platform)
        setCategory(next.category)
      },
      query: params.toString(),
    }
  }, [dateFrom, dateTo, platform, category])

  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>
}

export function useFilters() {
  const value = useContext(FilterContext)
  if (!value) throw new Error('FilterProvider belum terpasang')
  return value
}
