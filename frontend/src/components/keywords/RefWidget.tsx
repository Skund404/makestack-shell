/**
 * Generic reference widget for MATERIAL_REF_, TOOL_REF_, TECHNIQUE_REF_.
 * Fetches the referenced primitive and renders a compact card with a link.
 */
import { ExternalLink, Loader2 } from 'lucide-react'
import { usePrimitive } from '@/hooks/use-catalogue'
import { primitiveTypeBg, truncate } from '@/lib/utils'
import type { KeywordContext } from '@/modules/keyword-resolver'
import { useNavigate } from '@tanstack/react-router'

interface RefWidgetProps {
  keyword: string
  value: unknown
  context: KeywordContext
}

export function RefWidget({ value, context: _context }: RefWidgetProps) {
  const path = typeof value === 'string' ? value : ''
  const { data, isLoading, isError } = usePrimitive(path)
  const navigate = useNavigate()

  if (!path) return <span className="text-text-faint text-xs italic">invalid ref</span>

  if (isLoading) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-text-faint">
        <Loader2 size={10} className="animate-spin" /> loading…
      </span>
    )
  }

  if (isError || !data) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-danger/70 font-mono">
        <ExternalLink size={10} />
        {path}
      </span>
    )
  }

  return (
    <button
      onClick={() => void navigate({ to: '/catalogue/detail', search: { path, at: undefined } })}
      className="inline-flex items-center gap-1.5 px-2 py-1 rounded border border-border-bright bg-surface-el hover:border-accent/30 hover:bg-surface transition-colors text-left"
    >
      <span className={`text-xs px-1.5 py-0.5 rounded border ${primitiveTypeBg(data.type)}`}>
        {data.type}
      </span>
      <span className="text-sm text-text font-medium">{data.name}</span>
      {data.description && (
        <span className="text-xs text-text-muted hidden sm:inline">
          — {truncate(data.description, 60)}
        </span>
      )}
    </button>
  )
}
