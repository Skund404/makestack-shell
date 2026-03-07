import { ExternalLink } from 'lucide-react'
import type { KeywordContext } from '@/modules/keyword-resolver'

interface LinkValue {
  url: string
  label?: string
}

interface LinkWidgetProps {
  keyword: string
  value: unknown
  context: KeywordContext
}

export function LinkWidget({ value, context: _context }: LinkWidgetProps) {
  const url = typeof value === 'string' ? value : (value as LinkValue)?.url ?? ''
  const label = typeof value === 'object' && value !== null ? (value as LinkValue).label : undefined

  if (!url) return null

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-sm text-accent hover:underline"
    >
      {label ?? url}
      <ExternalLink size={11} />
    </a>
  )
}
