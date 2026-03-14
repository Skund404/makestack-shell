import { useEffect } from 'react'
import { useQueries } from '@tanstack/react-query'
import { Loader2, Package, Settings, Link as LinkIcon } from 'lucide-react'
import { Link } from '@tanstack/react-router'
import { apiGet } from '@/lib/api'
import { useWorkshopContext } from '@/context/WorkshopContext'
import { useWorkshop } from '@/hooks/use-workshops'
import { resolvePanel } from '@/modules/panel-registry'
import { UnknownPanel } from '@/components/modules/UnknownPanel'
// ---------------------------------------------------------------------------
// Types — mirrors /api/modules/{name}/views response
// ---------------------------------------------------------------------------

interface ModuleViewsResponse {
  views: Array<{ id: string; label: string; route: string; icon: string; sort_order: number }>
  panels: Array<{ id: string; label: string; size: 'full' | 'half' | 'third' }>
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
// Workshop home inner — renders panels grid for all active modules
// ---------------------------------------------------------------------------

function WorkshopHomeInner({ id }: { id: string }) {
  const { workshopModules, activeWorkshop, switchWorkshop } = useWorkshopContext()

  // If navigated directly to /workshop/$id (e.g. from a bookmark or sidebar link)
  // and this isn't the active workshop in context, switch to it.
  useEffect(() => {
    if (activeWorkshop?.id !== id) {
      switchWorkshop(id)
    }
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch panels for every active module in parallel.
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
        <span className="text-sm">Loading panels…</span>
      </div>
    )
  }

  // Collect all panels across all loaded modules.
  const panels: Array<{
    key: string
    panelId: string
    label: string
    size: 'full' | 'half' | 'third'
  }> = []

  workshopModules.forEach((moduleName, i) => {
    const data = moduleQueries[i]?.data
    if (!data) return
    for (const panel of data.panels) {
      panels.push({
        key: `${moduleName}.${panel.id}`,
        panelId: panel.id,
        label: panel.label,
        size: panel.size,
      })
    }
  })

  if (panels.length === 0) {
    return <EmptyState workshopId={id} />
  }

  return (
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
