export function formatNumber(value: number) {
  return new Intl.NumberFormat('id-ID').format(value)
}

export function formatReach(value: number) {
  if (!value) return 'tidak tersedia'
  return formatNumber(value)
}

export function formatPct(value: number, digits = 1) {
  return `${new Intl.NumberFormat('id-ID', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value)}%`
}

export function formatSigned(value: number, suffix = '') {
  const number = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1, signDisplay: 'exceptZero' }).format(value)
  return `${number}${suffix}`
}

export function formatWhen(iso: string) {
  const [date, time] = iso.split('T')
  if (!date) return iso
  const [year, month, day] = date.split('-').map(Number)
  const [hour, minute] = (time || '00:00').split(':')
  const stamp = new Date(year, (month || 1) - 1, day || 1, Number(hour), Number(minute))
  return new Intl.DateTimeFormat('id-ID', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(stamp)
}

export function relativeTime(iso: string) {
  const [date, time] = iso.split('T')
  if (!date) return iso
  const [year, month, day] = date.split('-').map(Number)
  const [hour, minute] = (time || '00:00').split(':')
  const stamp = new Date(year, (month || 1) - 1, day || 1, Number(hour), Number(minute))
  const minutes = Math.round((Date.now() - stamp.getTime()) / 60000)
  if (Number.isNaN(minutes)) return formatWhen(iso)
  if (minutes < 1) return 'baru saja'
  if (minutes < 60) return `${minutes} menit lalu`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} jam lalu`
  const days = Math.round(hours / 24)
  if (days < 14) return `${days} hari lalu`
  return formatWhen(iso)
}

export function formatDay(isoDate: string) {
  const [year, month, day] = isoDate.split('-').map(Number)
  if (!year || !month || !day) return isoDate
  return new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'short' }).format(new Date(year, month - 1, day))
}

export function isoDate(value: Date) {
  const month = `${value.getMonth() + 1}`.padStart(2, '0')
  const day = `${value.getDate()}`.padStart(2, '0')
  return `${value.getFullYear()}-${month}-${day}`
}

export const PLATFORM_LABEL: Record<string, string> = {
  berita: 'Berita online',
  x: 'X',
  instagram: 'Instagram',
  tiktok: 'TikTok',
  youtube: 'YouTube',
  facebook: 'Facebook',
  threads: 'Threads',
  forum: 'Forum',
}

export const STATUS_LABEL: Record<string, string> = {
  baru: 'Baru',
  ditinjau: 'Ditinjau',
  dieskalasi: 'Dieskalasi',
  ditangani: 'Ditangani',
  selesai: 'Selesai',
}

export const SOURCES = [
  'Detik',
  'Kompas',
  'CNBC Indonesia',
  'Kontan',
  'Bisnis.com',
  'Bloomberg Technoz',
  'CNN Indonesia',
  'Tempo',
  'Antara',
  'Liputan6',
  'Berita Jakarta',
  'Warta Kota',
]
