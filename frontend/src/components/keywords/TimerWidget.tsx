import { useCallback, useEffect, useRef, useState } from 'react'
import { Pause, Play, RotateCcw } from 'lucide-react'
import { parseDuration, formatDuration } from '@/lib/keyword-detect'
import type { KeywordContext } from '@/modules/keyword-resolver'

interface TimerValue {
  duration: string
  label?: string
}

interface TimerWidgetProps {
  keyword: string
  value: unknown
  context: KeywordContext
}

export function TimerWidget({ value, context: _context }: TimerWidgetProps) {
  const raw = typeof value === 'string' ? value : (value as TimerValue)?.duration ?? '0s'
  const label = typeof value === 'object' && value !== null ? (value as TimerValue).label : undefined
  const totalSeconds = parseDuration(raw)

  const [remaining, setRemaining] = useState(totalSeconds)
  const [running, setRunning] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stop = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setRunning(false)
  }, [])

  const start = useCallback(() => {
    if (remaining <= 0) return
    setRunning(true)
    intervalRef.current = setInterval(() => {
      setRemaining((r) => {
        if (r <= 1) {
          stop()
          return 0
        }
        return r - 1
      })
    }, 1000)
  }, [remaining, stop])

  const reset = useCallback(() => {
    stop()
    setRemaining(totalSeconds)
  }, [stop, totalSeconds])

  useEffect(() => () => stop(), [stop])

  const pct = totalSeconds > 0 ? ((totalSeconds - remaining) / totalSeconds) * 100 : 0

  return (
    <div className="inline-flex items-center gap-2 px-3 py-2 rounded border border-border-bright bg-surface-el text-sm">
      {label && <span className="text-text-faint text-xs">{label}</span>}
      <div className="relative w-28 h-1.5 rounded-full bg-border-bright overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 bg-accent rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="font-mono text-xs text-text tabular-nums w-20 text-right">
        {formatDuration(remaining)}
      </span>
      <button
        onClick={running ? stop : start}
        disabled={remaining <= 0}
        className="p-1 rounded hover:bg-surface text-text-muted hover:text-accent transition-colors disabled:opacity-30"
      >
        {running ? <Pause size={12} /> : <Play size={12} />}
      </button>
      <button
        onClick={reset}
        className="p-1 rounded hover:bg-surface text-text-faint hover:text-text-muted transition-colors"
      >
        <RotateCcw size={12} />
      </button>
    </div>
  )
}
