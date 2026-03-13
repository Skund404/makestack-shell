/**
 * DocsCommandEntry — renders a CLI command entry with CLI + REST side by side.
 */
import { Terminal } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { CliCommand } from '@/hooks/useDocsIndex'

interface DocsCommandEntryProps {
  entry: CliCommand
  selected: boolean
  onRun: (input: string) => void
}

export function DocsCommandEntry({ entry, selected, onRun }: DocsCommandEntryProps) {
  const cliExample = entry.accepts_arg ? `${entry.keyword} <type>` : entry.keyword
  const restExample = `${entry.method} ${entry.path}${entry.accepts_arg ? '/<type>' : ''}`

  return (
    <div className={cn(
      'flex items-start gap-2 px-3 py-1.5 group',
      selected ? 'bg-accent/10' : 'hover:bg-surface-el/40',
    )}>
      {/* CLI syntax (left) */}
      <div className="w-28 shrink-0">
        <div className="font-mono text-[11px] text-accent truncate">{cliExample}</div>
        {entry.description && (
          <div className="text-[10px] text-text-faint truncate">{entry.description}</div>
        )}
      </div>

      {/* Divider */}
      <div className="shrink-0 text-text-faint/30 font-mono text-[10px] pt-px">→</div>

      {/* REST equivalent (right) */}
      <div className="flex-1 min-w-0">
        <div className="font-mono text-[10px] text-text-muted truncate">{restExample}</div>
      </div>

      <button
        onClick={() => onRun(cliExample)}
        title="Run in terminal"
        className="shrink-0 flex items-center gap-0.5 text-[9px] text-text-faint hover:text-accent transition-colors opacity-0 group-hover:opacity-100 px-1 py-0.5 rounded border border-transparent hover:border-accent/30"
      >
        <Terminal size={9} />
        <span>run</span>
      </button>
    </div>
  )
}
