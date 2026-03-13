/**
 * LogPanel — passive real-time view of all backend structlog events.
 *
 * Subscribes to GET /api/terminal/stream (SSE) via useLogStream.
 * Client-side filters: entry type toggles (SYSTEM / SLOW / MODULE / ERROR).
 * Timestamp toggle + auto-scroll toggle.
 * Filter and UI state persisted to sessionStorage.
 */
import { useState } from 'react'
import { Trash2, Wifi, WifiOff } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useLogStream } from '@/hooks/useLogStream'
import { LogStream } from './LogStream'
import type { TerminalEntry } from '@/lib/terminalTypes'

// ---------------------------------------------------------------------------
// Helpers — derive display category from a structlog 'log' entry
// ---------------------------------------------------------------------------

type LogCategory = 'system' | 'slow' | 'module' | 'error'

function getCategory(entry: TerminalEntry): LogCategory {
  if (entry.level === 'error') return 'error'
  if (typeof entry.elapsed_ms === 'number' && entry.elapsed_ms > 1000) return 'slow'
  if (entry.component?.toLowerCase().includes('module')) return 'module'
  return 'system'
}

// ---------------------------------------------------------------------------
// Session-storage helpers
// ---------------------------------------------------------------------------

const SS_HIDDEN = 'log-hidden-categories'
const SS_TIMESTAMPS = 'log-show-timestamps'
const SS_AUTOSCROLL = 'log-auto-scroll'

function loadSet(key: string, defaults: string[]): Set<string> {
  try {
    const raw = sessionStorage.getItem(key)
    return raw ? new Set(JSON.parse(raw) as string[]) : new Set(defaults)
  } catch {
    return new Set(defaults)
  }
}

function saveSet(key: string, s: Set<string>): void {
  try { sessionStorage.setItem(key, JSON.stringify([...s])) } catch { /* ignore */ }
}

function loadBool(key: string, defaultVal: boolean): boolean {
  try {
    const raw = sessionStorage.getItem(key)
    return raw === null ? defaultVal : raw === 'true'
  } catch {
    return defaultVal
  }
}

function saveBool(key: string, v: boolean): void {
  try { sessionStorage.setItem(key, String(v)) } catch { /* ignore */ }
}

// ---------------------------------------------------------------------------
// Toggle button for entry type filters
// ---------------------------------------------------------------------------

interface TypeToggleProps {
  label: string
  active: boolean
  onClick: () => void
}

function TypeToggle({ label, active, onClick }: TypeToggleProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'text-[10px] font-mono px-1 py-px rounded transition-colors',
        active ? 'text-accent' : 'text-text-faint/50 line-through hover:text-text-faint',
      )}
      title={active ? `Hide ${label}` : `Show ${label}`}
    >
      {label}
    </button>
  )
}

// ---------------------------------------------------------------------------
// LogPanel
// ---------------------------------------------------------------------------

export function LogPanel() {
  const { entries, isConnected, clear } = useLogStream()

  const [hiddenCats, setHiddenCats] = useState<Set<string>>(() =>
    loadSet(SS_HIDDEN, []) // default: show all
  )
  const [showTimestamps, setShowTimestamps] = useState(() => loadBool(SS_TIMESTAMPS, false))
  const [autoScroll, setAutoScroll] = useState(() => loadBool(SS_AUTOSCROLL, true))

  const toggleCategory = (cat: string) => {
    setHiddenCats((prev) => {
      const next = new Set(prev)
      if (next.has(cat)) next.delete(cat)
      else next.add(cat)
      saveSet(SS_HIDDEN, next)
      return next
    })
  }

  const toggleTimestamps = () => {
    setShowTimestamps((v) => { saveBool(SS_TIMESTAMPS, !v); return !v })
  }

  const toggleAutoScroll = () => {
    setAutoScroll((v) => { saveBool(SS_AUTOSCROLL, !v); return !v })
  }

  // Apply category filter (only applies to 'log' entries; others pass through).
  const filtered = entries.filter((e) => {
    if (e.type !== 'log') return true
    return !hiddenCats.has(getCategory(e))
  })

  const cats: LogCategory[] = ['system', 'slow', 'module', 'error']

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-1.5 px-3 py-1 border-b border-border shrink-0 flex-wrap">
        <span className="text-[10px] text-text-faint font-mono shrink-0">log stream</span>

        {isConnected ? (
          <Wifi size={10} className="text-success shrink-0" />
        ) : (
          <WifiOff size={10} className="text-warning shrink-0" />
        )}

        <div className="w-px h-3 bg-border shrink-0 mx-0.5" />

        {/* Entry type toggles */}
        {cats.map((cat) => (
          <TypeToggle
            key={cat}
            label={cat}
            active={!hiddenCats.has(cat)}
            onClick={() => toggleCategory(cat)}
          />
        ))}

        <div className="flex-1" />

        {/* Timestamp toggle */}
        <button
          onClick={toggleTimestamps}
          title={showTimestamps ? 'Hide timestamps' : 'Show timestamps'}
          className={cn(
            'text-[10px] font-mono px-1 py-px rounded shrink-0 transition-colors',
            showTimestamps ? 'text-accent' : 'text-text-faint hover:text-text',
          )}
        >
          ts
        </button>

        {/* Auto-scroll toggle */}
        <button
          onClick={toggleAutoScroll}
          title={autoScroll ? 'Disable auto-scroll' : 'Enable auto-scroll'}
          className={cn(
            'text-[10px] font-mono px-1 py-px rounded shrink-0 transition-colors',
            autoScroll ? 'text-accent' : 'text-text-faint hover:text-text',
          )}
          aria-label={autoScroll ? 'Disable auto-scroll' : 'Enable auto-scroll'}
        >
          ↓↓
        </button>

        {/* Clear */}
        <button
          onClick={clear}
          title="Clear log"
          className="text-text-faint hover:text-text transition-colors"
          aria-label="Clear log"
        >
          <Trash2 size={11} />
        </button>
      </div>

      <LogStream
        entries={filtered}
        showTimestamps={showTimestamps}
        autoScroll={autoScroll}
      />
    </div>
  )
}
