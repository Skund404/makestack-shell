/**
 * TerminalPanel — interactive command input with execution history.
 *
 * Executes commands via POST /api/terminal/exec.
 * State (history) is preserved while the panel is mounted (hidden tabs preserve state).
 * Resize handle and height persistence live in Layout.tsx (BottomPanel).
 */
import { Trash2 } from 'lucide-react'
import { useTerminal } from '@/hooks/useTerminal'
import { TerminalLog } from './TerminalLog'
import { TerminalInput } from './TerminalInput'

interface TerminalPanelProps {
  /** Prefill value injected by DocsPanel "Run in terminal" (9E). */
  prefill?: string
  onPrefillConsumed?: () => void
}

export function TerminalPanel({ prefill, onPrefillConsumed }: TerminalPanelProps) {
  const { entries, exec, isLoading, clear, history } = useTerminal()

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-1 border-b border-border shrink-0">
        <span className="text-[10px] text-text-faint font-mono">terminal</span>
        <button
          onClick={clear}
          title="Clear history (⌘L)"
          className="text-text-faint hover:text-text transition-colors"
          aria-label="Clear terminal history"
        >
          <Trash2 size={11} />
        </button>
      </div>

      <TerminalLog entries={entries} />

      <TerminalInput
        onExec={exec}
        onClear={clear}
        isLoading={isLoading}
        history={history}
        prefill={prefill}
        onPrefillConsumed={onPrefillConsumed}
      />
    </div>
  )
}
