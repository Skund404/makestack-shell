import { useState, useEffect, useCallback, useRef } from 'react'
import { Outlet } from '@tanstack/react-router'
import { X, Terminal, ScrollText } from 'lucide-react'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { useSystemStatus } from '@/hooks/use-status'
import { WorkshopContextProvider } from '@/context/WorkshopContext'
import { TerminalPanel } from '@/components/terminal/TerminalPanel'
import { LogPanel } from '@/components/terminal/LogPanel'
import { DocsPanel } from '@/components/terminal/DocsPanel'
import { cn } from '@/lib/utils'

/**
 * Dismissable banner shown when Core is not reachable.
 */
function StaleBanner() {
  const { data: status } = useSystemStatus()
  const [dismissed, setDismissed] = useState(false)

  if (!status || status.core_connected || dismissed) return null

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-yellow-500/10 border-b border-yellow-500/30 text-yellow-600 dark:text-yellow-400 text-xs">
      <span className="w-1.5 h-1.5 rounded-full bg-yellow-500 shrink-0" />
      <span className="flex-1">
        Catalogue data may be outdated — Core is not connected.
        Inventory and workshops are fully functional.
        Catalogue writes are disabled until Core reconnects.
      </span>
      <button
        onClick={() => setDismissed(true)}
        className="shrink-0 text-yellow-600/70 hover:text-yellow-600 transition-colors"
        aria-label="Dismiss"
      >
        <X size={13} />
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Bottom panel — Terminal + Log stream with drag-to-resize
// ---------------------------------------------------------------------------

const PANEL_HEIGHT_DEFAULT = 240
const PANEL_HEIGHT_MIN = 120
const PANEL_HEIGHT_MAX_VH = 0.6
const SS_HEIGHT = 'terminal-panel-height'
const SS_OPEN = 'terminal-panel-open'
const SS_TAB = 'terminal-panel-tab'

type PanelTab = 'terminal' | 'log'

function loadPanelHeight(): number {
  try {
    const v = sessionStorage.getItem(SS_HEIGHT)
    return v ? Math.max(PANEL_HEIGHT_MIN, parseInt(v, 10)) : PANEL_HEIGHT_DEFAULT
  } catch { return PANEL_HEIGHT_DEFAULT }
}

function saveSS(key: string, value: string) {
  try { sessionStorage.setItem(key, value) } catch { /* ignore */ }
}

interface BottomPanelProps {
  open: boolean
  activeTab: PanelTab
  onTabClick: (tab: PanelTab) => void
  onClose: () => void
  terminalPrefill: string
  onPrefillConsumed: () => void
}

function BottomPanel({
  open,
  activeTab,
  onTabClick,
  onClose,
  terminalPrefill,
  onPrefillConsumed,
}: BottomPanelProps) {
  const [panelHeight, setPanelHeight] = useState(loadPanelHeight)
  const draggingRef = useRef(false)

  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault()
    draggingRef.current = true
    const startY = e.clientY
    const startH = panelHeight

    const onMove = (ev: MouseEvent) => {
      if (!draggingRef.current) return
      const delta = startY - ev.clientY
      const maxH = window.innerHeight * PANEL_HEIGHT_MAX_VH
      const next = Math.max(PANEL_HEIGHT_MIN, Math.min(maxH, startH + delta))
      setPanelHeight(next)
      saveSS(SS_HEIGHT, String(Math.round(next)))
    }
    const onUp = () => {
      draggingRef.current = false
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  return (
    <div className="border-t border-border bg-bg shrink-0">
      {/* Drag handle — only shown when panel is open */}
      {open && (
        <div
          onMouseDown={handleDragStart}
          className="h-1 w-full cursor-ns-resize hover:bg-accent/20 transition-colors"
          title="Drag to resize"
        />
      )}

      {/* Tab bar — always visible */}
      <div className="flex items-center h-7 px-1 gap-0.5">
        <TabButton
          icon={<Terminal size={10} />}
          label="Terminal"
          active={open && activeTab === 'terminal'}
          onClick={() => onTabClick('terminal')}
        />
        <TabButton
          icon={<ScrollText size={10} />}
          label="Log"
          active={open && activeTab === 'log'}
          onClick={() => onTabClick('log')}
        />
        <div className="flex-1" />
        {open && (
          <button
            onClick={onClose}
            title="Close panel"
            className="text-text-faint hover:text-text transition-colors p-1 rounded"
            aria-label="Close panel"
          >
            <X size={11} />
          </button>
        )}
      </div>

      {/* Panel content — hidden (not unmounted) on inactive tab */}
      {open && (
        <div style={{ height: panelHeight }} className="flex flex-col">
          <div className={cn('flex-1 flex flex-col min-h-0', activeTab !== 'terminal' && 'hidden')}>
            <TerminalPanel
              prefill={terminalPrefill}
              onPrefillConsumed={onPrefillConsumed}
            />
          </div>
          <div className={cn('flex-1 flex flex-col min-h-0', activeTab !== 'log' && 'hidden')}>
            <LogPanel />
          </div>
        </div>
      )}
    </div>
  )
}

interface TabButtonProps {
  icon: React.ReactNode
  label: string
  active: boolean
  onClick: () => void
}

function TabButton({ icon, label, active, onClick }: TabButtonProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-1 px-2 h-7 text-[10px] font-medium',
        'transition-colors rounded-sm cursor-pointer',
        active ? 'text-accent' : 'text-text-faint hover:text-text-muted',
      )}
      aria-pressed={active}
    >
      {icon}
      <span>{label}</span>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Root layout
// ---------------------------------------------------------------------------

export function Layout() {
  const [panelOpen, setPanelOpen] = useState(
    () => { try { return sessionStorage.getItem(SS_OPEN) === 'true' } catch { return false } }
  )
  const [activeTab, setActiveTab] = useState<PanelTab>(
    () => { try { return (sessionStorage.getItem(SS_TAB) as PanelTab) ?? 'terminal' } catch { return 'terminal' } }
  )
  const [terminalPrefill, setTerminalPrefill] = useState('')
  const [docsOpen, setDocsOpen] = useState(false)

  const setPanel = useCallback((open: boolean, tab?: PanelTab) => {
    setPanelOpen(open)
    saveSS(SS_OPEN, String(open))
    if (tab) {
      setActiveTab(tab)
      saveSS(SS_TAB, tab)
    }
  }, [])

  // Ctrl+` toggles the bottom panel.
  // ⌘K opens docs panel.
  // ? opens docs panel when not in any input field.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === '`' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault()
        setPanelOpen((v) => { saveSS(SS_OPEN, String(!v)); return !v })
        return
      }
      if (e.key === 'k' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault()
        setDocsOpen((v) => !v)
        return
      }
      // ? only when NOT focused in any input/textarea
      if (
        e.key === '?' &&
        !e.ctrlKey &&
        !e.metaKey &&
        !(document.activeElement instanceof HTMLInputElement) &&
        !(document.activeElement instanceof HTMLTextAreaElement)
      ) {
        e.preventDefault()
        setDocsOpen((v) => !v)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  // Listen for sidebar/DocsPanelFull "open-panel" custom events.
  useEffect(() => {
    const handler = (e: Event) => {
      const { tab } = (e as CustomEvent<{ tab: PanelTab }>).detail
      setPanel(true, tab)
    }
    window.addEventListener('open-panel', handler)
    return () => window.removeEventListener('open-panel', handler)
  }, [setPanel])

  // Listen for terminal-prefill custom event (from DocsPanelFull "Run in terminal").
  useEffect(() => {
    const handler = (e: Event) => {
      const { input } = (e as CustomEvent<{ input: string }>).detail
      setTerminalPrefill(input)
    }
    window.addEventListener('terminal-prefill', handler)
    return () => window.removeEventListener('terminal-prefill', handler)
  }, [])

  const handleTabClick = (tab: PanelTab) => {
    if (panelOpen && activeTab === tab) {
      setPanel(false)
    } else {
      setPanel(true, tab)
    }
  }

  // Called by DocsPanel "Run in terminal" — opens terminal tab with prefill.
  const handleRunInTerminal = useCallback((input: string) => {
    setTerminalPrefill(input)
    setPanel(true, 'terminal')
  }, [setPanel])

  return (
    <WorkshopContextProvider>
      <div className="flex h-screen overflow-hidden bg-bg font-sans">
        <Sidebar />
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
          <Header />
          <StaleBanner />
          <main className="flex-1 min-h-0 overflow-y-auto">
            <Outlet />
          </main>
          <BottomPanel
            open={panelOpen}
            activeTab={activeTab}
            onTabClick={handleTabClick}
            onClose={() => setPanel(false)}
            terminalPrefill={terminalPrefill}
            onPrefillConsumed={() => setTerminalPrefill('')}
          />
        </div>
      </div>
      <DocsPanel
        open={docsOpen}
        onClose={() => setDocsOpen(false)}
        onRunInTerminal={handleRunInTerminal}
      />
    </WorkshopContextProvider>
  )
}
