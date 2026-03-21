import { useEffect, useState } from 'react'
import { useQueries } from '@tanstack/react-query'
import { Loader2, Package, Settings, Link as LinkIcon, Plus } from 'lucide-react'
import { Link } from '@tanstack/react-router'
import { apiGet } from '@/lib/api'
import { useWorkshopContext } from '@/context/WorkshopContext'
import { useWorkshop } from '@/hooks/use-workshops'
import { resolvePanel } from '@/modules/panel-registry'
import { UnknownPanel } from '@/components/modules/UnknownPanel'
import { AddAppDialog } from '@/components/workshops/AddAppDialog'

// ---------------------------------------------------------------------------
// Types — mirrors /api/modules/{name}/views response
// ---------------------------------------------------------------------------

interface ModuleViewsResponse {
  views: Array<{ id: string; label: string; route: string; icon: string; sort_order: number }>
  panels: Array<{ id: string; label: string; size: 'full' | 'half' | 'third' }>
  app_mode?: {
    enabled: boolean
    title: string
    subtitle: string
    home_route: string
    theme?: { accent?: string; sidebar_bg?: string } | null
  }
}

// ---------------------------------------------------------------------------
// Panel size → Tailwind col-span class
// ---------------------------------------------------------------------------

const SIZE_COLS: Record<'full' | 'half' | 'third', string> = {
  full:  'col-span-12',
  half:  'col-span-12 md:col-span-6',
  third: 'col-span-12 md:col-span-4',
}

// ---------------------------------------------------------------------------
// Empty state — shown when no modules are associated
// ---------------------------------------------------------------------------

function EmptyState({ workshopId }: { workshopId: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4 text-text-faint">
      <Package size={32} className="opacity-30" />
      <div className="text-center">
        <p className="text-sm font-medium text-text-muted mb-1">No modules active</p>
        <p className="text-xs max-w-xs text-center">
          Add modules to this workshop to see their panels here.
        </p>
      </div>
      <Link
        to="/workshop/$id/settings"
        params={{ id: workshopId }}
        className="text-xs text-accent hover:underline flex items-center gap-1"
      >
        <LinkIcon size={11} />
        Add modules in settings
      </Link>
    </div>
  )
}

// ---------------------------------------------------------------------------
// App launcher card — clickable card that navigates to module's app mode
// ---------------------------------------------------------------------------

function AppLauncherCard({
  moduleName,
  title,
  subtitle,
  homeRoute,
  accent,
  workshopId,
  workshopName,
}: {
  moduleName: string
  title: string
  subtitle: string
  homeRoute: string
  accent?: string
  workshopId: string
  workshopName: string
}) {
  const handleClick = () => {
    // Store workshop context for the back link in app mode
    try {
      sessionStorage.setItem('app-mode-workshop-id', workshopId)
      sessionStorage.setItem('app-mode-workshop-name', workshopName)
    } catch { /* ignore */ }
    window.location.href = homeRoute
  }

  return (
    <button
      onClick={handleClick}
      className="flex flex-col items-start p-4 rounded-lg border border-border bg-surface hover:bg-surface-el transition-colors text-left cursor-pointer min-w-[140px]"
      style={{ borderLeftColor: accent || 'var(--accent)', borderLeftWidth: 3 }}
    >
      <span className="text-sm font-semibold text-text">{title || moduleName}</span>
      {subtitle && <span className="text-[10px] text-text-faint mt-0.5">{subtitle}</span>}
    </button>
  )
}

function AddAppCard({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex flex-col items-center justify-center p-4 rounded-lg border border-dashed border-border hover:border-accent/40 hover:bg-accent/5 transition-colors cursor-pointer min-w-[140px] min-h-[72px]"
    >
      <Plus size={16} className="text-text-faint mb-1" />
      <span className="text-[10px] text-text-faint">Add app</span>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Single panel slot — resolves panelId, renders component or fallback
// ---------------------------------------------------------------------------

function PanelSlot({
  panelId,
  label,
  size,
  workshopId,
}: {
  panelId: string
  label: string
  size: 'full' | 'half' | 'third'
  workshopId: string
}) {
  const Resolved = resolvePanel(panelId)

  return (
    <div className={SIZE_COLS[size]}>
      <div className="rounded border border-border bg-surface overflow-hidden h-full">
        <div className="px-3 py-2 border-b border-border/50">
          <p className="text-xs font-medium text-text-muted">{label}</p>
        </div>
        <div className="p-3">
          {Resolved ? (
            <Resolved workshopId={workshopId} panelId={panelId} />
          ) : (
            <UnknownPanel panelId={panelId} />
          )}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Workshop home inner — launcher cards + panels grid
// ---------------------------------------------------------------------------

function WorkshopHomeInner({ id }: { id: string }) {
  const { workshopModules, activeWorkshop, switchWorkshop } = useWorkshopContext()
  const [addAppOpen, setAddAppOpen] = useState(false)

  // If navigated directly to /workshop/$id (e.g. from a bookmark or sidebar link)
  // and this isn't the active workshop in context, switch to it.
  useEffect(() => {
    if (activeWorkshop?.id !== id) {
      switchWorkshop(id)
    }
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch panels + app_mode for every active module in parallel.
  const moduleQueries = useQueries({
    queries: workshopModules.map((name) => ({
      queryKey: ['module-views', name] as const,
      queryFn: () => apiGet<ModuleViewsResponse>(`/api/modules/${name}/views`),
      staleTime: 60_000,
    })),
  })

  const isLoading = moduleQueries.some((q) => q.isLoading)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20 gap-2 text-text-muted">
        <Loader2 size={14} className="animate-spin" />
        <span className="text-sm">Loading panels...</span>
      </div>
    )
  }

  // Collect app launcher cards and panels
  const appCards: Array<{
    key: string
    moduleName: string
    title: string
    subtitle: string
    homeRoute: string
    accent?: string
  }> = []

  const panels: Array<{
    key: string
    panelId: string
    label: string
    size: 'full' | 'half' | 'third'
  }> = []

  workshopModules.forEach((moduleName, i) => {
    const data = moduleQueries[i]?.data
    if (!data) return

    // App mode launcher card
    if (data.app_mode?.enabled) {
      appCards.push({
        key: moduleName,
        moduleName,
        title: data.app_mode.title,
        subtitle: data.app_mode.subtitle,
        homeRoute: data.app_mode.home_route,
        accent: data.app_mode.theme?.accent,
      })
    }

    // Dashboard panels
    for (const panel of data.panels) {
      panels.push({
        key: `${moduleName}.${panel.id}`,
        panelId: panel.id,
        label: panel.label,
        size: panel.size,
      })
    }
  })

  if (appCards.length === 0 && panels.length === 0) {
    return (
      <>
        <EmptyState workshopId={id} />
        <AddAppDialog
          open={addAppOpen}
          onOpenChange={setAddAppOpen}
          workshopId={id}
          existingModules={workshopModules}
        />
      </>
    )
  }

  return (
    <>
      {/* App launcher cards */}
      {(appCards.length > 0 || true) && (
        <div className="mb-6">
          <p className="text-[10px] font-semibold text-text-faint uppercase tracking-widest mb-2">Apps</p>
          <div className="flex flex-wrap gap-3">
            {appCards.map((card) => (
              <AppLauncherCard
                key={card.key}
                moduleName={card.moduleName}
                title={card.title}
                subtitle={card.subtitle}
                homeRoute={card.homeRoute}
                accent={card.accent}
                workshopId={id}
                workshopName={activeWorkshop?.name ?? 'Workshop'}
              />
            ))}
            <AddAppCard onClick={() => setAddAppOpen(true)} />
          </div>
        </div>
      )}

      {/* Dashboard panels */}
      {panels.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold text-text-faint uppercase tracking-widest mb-2">Dashboard</p>
          <div className="grid grid-cols-12 gap-4">
            {panels.map((p) => (
              <PanelSlot
                key={p.key}
                panelId={p.panelId}
                label={p.label}
                size={p.size}
                workshopId={id}
              />
            ))}
          </div>
        </div>
      )}

      <AddAppDialog
        open={addAppOpen}
        onOpenChange={setAddAppOpen}
        workshopId={id}
        existingModules={workshopModules}
      />
    </>
  )
}

// ---------------------------------------------------------------------------
// Workshop home header
// ---------------------------------------------------------------------------

function WorkshopHomeHeader({ id }: { id: string }) {
  const { data: ws } = useWorkshop(id)
  if (!ws) return null

  return (
    <div className="flex items-center gap-2 mb-6">
      {ws.icon && <span className="text-xl">{ws.icon}</span>}
      <h1 className="text-lg font-semibold text-text flex-1">{ws.name}</h1>
      <Link
        to="/workshop/$id/settings"
        params={{ id }}
        className="text-text-faint hover:text-text transition-colors p-1 rounded"
        title="Workshop settings"
      >
        <Settings size={14} />
      </Link>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Exported page component
// ---------------------------------------------------------------------------

export function WorkshopHome({ id }: { id: string }) {
  if (!id) {
    return (
      <div className="p-4 text-sm text-text-faint">No workshop ID specified.</div>
    )
  }

  return (
    <div className="p-4 overflow-y-auto">
      <WorkshopHomeHeader id={id} />
      <WorkshopHomeInner id={id} />
    </div>
  )
}
