/**
 * DocsPanelFull — full-page docs view at /dev/docs.
 *
 * Same three domains (API / Commands / Widgets) laid out as a full page
 * with a sidebar nav for domain switching.
 */
import { useState, useMemo } from 'react'
import { BookOpen, Code2, Zap, Blocks } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useDocsIndex } from '@/hooks/useDocsIndex'
import { getAll } from '@/modules/keyword-resolver'
import { DocsApiEntry } from './DocsApiEntry'
import { DocsCommandEntry } from './DocsCommandEntry'
import { DocsWidgetEntry } from './DocsWidgetEntry'

type Domain = 'api' | 'commands' | 'widgets'

const DOMAIN_ICONS: Record<Domain, React.ReactNode> = {
  api:      <Code2 size={14} />,
  commands: <Zap size={14} />,
  widgets:  <Blocks size={14} />,
}

function openTerminalWith(input: string) {
  window.dispatchEvent(new CustomEvent('open-panel', { detail: { tab: 'terminal' } }))
  // Small delay to let Layout open before injecting prefill via custom event.
  setTimeout(() => {
    window.dispatchEvent(new CustomEvent('terminal-prefill', { detail: { input } }))
  }, 50)
}

export function DocsPanelFull() {
  const [domain, setDomain] = useState<Domain>('api')
  const { api, commands, isLoading } = useDocsIndex()
  const widgets = useMemo(() => getAll(), [])

  return (
    <div className="flex h-full">
      {/* Sidebar nav */}
      <aside className="w-44 shrink-0 border-r border-border bg-bg-secondary p-3 space-y-1">
        <div className="flex items-center gap-2 mb-3">
          <BookOpen size={14} className="text-accent" />
          <span className="text-sm font-semibold text-text">Docs</span>
        </div>
        {(['api', 'commands', 'widgets'] as Domain[]).map((d) => (
          <button
            key={d}
            onClick={() => setDomain(d)}
            className={cn(
              'flex items-center gap-2 w-full px-2 py-1.5 rounded text-xs transition-colors',
              domain === d
                ? 'bg-accent/10 text-accent border border-accent/20'
                : 'text-text-muted hover:bg-surface-el hover:text-text',
            )}
          >
            {DOMAIN_ICONS[d]}
            <span className="capitalize">{d}</span>
          </button>
        ))}
      </aside>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-16 text-xs text-text-faint font-mono">
            Loading docs…
          </div>
        ) : (
          <div className="divide-y divide-border">
            {domain === 'api' && api.map((e) => (
              <DocsApiEntry
                key={`${e.method}:${e.path}`}
                entry={e}
                selected={false}
                onRun={openTerminalWith}
              />
            ))}
            {domain === 'commands' && commands.map((e) => (
              <DocsCommandEntry
                key={e.keyword}
                entry={e}
                selected={false}
                onRun={openTerminalWith}
              />
            ))}
            {domain === 'widgets' && widgets.map((e) => (
              <DocsWidgetEntry
                key={e.keyword}
                entry={e}
                selected={false}
                onRun={openTerminalWith}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
