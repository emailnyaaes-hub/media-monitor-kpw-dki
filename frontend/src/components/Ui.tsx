import {
  AlertTriangle,
  CheckCircle2,
  Info,
  Minus,
  ShieldAlert,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { formatNumber, formatSigned, STATUS_LABEL } from '../format'
import type { Sentiment, Severity, Stance } from '../types'

export function PageHeader({ title, description }: { title: string; description: string }) {
  return (
    <div className="mb-5">
      <h1 className="font-serif text-2xl font-medium tracking-tight md:text-3xl">{title}</h1>
      <p className="mt-1 max-w-3xl text-base text-muted">{description}</p>
    </div>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-md border border-line bg-card p-4 ${className}`}>{children}</section>
}

export function Loading() {
  return (
    <div className="grid gap-3">
      <div className="h-16 animate-pulse rounded-md bg-line/80" />
      <div className="h-40 animate-pulse rounded-md bg-line/80" />
    </div>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-base text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">{message}</div>
}

export function Empty({ label }: { label: string }) {
  return <p className="py-8 text-center text-sm text-muted">{label}</p>
}

export function StanceBadge({ stance }: { stance: Stance }) {
  const map = {
    upside: { label: 'Upside', icon: TrendingUp, className: 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200' },
    netral: { label: 'Netral', icon: Minus, className: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200' },
    downside: { label: 'Downside', icon: TrendingDown, className: 'bg-red-50 text-red-800 dark:bg-red-950/50 dark:text-red-200' },
  }[stance]
  const Icon = map.icon
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${map.className}`}>
      <Icon size={13} aria-hidden />
      {map.label}
    </span>
  )
}

export function SentimentBadge({ sentiment }: { sentiment: Sentiment }) {
  const map = {
    positif: { label: 'Positif', icon: TrendingUp, className: 'text-emerald-700 dark:text-emerald-300' },
    netral: { label: 'Netral', icon: Minus, className: 'text-slate-600 dark:text-slate-300' },
    negatif: { label: 'Negatif', icon: TrendingDown, className: 'text-red-700 dark:text-red-300' },
  }[sentiment]
  const Icon = map.icon
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium ${map.className}`}>
      <Icon size={13} aria-hidden />
      {map.label}
    </span>
  )
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  const map = {
    info: { label: 'Info', icon: Info, className: 'bg-sky-50 text-sky-800 dark:bg-sky-950/40 dark:text-sky-200' },
    waspada: { label: 'Waspada', icon: AlertTriangle, className: 'bg-amber-50 text-amber-900 dark:bg-amber-950/40 dark:text-amber-100' },
    kritis: { label: 'Kritis', icon: ShieldAlert, className: 'bg-red-50 text-red-800 dark:bg-red-950/50 dark:text-red-200' },
  }[severity]
  const Icon = map.icon
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${map.className}`}>
      <Icon size={13} aria-hidden />
      {map.label}
    </span>
  )
}

export function StatusBadge({ status }: { status: string }) {
  const tone: Record<string, string> = {
    baru: 'bg-sky-50 text-sky-800 dark:bg-sky-950/40 dark:text-sky-100',
    ditinjau: 'bg-gold-100 text-navy-900 dark:bg-navy-800 dark:text-gold-300',
    dieskalasi: 'bg-red-50 text-red-800 dark:bg-red-950/40 dark:text-red-100',
    ditangani: 'bg-indigo-50 text-indigo-800 dark:bg-indigo-950/40 dark:text-indigo-100',
    selesai: 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-100',
  }
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${tone[status] || tone.baru}`}>{STATUS_LABEL[status] || status}</span>
}

export function Delta({ value, good, suffix = '%' }: { value: number | null | undefined; good: 'up' | 'down' | 'neutral'; suffix?: string }) {
  if (value == null) return <span className="text-xs text-muted">Tidak ada pembanding</span>
  const higher = value > 0
  const helpful = good === 'neutral' ? null : good === 'up' ? higher : !higher && value !== 0
  const color = value === 0 || good === 'neutral' ? 'text-muted' : helpful ? 'text-emerald-700 dark:text-emerald-300' : 'text-red-700 dark:text-red-300'
  return (
    <span className={`text-xs font-medium ${color}`}>
      {formatSigned(value, suffix)} vs periode sebelumnya
    </span>
  )
}

export function Kpi({
  label,
  value,
  hint,
  delta,
  good,
  suffix,
}: {
  label: string
  value: string
  hint: string
  delta?: number | null
  good?: 'up' | 'down' | 'neutral'
  suffix?: string
}) {
  return (
    <Card>
      <p className="text-xs font-medium uppercase tracking-wide text-muted" title={hint}>{label}</p>
      <p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p>
      {good && <div className="mt-2"><Delta value={delta} good={good} suffix={suffix} /></div>}
      <p className="mt-2 text-xs text-muted">{hint}</p>
    </Card>
  )
}

export function SourceLink({ url }: { url?: string }) {
  if (!url) return null
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className="inline-flex min-h-11 items-center text-base text-navy-700 underline dark:text-gold-300"
      onClick={(event) => event.stopPropagation()}
    >
      Buka sumber asli
    </a>
  )
}

export function QuoteBadge({ show }: { show?: boolean }) {
  if (!show) return null
  return <span className="rounded-full bg-gold-100 px-2 py-0.5 text-[11px] font-medium text-navy-900">Mengutip BI</span>
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid gap-1 text-xs font-medium text-muted">
      {label}
      {children}
    </label>
  )
}

export const inputClass = 'h-11 min-h-11 rounded-md border border-line bg-card px-2 text-base text-ink'

export function Help({ text }: { text: string }) {
  return (
    <button type="button" className="ml-1 inline-grid h-5 w-5 place-items-center rounded-sm border border-line text-[11px] leading-none text-muted" title={text} aria-label={text}>
      ?
    </button>
  )
}

export function RiskBar({ score }: { score: number }) {
  const tone = score >= 75 ? 'bg-red-600' : score >= 55 ? 'bg-amber-500' : 'bg-emerald-600'
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-line" aria-hidden>
        <div className={`h-full ${tone}`} style={{ width: `${Math.max(4, Math.min(100, score))}%` }} />
      </div>
      <span className="tabular-nums text-xs">{formatNumber(Math.round(score))}</span>
    </div>
  )
}

export function VerifiedNote() {
  return (
    <span className="inline-flex items-center gap-1 text-xs text-amber-800 dark:text-amber-200">
      <AlertTriangle size={13} aria-hidden />
      Perlu diverifikasi
    </span>
  )
}

export function HumanNote() {
  return (
    <span className="inline-flex items-center gap-1 text-xs text-navy-800 dark:text-gold-300">
      <CheckCircle2 size={13} aria-hidden />
      Dikoreksi manusia
    </span>
  )
}
