/**
 * TerminalInput — command input bar.
 *
 * ↑/↓  navigate command history (from sessionStorage via useTerminal)
 * Tab   autocomplete from useDocsIndex commands cache
 * CLI/REST syntax hint via isRestSyntax() — label only, no translation
 * ⌘L    clear terminal (Ctrl+L)
 */
import { useState, useEffect, useRef } from 'react'
import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { isRestSyntax } from '@/lib/terminalUtils'
import { useDocsIndex } from '@/hooks/useDocsIndex'
import type { TerminalSyntax } from '@/lib/terminalTypes'

interface TerminalInputProps {
  onExec: (input: string, syntax: TerminalSyntax) => void
  onClear: () => void
  isLoading: boolean
  history: string[]
  /** Prefilled value — set externally by "Run in terminal" in DocsPanel (9E). */
  prefill?: string
  onPrefillConsumed?: () => void
}

export function TerminalInput({
  onExec,
  onClear,
  isLoading,
  history,
  prefill = '',
  onPrefillConsumed,
}: TerminalInputProps) {
  const [value, setValue] = useState('')
  const [historyIdx, setHistoryIdx] = useState(-1)
  const [suggestion, setSuggestion] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const { commands } = useDocsIndex()

  // Apply external prefill (e.g. from DocsPanel "Run in terminal").
  useEffect(() => {
    if (prefill) {
      setValue(prefill)
      setSuggestion('')
      inputRef.current?.focus()
      onPrefillConsumed?.()
    }
  }, [prefill, onPrefillConsumed])

  // Derive Tab autocomplete suggestion from the commands cache.
  useEffect(() => {
    if (!value.trim() || isRestSyntax(value)) {
      setSuggestion('')
      return
    }
    const lower = value.toLowerCase()
    const match = commands.find((c) => c.keyword.startsWith(lower) && c.keyword !== lower)
    setSuggestion(match ? match.keyword : '')
  }, [value, commands])

  const syntaxHint: TerminalSyntax = isRestSyntax(value) ? 'rest' : 'cli'

  const handleSubmit = () => {
    if (!value.trim() || isLoading) return
    onExec(value.trim(), syntaxHint)
    setHistoryIdx(-1)
    setValue('')
    setSuggestion('')
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSubmit()
    } else if (e.key === 'Tab') {
      e.preventDefault()
      if (suggestion) {
        setValue(suggestion)
        setSuggestion('')
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      const next = Math.min(historyIdx + 1, history.length - 1)
      setHistoryIdx(next)
      if (history[next] !== undefined) {
        setValue(history[next])
        setSuggestion('')
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      const next = Math.max(historyIdx - 1, -1)
      setHistoryIdx(next)
      setValue(next === -1 ? '' : (history[next] ?? ''))
      setSuggestion('')
    } else if ((e.ctrlKey || e.metaKey) && e.key === 'l') {
      e.preventDefault()
      onClear()
    }
  }

  return (
    <div className="flex items-center gap-2 px-3 py-2 border-t border-border bg-bg shrink-0">
      <span className="text-accent font-mono text-xs shrink-0 select-none">$</span>

      <div className="flex-1 relative">
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => { setValue(e.target.value); setHistoryIdx(-1) }}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          placeholder="status · GET /api/status"
          className={cn(
            'w-full bg-transparent border-none outline-none font-mono text-xs text-text',
            'placeholder:text-text-faint',
            isLoading && 'opacity-50 cursor-not-allowed',
          )}
          spellCheck={false}
          autoComplete="off"
          autoCapitalize="off"
        />
        {/* Tab autocomplete ghost text */}
        {suggestion && !isLoading && (
          <span className="absolute left-0 top-0 font-mono text-xs pointer-events-none">
            <span className="opacity-0">{value}</span>
            <span className="text-text-faint/40">{suggestion.slice(value.length)}</span>
            <span className="ml-1 text-[9px] text-text-faint/30 font-sans">Tab</span>
          </span>
        )}
      </div>

      {/* Syntax hint — isRestSyntax() used only for this label */}
      {value.trim() && (
        <span className="text-[10px] text-text-faint font-mono shrink-0 tabular-nums">
          {syntaxHint}
        </span>
      )}

      {isLoading ? (
        <Loader2 size={12} className="animate-spin text-text-faint shrink-0" />
      ) : (
        <button
          onClick={handleSubmit}
          disabled={!value.trim()}
          className="text-[10px] text-text-faint hover:text-text disabled:opacity-30 shrink-0 font-mono cursor-pointer"
          aria-label="Run command"
        >
          ↵
        </button>
      )}
    </div>
  )
}
