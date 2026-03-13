/**
 * JsonViewer — pretty-prints a JSON string with a collapse toggle for long output.
 * Falls back to raw monospace text if the string is not valid JSON.
 */
import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

interface JsonViewerProps {
  value: string
  className?: string
}

const COLLAPSE_THRESHOLD = 6 // lines

export function JsonViewer({ value, className }: JsonViewerProps) {
  const [collapsed, setCollapsed] = useState(false)

  let display = value
  let isJson = false
  try {
    display = JSON.stringify(JSON.parse(value), null, 2)
    isJson = true
  } catch {
    // Not JSON — render raw.
  }

  const lineCount = display.split('\n').length
  const collapsible = isJson && lineCount > COLLAPSE_THRESHOLD

  return (
    <div className={cn('text-xs', className)}>
      {collapsible && (
        <button
          onClick={() => setCollapsed((v) => !v)}
          className="flex items-center gap-0.5 text-text-faint hover:text-text-muted mb-0.5"
        >
          {collapsed ? <ChevronRight size={10} /> : <ChevronDown size={10} />}
          <span>{collapsed ? `expand (${lineCount} lines)` : 'collapse'}</span>
        </button>
      )}
      {!collapsed && (
        <pre className="font-mono whitespace-pre-wrap break-all text-text-muted leading-4 text-[11px]">
          {display}
        </pre>
      )}
    </div>
  )
}
