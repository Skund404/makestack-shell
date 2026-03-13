/**
 * LogStream — scrollable, auto-scrolling view of live structlog events.
 *
 * Uses the shared TerminalEntry renderer for consistent entry display.
 * Auto-scroll: follows new entries unless user scrolls up (same logic as TerminalLog).
 */
import { useEffect, useRef, useState } from 'react'
import { TerminalEntry } from './TerminalEntry'
import type { TerminalEntry as TEntry } from '@/lib/terminalTypes'

interface LogStreamProps {
  entries: TEntry[]
  showTimestamps: boolean
  autoScroll: boolean
}

const AT_BOTTOM_THRESHOLD = 40

export function LogStream({ entries, showTimestamps, autoScroll }: LogStreamProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [userScrolled, setUserScrolled] = useState(false)

  useEffect(() => {
    if (!autoScroll || userScrolled) return
    const el = containerRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [entries, autoScroll, userScrolled])

  // Reset userScrolled when autoScroll is toggled back on.
  useEffect(() => {
    if (autoScroll) setUserScrolled(false)
  }, [autoScroll])

  const handleScroll = () => {
    const el = containerRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < AT_BOTTOM_THRESHOLD
    setUserScrolled(!atBottom)
  }

  if (entries.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-xs text-text-faint font-mono">
        Waiting for log events…
      </div>
    )
  }

  return (
    <div className="flex-1 relative min-h-0">
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="h-full overflow-y-auto px-2 py-1.5"
      >
        {entries.map((entry, i) => (
          <TerminalEntry key={i} entry={entry} showTimestamp={showTimestamps} />
        ))}
      </div>
      {userScrolled && autoScroll && (
        <button
          onClick={() => {
            setUserScrolled(false)
            const el = containerRef.current
            if (el) el.scrollTop = el.scrollHeight
          }}
          className="absolute bottom-2 right-3 text-[10px] font-mono text-text-faint hover:text-accent bg-surface border border-border rounded px-1.5 py-0.5 shadow-sm transition-colors"
        >
          ↓ bottom
        </button>
      )}
    </div>
  )
}
