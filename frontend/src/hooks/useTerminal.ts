/**
 * useTerminal — executes commands via POST /api/terminal/exec.
 *
 * Backend returns command + request + response (or command + error) entries.
 * No client-side echo — the command entry comes from the backend.
 *
 * Ring buffer: 2000 entries (oldest dropped on overflow).
 * Command history: max 200, persisted to sessionStorage.
 */
import { useState, useCallback } from 'react'
import { useMutation } from '@tanstack/react-query'
import { apiPost } from '@/lib/api'
import type { TerminalEntry, ExecRequest, ExecResponse, TerminalSyntax } from '@/lib/terminalTypes'

const MAX_ENTRIES = 2000
const MAX_HISTORY = 200
const HISTORY_KEY = 'terminal-command-history'

function loadHistory(): string[] {
  try {
    const raw = sessionStorage.getItem(HISTORY_KEY)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    return []
  }
}

function saveHistory(history: string[]): void {
  try {
    sessionStorage.setItem(HISTORY_KEY, JSON.stringify(history))
  } catch {
    // sessionStorage unavailable — ignore.
  }
}

export interface TerminalHook {
  entries: TerminalEntry[]
  exec: (input: string, syntax?: TerminalSyntax) => void
  isLoading: boolean
  clear: () => void
  history: string[]
}

export function useTerminal(): TerminalHook {
  const [entries, setEntries] = useState<TerminalEntry[]>([])
  const [history, setHistory] = useState<string[]>(loadHistory)

  const appendEntries = (incoming: TerminalEntry[]) => {
    setEntries((prev) => {
      const next = [...prev, ...incoming]
      return next.length > MAX_ENTRIES ? next.slice(-MAX_ENTRIES) : next
    })
  }

  const mutation = useMutation({
    mutationFn: (req: ExecRequest) =>
      apiPost<ExecResponse>('/api/terminal/exec', req),
    onSuccess: (data) => appendEntries(data.entries),
    onError: (err) => {
      appendEntries([{
        type: 'error',
        timestamp: new Date().toISOString(),
        event: err instanceof Error ? err.message : 'Request failed',
        level: 'error',
        component: 'terminal',
      }])
    },
  })

  const exec = useCallback(
    (input: string, syntax: TerminalSyntax = 'auto') => {
      const trimmed = input.trim()
      if (!trimmed) return

      // Prepend to history (most recent first), cap at MAX_HISTORY.
      setHistory((prev) => {
        const next = [trimmed, ...prev.filter((h) => h !== trimmed)].slice(0, MAX_HISTORY)
        saveHistory(next)
        return next
      })

      mutation.mutate({ input: trimmed, syntax })
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [mutation.mutate],
  )

  const clear = useCallback(() => setEntries([]), [])

  return {
    entries,
    exec,
    isLoading: mutation.isPending,
    clear,
    history,
  }
}
