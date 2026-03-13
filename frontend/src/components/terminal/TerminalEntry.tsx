/**
 * TerminalEntry — renders a single entry (all 6 types).
 *
 *   command  → $ input line
 *   request  → → METHOD /path [body preview]
 *   response → ← status elapsed_ms + collapsible JSON body
 *   error    → ✗ message + suggestion in amber
 *   log      → structlog event (used by LogStream as shared renderer)
 */
import { cn } from '@/lib/utils'
import { JsonViewer } from './JsonViewer'
import type { TerminalEntry as TEntry } from '@/lib/terminalTypes'

interface TerminalEntryProps {
  entry: TEntry
  showTimestamp?: boolean
}

const LEVEL_COLOR: Record<string, string> = {
  debug:   'text-text-faint',
  info:    'text-text-muted',
  warning: 'text-warning',
  error:   'text-danger',
}

const METHOD_COLOR: Record<string, string> = {
  GET:    'text-[#4ec9b0]',
  POST:   'text-[#ce9178]',
  PUT:    'text-[#dcdcaa]',
  DELETE: 'text-danger',
  PATCH:  'text-warning',
}

function Timestamp({ ts }: { ts: string }) {
  try {
    return (
      <span className="text-text-faint shrink-0 tabular-nums font-mono text-[10px]">
        {new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
      </span>
    )
  } catch {
    return null
  }
}

export function TerminalEntry({ entry, showTimestamp = false }: TerminalEntryProps) {
  // command — what the user typed
  if (entry.type === 'command') {
    return (
      <div className="flex items-baseline gap-2 py-0.5">
        {showTimestamp && <Timestamp ts={entry.timestamp} />}
        <span className="text-accent font-mono text-xs select-none shrink-0">$</span>
        <span className="text-text font-mono text-xs">{entry.event}</span>
      </div>
    )
  }

  // request — translated HTTP call
  if (entry.type === 'request') {
    const methodColor = METHOD_COLOR[entry.method?.toUpperCase() ?? ''] ?? 'text-text-muted'
    return (
      <div className="flex items-baseline gap-2 py-0.5 pl-4">
        {showTimestamp && <Timestamp ts={entry.timestamp} />}
        <span className="text-text-faint font-mono text-[10px] select-none shrink-0">→</span>
        <span className={cn('font-mono text-xs shrink-0', methodColor)}>{entry.method}</span>
        <span className="text-text-muted font-mono text-xs">{entry.path}</span>
        {entry.body && (
          <span className="text-text-faint font-mono text-[10px] truncate max-w-[20rem]">
            {entry.body}
          </span>
        )}
      </div>
    )
  }

  // response — HTTP response with status + body
  if (entry.type === 'response') {
    const ok = (entry.status_code ?? 0) < 400
    return (
      <div className="pl-4 py-0.5 space-y-1">
        <div className="flex items-center gap-2 font-mono text-xs">
          {showTimestamp && <Timestamp ts={entry.timestamp} />}
          <span className="text-text-faint select-none">←</span>
          <span className={cn('font-semibold tabular-nums', ok ? 'text-success' : 'text-warning')}>
            {entry.status_code}
          </span>
          {entry.elapsed_ms !== undefined && (
            <span className="text-text-faint text-[10px]">{entry.elapsed_ms}ms</span>
          )}
        </div>
        {entry.body && entry.body.length > 0 && (
          <JsonViewer value={entry.body} className="ml-4" />
        )}
      </div>
    )
  }

  // error — command failure or unknown command
  if (entry.type === 'error') {
    return (
      <div className="pl-4 border-l border-danger/40 py-0.5 space-y-0.5">
        {showTimestamp && <Timestamp ts={entry.timestamp} />}
        <div className="font-mono text-xs text-danger">{entry.event}</div>
        {typeof entry.suggestion === 'string' && entry.suggestion && (
          <div className="text-xs text-warning/80">{entry.suggestion}</div>
        )}
      </div>
    )
  }

  // log — structlog backend event (used by LogStream)
  if (entry.type === 'log') {
    const levelClass = LEVEL_COLOR[entry.level ?? 'info'] ?? 'text-text-muted'
    // Extra fields (beyond the standard set) shown on hover.
    const SKIP = new Set(['type', 'timestamp', 'level', 'component', 'event'])
    const extras = Object.entries(entry)
      .filter(([k, v]) => !SKIP.has(k) && v !== undefined && v !== null && v !== '')
      .map(([k, v]) => `${k}=${String(v)}`)
      .slice(0, 4)
      .join(' ')

    return (
      <div className="flex gap-1.5 leading-4 font-mono text-[11px] group hover:bg-surface-el/30 rounded px-1 py-0.5">
        {showTimestamp && (
          <span className="text-text-faint shrink-0 w-[5.5rem] text-right tabular-nums">
            <Timestamp ts={entry.timestamp} />
          </span>
        )}
        <span className={cn('w-14 shrink-0 text-right font-medium', levelClass)}>
          {entry.level ?? 'info'}
        </span>
        <span className="text-text-faint w-20 shrink-0 truncate">{entry.component}</span>
        <span className="text-text flex-1 truncate">{entry.event}</span>
        {extras && (
          <span className="text-text-faint truncate max-w-[12rem] hidden group-hover:inline">
            {extras}
          </span>
        )}
      </div>
    )
  }

  return null
}
