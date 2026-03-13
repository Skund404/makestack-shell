/**
 * DocsWidgetEntry — renders a widget entry with live preview.
 * Keyword name, description, accepts list, DocsWidgetPreview, source badge.
 */
import { Terminal } from 'lucide-react'
import { cn } from '@/lib/utils'
import { DocsWidgetPreview } from './DocsWidgetPreview'
import type { WidgetMeta } from '@/modules/keyword-resolver'

interface DocsWidgetEntryProps {
  entry: WidgetMeta
  selected: boolean
  onRun: (input: string) => void
}

export function DocsWidgetEntry({ entry, selected, onRun }: DocsWidgetEntryProps) {
  const exampleValue = entry.accepts[0] ?? ''
  const runInput = `{"${entry.keyword}": "${exampleValue}"}`

  return (
    <div className={cn(
      'px-3 py-1.5 group',
      selected ? 'bg-accent/10' : 'hover:bg-surface-el/40',
    )}>
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-[11px] text-[#c586c0]">{entry.keyword}</span>
            <span className="text-[9px] text-text-faint/50 border border-border rounded px-1">
              {entry.source}
            </span>
          </div>
          <div className="text-[10px] text-text-faint truncate">{entry.description}</div>
          <div className="text-[10px] text-text-faint/50 truncate">
            accepts: {entry.accepts.join(', ')}
          </div>
        </div>
        <button
          onClick={() => onRun(runInput)}
          title="Run in terminal"
          className="shrink-0 flex items-center gap-0.5 text-[9px] text-text-faint hover:text-accent transition-colors opacity-0 group-hover:opacity-100 px-1 py-0.5 rounded border border-transparent hover:border-accent/30"
        >
          <Terminal size={9} />
          <span>run</span>
        </button>
      </div>

      {/* Live preview */}
      <DocsWidgetPreview keyword={entry.keyword} initialValue={exampleValue} />
    </div>
  )
}
