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
      className={`mt-1.5 text-sm leading-relaxed text-foreground/90 ${compact ? 'line-clamp-3' : ''} ${className}`}
    >
      {text}
    </p>
  )
}
