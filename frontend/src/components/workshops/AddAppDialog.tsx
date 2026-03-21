/**
 * AddAppDialog — streamlined flow for adding module apps to a workshop.
 *
 * Two tabs:
 *   Available — installed modules not yet in this workshop (one-click add)
 *   Browse — search registries, preview dependencies, install & assign
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Plus, Check, AlertTriangle, Package } from 'lucide-react'
import { Dialog } from '@/components/ui/Dialog'
import { apiGet, apiPost } from '@/lib/api'
import { cn } from '@/lib/utils'

interface AddAppDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  workshopId: string
  /** Module names already associated with this workshop. */
  existingModules: string[]
}

interface InstalledModuleRow {
  name: string
  version: string
  enabled: boolean
  manifest: Record<string, unknown> | null
}

interface SearchResult {
  name: string
  type: string
  description: string | null
  git_url: string | null
  registry: string
}

interface PreviewResult {
  module: { name: string; type: string; version?: string; description?: string }
  already_installed: boolean
  dependencies: Array<{ name: string; type: string; already_installed: boolean }>
  warnings: string[]
}

type Tab = 'available' | 'browse'

export function AddAppDialog({ open, onOpenChange, workshopId, existingModules }: AddAppDialogProps) {
  const [activeTab, setActiveTab] = useState<Tab>('available')
  const qc = useQueryClient()

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Add App" className="max-w-md">
      <div className="px-4 pt-2 pb-1 flex gap-1">
        <TabPill label="Available" active={activeTab === 'available'} onClick={() => setActiveTab('available')} />
        <TabPill label="Browse" active={activeTab === 'browse'} onClick={() => setActiveTab('browse')} />
      </div>
      <div className="min-h-[280px] max-h-[400px] overflow-y-auto">
        {activeTab === 'available' ? (
          <AvailableTab workshopId={workshopId} existingModules={existingModules} onDone={() => { qc.invalidateQueries({ queryKey: ['workshop-modules'] }); onOpenChange(false) }} />
        ) : (
          <BrowseTab workshopId={workshopId} onDone={() => { qc.invalidateQueries({ queryKey: ['workshop-modules'] }); onOpenChange(false) }} />
        )}
      </div>
    </Dialog>
  )
}

function TabPill({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'px-3 py-1 text-xs rounded-full transition-colors',
        active
          ? 'bg-accent/10 text-accent font-medium'
          : 'text-text-muted hover:bg-surface-el',
      )}
    >
      {label}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Available tab — installed modules not yet in this workshop
// ---------------------------------------------------------------------------

function AvailableTab({
  workshopId,
  existingModules,
  onDone,
}: {
  workshopId: string
  existingModules: string[]
  onDone: () => void
}) {
  const { data, isLoading } = useQuery({
    queryKey: ['modules-list'],
    queryFn: () => apiGet<{ items: InstalledModuleRow[] }>('/api/modules'),
    staleTime: 30_000,
  })

  const addMutation = useMutation({
    mutationFn: (moduleName: string) =>
      apiPost(`/api/workshops/${workshopId}/modules`, { module_name: moduleName, sort_order: 0 }),
    onSuccess: () => onDone(),
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-text-muted gap-2">
        <Loader2 size={14} className="animate-spin" />
        <span className="text-xs">Loading modules...</span>
      </div>
    )
  }

  const existing = new Set(existingModules)
  const available = (data?.items ?? []).filter(
    (m) => m.enabled && !existing.has(m.name),
  )

  if (available.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-text-faint gap-2">
        <Package size={20} className="opacity-30" />
        <p className="text-xs">All installed modules are already in this workshop.</p>
        <p className="text-xs text-text-faint">Switch to Browse to find new apps.</p>
      </div>
    )
  }

  return (
    <div className="px-4 py-2 space-y-1">
      {available.map((mod) => {
        const displayName = (mod.manifest as Record<string, unknown>)?.display_name as string | undefined
        return (
          <div
            key={mod.name}
            className="flex items-center gap-3 px-3 py-2.5 rounded-md hover:bg-surface-el transition-colors"
          >
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-text truncate">{displayName ?? mod.name}</p>
              <p className="text-[10px] text-text-faint truncate">{mod.name} v{mod.version}</p>
            </div>
            <button
              onClick={() => addMutation.mutate(mod.name)}
              disabled={addMutation.isPending}
              className="shrink-0 flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium rounded bg-accent/10 text-accent hover:bg-accent/20 transition-colors disabled:opacity-50"
            >
              <Plus size={10} />
              Add
            </button>
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Browse tab — search registries, preview, install & assign
// ---------------------------------------------------------------------------

function BrowseTab({ workshopId, onDone }: { workshopId: string; onDone: () => void }) {
  const [query, setQuery] = useState('')
  const [selectedPkg, setSelectedPkg] = useState<string | null>(null)

  const { data: registries } = useQuery({
    queryKey: ['registries'],
    queryFn: () => apiGet<{ items: Array<{ name: string }> }>('/api/registries'),
    staleTime: 60_000,
  })

  const hasRegistries = (registries?.items ?? []).length > 0

  if (!hasRegistries) {
    return <NoRegistriesState />
  }

  if (selectedPkg) {
    return (
      <InstallPreview
        packageName={selectedPkg}
        workshopId={workshopId}
        onBack={() => setSelectedPkg(null)}
        onDone={onDone}
      />
    )
  }

  return (
    <div>
      <div className="px-4 py-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search packages..."
          className="w-full px-3 py-1.5 text-xs rounded border border-border bg-surface text-text placeholder:text-text-faint focus:outline-none focus:border-accent/50"
          autoFocus
        />
      </div>
      <SearchResults query={query} onSelect={setSelectedPkg} />
    </div>
  )
}

function SearchResults({ query, onSelect }: { query: string; onSelect: (name: string) => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ['package-search', query],
    queryFn: () => apiGet<{ items: SearchResult[] }>('/api/packages/search', { q: query }),
    staleTime: 30_000,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-text-muted gap-2">
        <Loader2 size={14} className="animate-spin" />
        <span className="text-xs">Searching...</span>
      </div>
    )
  }

  const items = (data?.items ?? []).filter((i) => i.type === 'module')

  if (items.length === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-text-faint">
        <p className="text-xs">{query ? 'No modules found.' : 'Type to search for modules.'}</p>
      </div>
    )
  }

  return (
    <div className="px-4 py-1 space-y-1">
      {items.map((item) => (
        <button
          key={item.name}
          onClick={() => onSelect(item.name)}
          className="flex items-start gap-3 px-3 py-2.5 rounded-md hover:bg-surface-el transition-colors w-full text-left"
        >
          <Package size={14} className="shrink-0 mt-0.5 text-text-muted" />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-text">{item.name}</p>
            {item.description && (
              <p className="text-[10px] text-text-faint truncate">{item.description}</p>
            )}
          </div>
        </button>
      ))}
    </div>
  )
}

function InstallPreview({
  packageName,
  workshopId,
  onBack,
  onDone,
}: {
  packageName: string
  workshopId: string
  onBack: () => void
  onDone: () => void
}) {
  const { data, isLoading } = useQuery({
    queryKey: ['package-preview', packageName],
    queryFn: () => apiGet<PreviewResult>(`/api/packages/${packageName}/preview`),
  })

  const installMutation = useMutation({
    mutationFn: () =>
      apiPost(`/api/workshops/${workshopId}/add-app`, { package_name: packageName }),
    onSuccess: () => onDone(),
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-text-muted gap-2">
        <Loader2 size={14} className="animate-spin" />
        <span className="text-xs">Loading preview...</span>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="px-4 py-8 text-center text-xs text-text-faint">
        Could not load preview.
        <button onClick={onBack} className="block mx-auto mt-2 text-accent underline">Go back</button>
      </div>
    )
  }

  const needsInstall = !data.already_installed
  const depsToInstall = data.dependencies.filter((d) => !d.already_installed && d.type === 'required')

  return (
    <div className="px-4 py-3 space-y-3">
      <div>
        <p className="text-xs font-medium text-text">{data.module.name}</p>
        {data.module.description && (
          <p className="text-[10px] text-text-faint mt-0.5">{data.module.description}</p>
        )}
        {data.module.version && (
          <p className="text-[10px] text-text-faint">v{data.module.version}</p>
        )}
      </div>

      {data.already_installed && (
        <div className="flex items-center gap-1.5 text-[10px] text-green-600 dark:text-green-400">
          <Check size={10} /> Already installed
        </div>
      )}

      {data.dependencies.length > 0 && (
        <div>
          <p className="text-[10px] font-medium text-text-muted mb-1">Dependencies</p>
          <div className="space-y-1">
            {data.dependencies.map((dep) => (
              <div key={dep.name} className="flex items-center gap-2 text-[10px]">
                {dep.already_installed ? (
                  <Check size={9} className="text-green-500" />
                ) : (
                  <Plus size={9} className="text-accent" />
                )}
                <span className={dep.already_installed ? 'text-text-faint' : 'text-text'}>
                  {dep.name}
                </span>
                <span className="text-text-faint">({dep.type})</span>
                {dep.already_installed && <span className="text-text-faint">installed</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {data.warnings.length > 0 && (
        <div className="space-y-1">
          {data.warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-1.5 text-[10px] text-yellow-600">
              <AlertTriangle size={10} className="shrink-0 mt-px" />
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}

      {installMutation.isError && (
        <p className="text-[10px] text-red-500">
          Install failed. Please try again.
        </p>
      )}

      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={onBack}
          className="px-3 py-1.5 text-[10px] rounded border border-border text-text-muted hover:bg-surface-el transition-colors"
        >
          Back
        </button>
        <button
          onClick={() => installMutation.mutate()}
          disabled={installMutation.isPending}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-[10px] font-medium rounded bg-accent text-white hover:bg-accent/90 transition-colors disabled:opacity-50"
        >
          {installMutation.isPending ? (
            <><Loader2 size={10} className="animate-spin" /> Installing...</>
          ) : needsInstall ? (
            <>{depsToInstall.length > 0 ? `Install ${depsToInstall.length + 1} packages & Add` : 'Install & Add'}</>
          ) : (
            'Add to Workshop'
          )}
        </button>
      </div>
    </div>
  )
}

function NoRegistriesState() {
  const [url, setUrl] = useState('')
  const [name, setName] = useState('')

  const addMutation = useMutation({
    mutationFn: () => apiPost('/api/registries', { name: name || 'default', git_url: url }),
  })

  return (
    <div className="px-4 py-6 space-y-3">
      <p className="text-xs text-text-muted text-center">
        Add a registry to browse apps.
      </p>
      <div className="space-y-2">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Registry name"
          className="w-full px-3 py-1.5 text-xs rounded border border-border bg-surface text-text placeholder:text-text-faint focus:outline-none focus:border-accent/50"
        />
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Git URL (https://...)"
          className="w-full px-3 py-1.5 text-xs rounded border border-border bg-surface text-text placeholder:text-text-faint focus:outline-none focus:border-accent/50"
        />
        <button
          onClick={() => addMutation.mutate()}
          disabled={!url || addMutation.isPending}
          className="w-full px-3 py-1.5 text-[10px] font-medium rounded bg-accent text-white hover:bg-accent/90 transition-colors disabled:opacity-50"
        >
          {addMutation.isPending ? 'Adding...' : 'Add Registry'}
        </button>
        {addMutation.isSuccess && (
          <p className="text-[10px] text-green-600 text-center">Registry added. Search above.</p>
        )}
      </div>
    </div>
  )
}
