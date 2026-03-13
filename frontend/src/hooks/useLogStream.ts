/**
 * useLogStream — subscribes to GET /api/terminal/stream (SSE).
 *
 * All structlog events are received; heartbeats are silently dropped.
 * Ring buffer: 2000 entries (oldest dropped on overflow).
 * Reconnects automatically with exponential backoff (max 30s).
 */
import { useState, useEffect, useRef } from 'react'
import type { TerminalEntry } from '@/lib/terminalTypes'

const MAX_ENTRIES = 2000
const BACKOFF_INITIAL_MS = 1_000
const BACKOFF_MAX_MS = 30_000

export interface LogStreamHook {
  entries: TerminalEntry[]
  isConnected: boolean
  clear: () => void
}

export function useLogStream(): LogStreamHook {
  const [entries, setEntries] = useState<TerminalEntry[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const backoffRef = useRef(BACKOFF_INITIAL_MS)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    let unmounted = false

    function connect() {
      if (unmounted) return
      const es = new EventSource('/api/terminal/stream')
      esRef.current = es

      es.onopen = () => {
        if (unmounted) return
        setIsConnected(true)
        backoffRef.current = BACKOFF_INITIAL_MS // reset on successful connection
      }

      es.onmessage = (event: MessageEvent<string>) => {
        if (unmounted) return
        try {
          const entry = JSON.parse(event.data) as TerminalEntry
          if (entry.type === 'heartbeat') return
          setEntries((prev) => {
            const next = [...prev, entry]
            return next.length > MAX_ENTRIES ? next.slice(-MAX_ENTRIES) : next
          })
        } catch {
          // Ignore malformed SSE payloads.
        }
      }

      es.onerror = () => {
        if (unmounted) return
        setIsConnected(false)
        es.close()
        esRef.current = null
        // Exponential backoff reconnect.
        const delay = backoffRef.current
        backoffRef.current = Math.min(delay * 2, BACKOFF_MAX_MS)
        timerRef.current = setTimeout(connect, delay)
      }
    }

    connect()

    return () => {
      unmounted = true
      if (timerRef.current) clearTimeout(timerRef.current)
      esRef.current?.close()
      setIsConnected(false)
    }
  }, [])

  const clear = () => setEntries([])

  return { entries, isConnected, clear }
}
