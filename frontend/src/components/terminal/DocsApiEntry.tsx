/**
 * DocsApiEntry — renders a single API operation entry in the DocsPanel.
 * Shows method badge, path, summary, and a "Run in terminal" button.
 */
import { Terminal } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Capability } from '@/hooks/useDocsIndex'

const METHOD_COLOR: Record<string, string> = {
  GET:    'text-[#4ec9b0]',
  POST:   'text-[#ce9178]',
  PUT:    'text-[#dcdcaa]',
  DELETE: 'text-danger',
  PATCH:  'text-warning',
}

interface DocsApiEntryProps {
  entry: Capability
  selected: boolean
  onRun: (input: string) => void
}

export function DocsApiEntry({ entry, selected, onRun }: DocsApiEntryProps) {
  const methodColor = METHOD_COLOR[entry.method.toUpperCase()] ?? 'text-text-muted'

  return (
    <div className={cn(
      'flex items-start gap-2 px-3 py-1.5 group',
      selected ? 'bg-accent/10' : 'hover:bg-surface-el/40',
    )}>
      <span className={cn('font-mono text-[10px] w-12 shrink-0 pt-px', methodColor)}>
        {entry.method.toUpperCase()}
      </span>
      <div className="flex-1 min-w-0">
        <div className="font-mono text-[11px] text-text truncate">{entry.path}</div>
        {entry.summary && (
          <div className="text-[10px] text-text-faint truncate">{entry.summary}</div>
        )}
      </div>
      <button
        onClick={() => onRun(`${entry.method.toUpperCase()} ${entry.path}`)}
        title="Run in terminal"
        className="shrink-0 flex items-center gap-0.5 text-[9px] text-text-faint hover:text-accent transition-colors opacity-0 group-hover:opacity-100 px-1 py-0.5 rounded border border-transparent hover:border-accent/30"
      >
        <Terminal size={9} />
        <span>run</span>
      </button>
    </div>
  )
}
