/**
 * DocsPanel — searchable docs popup (⌘K / ?).
 *
 * Three domains: API / Commands / Widgets.
 * Search is client-side — instant, no round trips.
 * Results ranked: exact keyword match > description match > other.
 * Max 20 results per domain.
 * ↑/↓ to move between results, Enter to run, Escape to close.
 * "Run in terminal" prefills TerminalInput and opens the terminal tab.
 */
import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { X, Search, Code2, Zap, Blocks } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useDocsIndex } from '@/hooks/useDocsIndex'
import { getAll } from '@/modules/keyword-resolver'
import { DocsApiEntry } from './DocsApiEntry'
import { DocsCommandEntry } from './DocsCommandEntry'
import { DocsWidgetEntry } from './DocsWidgetEntry'
import type { Capability, CliCommand } from '@/hooks/useDocsIndex'
import type { WidgetMeta } from '@/modules/keyword-resolver'

type Domain = 'api' | 'commands' | 'widgets'

const MAX_RESULTS = 20

// ---------------------------------------------------------------------------
// Ranking helpers
// ---------------------------------------------------------------------------

function rankScore(query: string, keyword: string, description: string): number {
  const q = query.toLowerCase()
  const kw = keyword.toLowerCase()
  const desc = description.toLowerCase()
  if (kw === q) return 3
  if (kw.startsWith(q)) return 2
  if (kw.includes(q)) return 1
  if (desc.includes(q)) return 0
  return -1
}

function filterApi(api: Capability[], q: string): Capability[] {
  if (!q) return api.slice(0, MAX_RESULTS)
  return api
    .map((e) => ({ e, score: rankScore(q, e.path, e.summary ?? '') }))
    .filter(({ score }) => score >= 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, MAX_RESULTS)
    .map(({ e }) => e)
}

function filterCommands(commands: CliCommand[], q: string): CliCommand[] {
  if (!q) return commands.slice(0, MAX_RESULTS)
  return commands
    .map((e) => ({ e, score: rankScore(q, e.keyword, e.description) }))
    .filter(({ score }) => score >= 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, MAX_RESULTS)
    .map(({ e }) => e)
}

function filterWidgets(widgets: WidgetMeta[], q: string): WidgetMeta[] {
  if (!q) return widgets.slice(0, MAX_RESULTS)
  return widgets
    .map((e) => ({ e, score: rankScore(q, e.keyword, e.description) }))
    .filter(({ score }) => score >= 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, MAX_RESULTS)
    .map(({ e }) => e)
}

// ---------------------------------------------------------------------------
// Section heading
// ---------------------------------------------------------------------------

function SectionHeading({ label, icon }: { label: string; icon: React.ReactNode }) {
  return (
    <div className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-semibold text-text-faint uppercase tracking-wider border-b border-border bg-surface/50 sticky top-0">
      {icon}
      {label}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Domain tabs
// ---------------------------------------------------------------------------

const DOMAIN_ICONS: Record<Domain, React.ReactNode> = {
  api:      <Code2 size={10} />,
  commands: <Zap size={10} />,
  widgets:  <Blocks size={10} />,
}

function DomainTab({ domain, active, count, onClick }: {
  domain: Domain; active: boolean; count: number; onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-sm transition-colors',
        active ? 'text-accent bg-surface-el' : 'text-text-faint hover:text-text',
      )}
    >
      {DOMAIN_ICONS[domain]}
      <span className="capitalize">{domain}</span>
      <span className="text-text-faint/60 font-mono">{count}</span>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Main DocsPanel
// ---------------------------------------------------------------------------

interface DocsPanelProps {
  open: boolean
  onClose: () => void
  onRunInTerminal: (input: string) => void
}

export function DocsPanel({ open, onClose, onRunInTerminal }: DocsPanelProps) {
  const [query, setQuery] = useState('')
  const [domain, setDomain] = useState<Domain>('api')
  const [selectedIdx, setSelectedIdx] = useState(0)
  const { api, commands, isLoading } = useDocsIndex()
  const widgets = useMemo(() => getAll(), [])
  const inputRef = useRef<HTMLInputElement>(null)

  const filteredApi      = useMemo(() => filterApi(api, query), [api, query])
  const filteredCommands = useMemo(() => filterCommands(commands, query), [commands, query])
  const filteredWidgets  = useMemo(() => filterWidgets(widgets, query), [widgets, query])

  const currentList = domain === 'api'
    ? filteredApi
    : domain === 'commands'
      ? filteredCommands
      : filteredWidgets

  // Reset selection when query or domain changes.
  useEffect(() => { setSelectedIdx(0) }, [query, domain])

  // Focus input when opened; clear query when closed.
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50)
    } else {
      setQuery('')
      setSelectedIdx(0)
    }
  }, [open])

  const handleRun = useCallback((input: string) => {
    onRunInTerminal(input)
    onClose()
  }, [onRunInTerminal, onClose])

  // Keyboard nav: Escape, ↑↓, Enter.
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { onClose(); return }
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIdx((i) => Math.min(i + 1, currentList.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIdx((i) => Math.max(i - 1, 0))
      } else if (e.key === 'Enter') {
        e.preventDefault()
        const item = currentList[selectedIdx]
        if (!item) return
        if (domain === 'api') {
          const a = item as Capability
          handleRun(`${a.method.toUpperCase()} ${a.path}`)
        } else if (domain === 'commands') {
          const c = item as CliCommand
          handleRun(c.accepts_arg ? `${c.keyword} <type>` : c.keyword)
        } else {
          const w = item as WidgetMeta
          handleRun(`{"${w.keyword}": "${w.accepts[0] ?? ''}"}`)
        }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, currentList, selectedIdx, domain, handleRun, onClose])

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      {/* Panel */}
      <div className="fixed inset-x-0 top-16 mx-auto z-50 w-full max-w-2xl flex flex-col rounded-lg border border-border bg-bg shadow-2xl overflow-hidden max-h-[70vh]">
        {/* Search header */}
        <div className="flex items-center gap-2 px-3 py-2 border-b border-border shrink-0">
          <Search size={13} className="text-text-faint shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search API, commands, widgets…"
            className="flex-1 bg-transparent text-sm text-text placeholder:text-text-faint outline-none"
          />
          {query && (
            <button onClick={() => setQuery('')} className="text-text-faint hover:text-text transition-colors">
              <X size={12} />
            </button>
          )}
          <button onClick={onClose} className="text-text-faint hover:text-text transition-colors ml-1" aria-label="Close docs">
            <X size={13} />
          </button>
        </div>

        {/* Domain tabs */}
        <div className="flex items-center gap-0.5 px-2 py-1 border-b border-border shrink-0">
          <DomainTab domain="api"      active={domain === 'api'}      count={filteredApi.length}      onClick={() => setDomain('api')} />
          <DomainTab domain="commands" active={domain === 'commands'} count={filteredCommands.length} onClick={() => setDomain('commands')} />
          <DomainTab domain="widgets"  active={domain === 'widgets'}  count={filteredWidgets.length}  onClick={() => setDomain('widgets')} />
        </div>

        {/* Results */}
        <div className="overflow-y-auto flex-1">
          {isLoading ? (
            <div className="flex items-center justify-center py-8 text-xs text-text-faint font-mono">Loading docs…</div>
          ) : (
            <>
              {domain === 'api' && (
                <>
                  <SectionHeading label={`API operations (${filteredApi.length})`} icon={<Code2 size={10} />} />
                  {filteredApi.length === 0
                    ? <EmptyState />
                    : filteredApi.map((e, i) => (
                        <DocsApiEntry key={`${e.method}:${e.path}`} entry={e} selected={i === selectedIdx} onRun={handleRun} />
                      ))
                  }
                </>
              )}
              {domain === 'commands' && (
                <>
                  <SectionHeading label={`CLI commands (${filteredCommands.length})`} icon={<Zap size={10} />} />
                  {filteredCommands.length === 0
                    ? <EmptyState />
                    : filteredCommands.map((e, i) => (
                        <DocsCommandEntry key={e.keyword} entry={e} selected={i === selectedIdx} onRun={handleRun} />
                      ))
                  }
                </>
              )}
              {domain === 'widgets' && (
                <>
                  <SectionHeading label={`Widgets (${filteredWidgets.length})`} icon={<Blocks size={10} />} />
                  {filteredWidgets.length === 0
                    ? <EmptyState />
                    : filteredWidgets.map((e, i) => (
                        <DocsWidgetEntry key={e.keyword} entry={e} selected={i === selectedIdx} onRun={handleRun} />
                      ))
                  }
                </>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-3 px-3 py-1.5 border-t border-border shrink-0 text-[10px] text-text-faint">
          <span><kbd className="font-mono">↑↓</kbd> navigate</span>
          <span><kbd className="font-mono">Enter</kbd> run</span>
          <span><kbd className="font-mono">Esc</kbd> close</span>
          <div className="flex-1" />
          <span><kbd className="font-mono">⌘K</kbd> / <kbd className="font-mono">?</kbd> to toggle</span>
        </div>
      </div>
    </>
  )
}

function EmptyState() {
  return <div className="py-6 text-center text-xs text-text-faint font-mono">No results</div>
}
