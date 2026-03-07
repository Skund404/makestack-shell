import { useState } from 'react'
import { Outlet } from '@tanstack/react-router'
import { X } from 'lucide-react'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { useSystemStatus } from '@/hooks/use-status'

/**
 * Dismissable banner shown when Core is not reachable.
 * Catalogue data shown while Core is down may be stale (served from cache).
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

export function Layout() {
  return (
    <div className="flex h-screen overflow-hidden bg-bg font-sans">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <Header />
        <StaleBanner />
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
