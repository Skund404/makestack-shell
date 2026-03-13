import { ChevronDown, Search } from 'lucide-react'
import { useNavigate, useRouterState } from '@tanstack/react-router'
import { useState, useRef } from 'react'
import { useWorkshopList } from '@/hooks/use-workshops'
import { useSystemStatus } from '@/hooks/use-status'
import { useWorkshopContext } from '@/context/WorkshopContext'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from '@/components/ui/DropdownMenu'

function Breadcrumb() {
  const loc = useRouterState({ select: (s) => s.location })
  const parts = loc.pathname.split('/').filter(Boolean)

  if (parts.length === 0) return <span className="text-sm text-text-muted">Home</span>

  return (
    <nav className="flex items-center gap-1 text-sm text-text-muted">
      {parts.map((part, i) => (
        <span key={i} className="flex items-center gap-1">
          {i > 0 && <span className="text-text-faint">/</span>}
          <span className={i === parts.length - 1 ? 'text-text capitalize' : 'capitalize'}>
            {part}
          </span>
        </span>
      ))}
    </nav>
  )
}

function WorkshopSwitcher() {
  const { data: workshops } = useWorkshopList()
  const { activeWorkshop, switchWorkshop } = useWorkshopContext()

  const activeLabel = activeWorkshop?.name ?? 'All'

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center gap-1.5 text-xs text-text-faint px-2 py-1 rounded bg-surface border border-border hover:border-border-bright hover:text-text transition-colors">
          {activeLabel}
          <ChevronDown size={11} />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Workshop context</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => switchWorkshop(null)}>
          <span className={!activeWorkshop ? 'text-accent' : undefined}>All</span>
        </DropdownMenuItem>
        {(workshops?.items ?? []).map((ws) => (
          <DropdownMenuItem
            key={ws.id}
            onSelect={() => switchWorkshop(ws.id)}
          >
            <span className={activeWorkshop?.id === ws.id ? 'text-accent' : undefined}>
              {ws.name}
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/**
 * Shows Core connection state as a coloured dot with a label.
 *
 * Green  "Connected"    — Core is reachable right now
 * Yellow "Reconnecting" — Core was reachable this session but is now down
 * Red    "Disconnected" — Core has never been reachable this session
 */
function CoreConnectionIndicator() {
  const { data: status, isLoading } = useSystemStatus()
  // Track whether core was ever connected in this browser session.
  const everConnected = useRef(false)

  if (isLoading || !status) return null

  if (status.core_connected) {
    everConnected.current = true
  }

  let dotColor: string
  let label: string
  let title: string

  if (status.core_connected) {
    dotColor = 'bg-green-500'
    label = 'Connected'
    title = `Core connected at ${status.core_url}`
  } else if (everConnected.current) {
    dotColor = 'bg-yellow-400 animate-pulse'
    label = 'Reconnecting'
    title = `Core disconnected — was at ${status.core_url}`
  } else {
    dotColor = 'bg-red-500'
    label = 'Disconnected'
    title = `Core unreachable at ${status.core_url}`
  }

  return (
    <div
      className="flex items-center gap-1.5 text-xs text-text-faint select-none"
      title={title}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
      <span>{label}</span>
    </div>
  )
}

export function Header() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      void navigate({ to: '/catalogue/search', search: { q: query.trim() } })
      setQuery('')
    }
  }

  return (
    <header className="h-11 shrink-0 border-b border-border bg-bg-secondary flex items-center px-4 gap-4">
      <Breadcrumb />
      <div className="flex-1" />
      <CoreConnectionIndicator />
      <form onSubmit={handleSearch} className="relative">
        <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-faint pointer-events-none" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search catalogue…"
          className="h-7 pl-7 pr-3 rounded border bg-surface border-border-bright text-xs text-text placeholder:text-text-faint focus:outline-none focus:border-accent/40 w-52 transition-colors"
        />
      </form>
      <WorkshopSwitcher />
    </header>
  )
}
