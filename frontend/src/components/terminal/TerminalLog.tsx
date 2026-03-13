/**
 * TerminalLog — scrollable list of terminal history entries.
 *
 * Auto-scrolls to the bottom when new entries arrive, but stops if the user
 * has scrolled up. A "↓" button re-enables auto-scroll.
 */
import { useEffect, useRef, useState } from 'react'
import { TerminalEntry } from './TerminalEntry'
import type { TerminalEntry as TEntry } from '@/lib/terminalTypes'

interface TerminalLogProps {
  entries: TEntry[]
}

const AT_BOTTOM_THRESHOLD = 40 // px

export function TerminalLog({ entries }: TerminalLogProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [userScrolled, setUserScrolled] = useState(false)

  // Scroll to bottom when new entries arrive, unless user has scrolled up.
  useEffect(() => {
    if (userScrolled) return
    const el = containerRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [entries, userScrolled])

  const handleScroll = () => {
    const el = containerRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < AT_BOTTOM_THRESHOLD
    setUserScrolled(!atBottom)
  }

  const scrollToBottom = () => {
    setUserScrolled(false)
    const el = containerRef.current
    if (el) el.scrollTop = el.scrollHeight
  }

  if (entries.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-xs text-text-faint font-mono">
        Type a command or use REST syntax: GET /api/status
      </div>
    )
  }

  return (
    <div className="flex-1 relative min-h-0">
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="h-full overflow-y-auto px-3 py-2 space-y-1"
      >
        {entries.map((entry, i) => (
          <TerminalEntry key={i} entry={entry} />
        ))}
      </div>
      {userScrolled && (
        <button
          onClick={scrollToBottom}
          title="Scroll to bottom"
          className="absolute bottom-2 right-3 text-[10px] font-mono text-text-faint hover:text-accent bg-surface border border-border rounded px-1.5 py-0.5 shadow-sm transition-colors"
        >
          ↓ bottom
        </button>
      )}
    </div>
  )
}
