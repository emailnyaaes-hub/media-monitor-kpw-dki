export function LogoMark({ className = 'h-12 w-12' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 64 64" fill="none" aria-hidden>
      <path d="M7 30 L32 16 L57 30 L52 56 L32 49 L12 56 Z" fill="#F7F4EC" stroke="#0B1F3A" strokeWidth="2" strokeLinejoin="round" />
      <path d="M32 16 V49" stroke="#0B1F3A" strokeWidth="1.75" />
      <path d="M15 33 H27" stroke="#0B1F3A" strokeWidth="2" strokeLinecap="round" />
      <path d="M15 39 H24" stroke="#0B1F3A" strokeWidth="2" strokeLinecap="round" />
      <path d="M15 45 H26" stroke="#8B93A0" strokeWidth="2" strokeLinecap="round" />
      <path d="M37 33 H49" stroke="#C4A35A" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M37 39 H46" stroke="#0B1F3A" strokeWidth="2" strokeLinecap="round" />
      <path d="M37 45 H43" stroke="#8B93A0" strokeWidth="2" strokeLinecap="round" />
      <path d="M34 14 C44 2 58 8 55 22" stroke="#C4A35A" strokeWidth="2.4" strokeLinecap="round" />
      <circle cx="55" cy="22" r="3" fill="#C4A35A" />
      <circle cx="55" cy="22" r="1.2" fill="#0B1F3A" />
    </svg>
  )
}

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <LogoMark />
      <div>
        <p className={`font-serif text-lg leading-tight ${light ? 'text-white' : 'text-navy-900'}`}>Media Monitor</p>
        <p className={`text-sm ${light ? 'text-slate-300' : 'text-muted'}`}>KPw BI DKI Jakarta</p>
      </div>
    </div>
  )
}
