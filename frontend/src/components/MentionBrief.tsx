export default function MentionBrief({
  text,
  compact = true,
  className = '',
}: {
  text?: string
  compact?: boolean
  className?: string
}) {
  if (!text?.trim()) return null
  return (
    <p
      className={`mt-1.5 text-justify text-sm leading-7 tracking-normal text-foreground/90 [text-wrap:pretty] hyphens-auto ${compact ? 'line-clamp-4' : ''} ${className}`}
      lang="id"
    >
      {text}
    </p>
  )
}
