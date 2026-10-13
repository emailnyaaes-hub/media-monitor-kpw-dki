export interface Evidence {
  id: number | null
  title: string
  url: string
  source: string
  published_at: string
}

export interface Count {
  label: string
  jumlah: number
}

export interface Narrative {
  label: string
  jumlah: number
  sumber: string[]
  bukti: Evidence[]
}

export const TOPICS = [
  'Ekonomi Jakarta',
  'Inflasi dan harga',
  'Rupiah/kurs',
  'Suku bunga',
  'Sistem pembayaran',
  'Pengedaran uang',
  'UMKM',
  'Perbankan/kredit',
  'Persepsi terhadap BI',
]

export const SEGMENTS = [
  'UMKM dan pedagang',
  'Konsumen dan rumah tangga',
  'Anak muda dan mahasiswa',
  'Pelaku fintech dan merchant',
  'Pengemudi dan pekerja informal',
  'Akademisi dan pengamat',
  'Media',
  'segmen tidak teridentifikasi',
]

export const AREAS = ['Jakarta Pusat', 'Jakarta Utara', 'Jakarta Barat', 'Jakarta Selatan', 'Jakarta Timur', 'Kepulauan Seribu']

export const VOICE_OPTIONS = [
  ['keluhan', 'Keluhan'],
  ['apresiasi', 'Apresiasi'],
  ['kebutuhan', 'Kebutuhan dan harapan'],
  ['hoaks', 'Salah paham dan hoaks'],
] as const

export function levelClass(level: string) {
  if (level === 'Tinggi' || level === 'Segera') return 'bg-red-50 text-red-800 dark:bg-red-950/50 dark:text-red-200'
  if (level === 'Sedang' || level === 'Minggu ini') return 'bg-amber-50 text-amber-900 dark:bg-amber-950/50 dark:text-amber-200'
  return 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200'
}
