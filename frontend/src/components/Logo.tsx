export function LogoMark({ className = 'h-12 w-12' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 64 64" fill="none" aria-hidden>
      <circle cx="32" cy="32" r="31" fill="#0B1F3A" />
      <circle cx="32" cy="32" r="28.5" stroke="#C4A35A" strokeWidth="2.4" />
      <circle cx="32" cy="32" r="24.5" stroke="#C4A35A" strokeWidth="0.8" strokeDasharray="1.6 2.2" />
      <path d="M22 18 H32 C41.5 18 47 24 47 32 C47 40 41.5 46 32 46 H22 Z" fill="#C4A35A" />
      <path d="M27 23 H32 C38.5 23 41.5 27 41.5 32 C41.5 37 38.5 41 32 41 H27 Z" fill="#0B1F3A" />
      <rect x="29.5" y="34" width="2.6" height="4.5" rx="0.6" fill="#FFFFFF" />
      <rect x="33.4" y="30.5" width="2.6" height="8" rx="0.6" fill="#FFFFFF" />
      <rect x="37.3" y="27" width="2.6" height="11.5" rx="0.6" fill="#E1CB8E" />
    </svg>
  )
}

export function BiLogo({ variant = 'white', className = 'h-7 w-auto' }: { variant?: 'white' | 'blue'; className?: string }) {
  const src = variant === 'white' ? '/img/bi-logo-white.png' : '/img/bi-logo-blue.png'
  return <img src={src} alt="Bank Indonesia" className={className} />
}

export const APP_NAME = 'Danita'
export const APP_LONG = 'Dashboard Monitor Sentimen Berita'
export const OWNER = 'Kantor Perwakilan Bank Indonesia Provinsi DKI Jakarta'
export const UNIT = 'Kantor Perwakilan Bank Indonesia Provinsi DKI Jakarta'

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <LogoMark className="h-11 w-11 shrink-0" />
      <div>
        <p className={`text-xl font-extrabold uppercase leading-tight tracking-wide ${light ? 'text-white' : 'text-navy-900'}`}>{APP_NAME}</p>
        <p className={`text-[11px] uppercase leading-snug tracking-wide ${light ? 'text-slate-300' : 'text-muted'}`}>{APP_LONG}</p>
      </div>
    </div>
  )
}

export function Copyright({ className = '' }: { className?: string }) {
  return (
    <p className={className}>
      © {new Date().getFullYear()} {OWNER}. Hak cipta dilindungi.
    </p>
  )
}
