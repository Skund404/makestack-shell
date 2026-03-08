/**
 * Package Manager
 *
 * Three-tab power-user interface:
 *   Installed — all installed packages with full technical metadata
 *   Browse    — search across configured registries, install from results
 *   Registries — manage registry sources (add / remove / refresh)
 */
import { useState, useEffect, useRef } from 'react'
import {
  Package,
  Plus,
  RefreshCw,
  Trash2,
  ArrowUp,
  AlertTriangle,
  CheckCircle,
  Search,
  Globe,
  FolderOpen,
  RotateCcw,
  Terminal,
  XCircle,
} from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardBody } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Tabs, TabContent } from '@/components/ui/Tabs'
import { cn } from '@/lib/utils'
import type { InstalledPackage, PackageSearchResult, RegistryRecord } from '@/lib/types'
import {
  usePackageList,
  usePackageSearch,
  useInstallPackage,
  useUninstallPackage,
  useUpdatePackage,
  useRegistries,
  useAddRegistry,
  useRemoveRegistry,
  useRefreshRegistries,
} from '@/hooks/use-packages'
import type { InstallResult } from '@/lib/types'
import { ApiError } from '@/lib/api'

// ---------------------------------------------------------------------------
// Type badge
// ---------------------------------------------------------------------------

const TYPE_VARIANTS: Record<string, 'accent' | 'purple' | 'success' | 'warning' | 'muted'> = {
  module: 'accent',
  'widget-pack': 'purple',
  catalogue: 'success',
  data: 'warning',
}

function TypeBadge({ type }: { type: string }) {
  return <Badge variant={TYPE_VARIANTS[type] ?? 'muted'}>{type}</Badge>
}

// ---------------------------------------------------------------------------
// Source label — registry / git / local
// ---------------------------------------------------------------------------

function SourceLabel({ pkg }: { pkg: InstalledPackage }) {
  if (pkg.registry_name) {
    return (
      <span className="font-mono text-xs text-text-muted">
        <span className="text-text-faint">via </span>{pkg.registry_name}
      </span>
    )
  }
  if (pkg.git_url) {
    const short = pkg.git_url.replace(/^https?:\/\//, '').replace(/\.git$/, '')
    return (
      <span className="font-mono text-xs text-text-muted" title={pkg.git_url}>
        <span className="text-text-faint">git: </span>
        <span className="truncate max-w-[180px] inline-block align-bottom">{short}</span>
      </span>
    )
  }
  if (pkg.package_path) {
    return (
      <span className="font-mono text-xs text-text-muted" title={pkg.package_path}>
        <span className="text-text-faint">local: </span>
        <span className="truncate max-w-[180px] inline-block align-bottom">{pkg.package_path}</span>
      </span>
    )
  }
  return <span className="text-xs text-text-faint">—</span>
}

// ---------------------------------------------------------------------------
// Install result display
// ---------------------------------------------------------------------------

function InstallResultPanel({ result }: { result: InstallResult }) {
  return (
    <div className={cn(
      'rounded border p-3 space-y-2 text-xs',
      result.success ? 'border-success/30 bg-success/5' : 'border-danger/30 bg-danger/5',
    )}>
      <div className="flex items-start gap-2">
        {result.success
          ? <CheckCircle size={14} className="text-success shrink-0 mt-0.5" />
          : <XCircle size={14} className="text-danger shrink-0 mt-0.5" />}
        <div className="space-y-0.5">
          <p className={result.success ? 'text-success font-medium' : 'text-danger font-medium'}>
            {result.success
              ? `Installed ${result.package_name} v${result.version}`
              : `Failed: ${result.message}`}
          </p>
          {result.success && result.message && (
            <p className="text-text-muted">{result.message}</p>
          )}
        </div>
      </div>

      {result.restart_required && (
        <div className="flex items-center gap-2 px-3 py-2 rounded bg-warning/10 border border-warning/20 text-warning">
          <RotateCcw size={12} />
          <span className="font-medium">Shell restart required to activate this package.</span>
        </div>
      )}

      {result.warnings.length > 0 && (
        <div className="space-y-1 border-t border-border pt-2 mt-1">
          {result.warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2 text-warning">
              <AlertTriangle size={12} className="shrink-0 mt-0.5" />
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Install dialog
// ---------------------------------------------------------------------------

type SourceMode = 'registry' | 'git' | 'local'

interface InstallDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  prefillName?: string
}

function InstallDialog({ open, onOpenChange, prefillName }: InstallDialogProps) {
  const [mode, setMode] = useState<SourceMode>('registry')
  const [name, setName] = useState(prefillName ?? '')
  const [source, setSource] = useState('')
  const [version, setVersion] = useState('')
  const [result, setResult] = useState<InstallResult | null>(null)
  const install = useInstallPackage()

  useEffect(() => {
    if (!open) {
      // Reset on close
      setMode('registry')
      setName(prefillName ?? '')
      setSource('')
      setVersion('')
      setResult(null)
      install.reset()
    } else if (prefillName) {
      setName(prefillName)
    }
  }, [open, prefillName]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleInstall = () => {
    const body =
      mode === 'registry'
        ? { name: name.trim() || undefined, version: version.trim() || undefined }
        : { source: source.trim() || undefined, name: name.trim() || undefined, version: version.trim() || undefined }

    install.mutate(body, {
      onSuccess: (res) => setResult(res),
      onError: () => setResult(null),
    })
  }

  const isValid =
    mode === 'registry' ? name.trim().length > 0 : source.trim().length > 0

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Install Package"
      className="max-w-xl"
    >
      <div className="space-y-4">
        {/* Source mode selector */}
        <div className="flex gap-1 p-1 rounded bg-surface-el border border-border">
          {(['registry', 'git', 'local'] as SourceMode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={cn(
                'flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded text-xs font-medium transition-colors',
                mode === m
                  ? 'bg-surface text-text border border-border-bright shadow-sm'
                  : 'text-text-faint hover:text-text-muted',
              )}
            >
              {m === 'registry' && <Globe size={11} />}
              {m === 'git' && <Terminal size={11} />}
              {m === 'local' && <FolderOpen size={11} />}
              {m === 'registry' ? 'Registry' : m === 'git' ? 'Git URL' : 'Local Path'}
            </button>
          ))}
        </div>

        {/* Fields */}
        {mode === 'registry' && (
          <div className="space-y-2">
            <label className="block text-xs font-medium text-text-muted">Package name *</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. inventory-stock"
              className="font-mono text-xs"
            />
            <p className="text-xs text-text-faint">
              Resolved via your configured registries. Use{' '}
              <span className="font-mono">Browse</span> tab to discover packages.
            </p>
          </div>
        )}

        {mode === 'git' && (
          <div className="space-y-2">
            <label className="block text-xs font-medium text-text-muted">Git URL *</label>
            <Input
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="https://github.com/org/makestack-module-name"
              className="font-mono text-xs"
            />
            <label className="block text-xs font-medium text-text-muted">Name (optional)</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Override package name"
              className="font-mono text-xs"
            />
          </div>
        )}

        {mode === 'local' && (
          <div className="space-y-2">
            <label className="block text-xs font-medium text-text-muted">
              Local path on server *
            </label>
            <Input
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="/absolute/path/to/package or ./relative"
              className="font-mono text-xs"
            />
            <p className="text-xs text-text-faint">
              Path is resolved by the Shell server process, not the browser.
            </p>
          </div>
        )}

        {/* Version pin (all modes) */}
        <div className="space-y-1">
          <label className="block text-xs font-medium text-text-muted">
            Version pin <span className="text-text-faint font-normal">(optional — defaults to latest)</span>
          </label>
          <Input
            value={version}
            onChange={(e) => setVersion(e.target.value)}
            placeholder="1.2.0"
            className="font-mono text-xs w-32"
          />
        </div>

        {/* Error */}
        {install.isError && (
          <div className="rounded border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger">
            {install.error instanceof ApiError ? install.error.message : 'Install failed'}
          </div>
        )}

        {/* Result */}
        {result && <InstallResultPanel result={result} />}

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-1">
          {result?.success ? (
            <Button onClick={() => onOpenChange(false)}>Close</Button>
          ) : (
            <>
              <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
              <Button
                onClick={handleInstall}
                disabled={!isValid || install.isPending}
              >
                {install.isPending ? 'Installing…' : 'Install'}
              </Button>
            </>
          )}
        </div>
      </div>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Uninstall confirm dialog
// ---------------------------------------------------------------------------

interface UninstallDialogProps {
  pkg: InstalledPackage | null
  onOpenChange: (open: boolean) => void
}

function UninstallDialog({ pkg, onOpenChange }: UninstallDialogProps) {
  const uninstall = useUninstallPackage()
  const [result, setResult] = useState<InstallResult | null>(null)

  useEffect(() => {
    if (!pkg) { setResult(null); uninstall.reset() }
  }, [pkg]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!pkg) return null

  const handleUninstall = () => {
    uninstall.mutate(pkg.name, {
      onSuccess: (res) => setResult(res),
    })
  }

  return (
    <Dialog
      open={!!pkg}
      onOpenChange={onOpenChange}
      title={`Uninstall ${pkg.name}`}
    >
      <div className="space-y-4">
        {!result ? (
          <>
            <p className="text-sm text-text-muted">
              Remove <span className="font-medium text-text">{pkg.name}</span>{' '}
              <span className="text-text-faint">(v{pkg.version}, {pkg.type})</span>?
            </p>
            {pkg.type === 'module' && (
              <div className="flex items-start gap-2 text-xs text-text-muted rounded border border-border p-3">
                <AlertTriangle size={12} className="text-warning shrink-0 mt-0.5" />
                <span>
                  Module tables and data are <strong className="text-text">preserved</strong> in
                  the UserDB. Reinstalling later will reuse existing data.
                </span>
              </div>
            )}
            {uninstall.isError && (
              <div className="text-xs text-danger">
                {uninstall.error instanceof ApiError ? uninstall.error.message : 'Uninstall failed'}
              </div>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
              <Button
                variant="danger"
                onClick={handleUninstall}
                disabled={uninstall.isPending}
              >
                {uninstall.isPending ? 'Removing…' : 'Uninstall'}
              </Button>
            </div>
          </>
        ) : (
          <>
            <InstallResultPanel result={result} />
            <div className="flex justify-end">
              <Button onClick={() => onOpenChange(false)}>Close</Button>
            </div>
          </>
        )}
      </div>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Installed tab
// ---------------------------------------------------------------------------

const TYPE_FILTERS = ['all', 'module', 'widget-pack', 'catalogue', 'data'] as const
type TypeFilter = typeof TYPE_FILTERS[number]

function InstalledTab() {
  const { data, isLoading } = usePackageList()
  const updatePkg = useUpdatePackage()
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all')
  const [search, setSearch] = useState('')
  const [uninstallTarget, setUninstallTarget] = useState<InstalledPackage | null>(null)
  const [updateResults, setUpdateResults] = useState<Record<string, InstallResult>>({})

  const packages = data?.items ?? []
  const filtered = packages.filter((p) => {
    if (typeFilter !== 'all' && p.type !== typeFilter) return false
    if (search && !p.name.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const handleUpdate = (pkg: InstalledPackage) => {
    updatePkg.mutate(
      { name: pkg.name },
      { onSuccess: (res) => setUpdateResults((prev) => ({ ...prev, [pkg.name]: res })) },
    )
  }

  if (isLoading) {
    return <div className="p-6 text-sm text-text-muted">Loading packages…</div>
  }

  return (
    <div className="p-4 space-y-3">
      {/* Filter row */}
      <div className="flex items-center gap-2">
        <div className="relative">
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-faint pointer-events-none" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter by name…"
            className={cn(
              'pl-7 pr-3 py-1.5 text-xs rounded border border-border bg-surface',
              'text-text placeholder:text-text-faint focus:outline-none focus:border-accent/40',
              'w-48',
            )}
          />
        </div>
        <div className="flex gap-1">
          {TYPE_FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setTypeFilter(f)}
              className={cn(
                'px-2.5 py-1 text-xs rounded border transition-colors',
                typeFilter === f
                  ? 'border-accent/30 bg-accent/10 text-accent'
                  : 'border-border text-text-faint hover:text-text-muted hover:border-border-bright',
              )}
            >
              {f === 'all' ? `All (${packages.length})` : f}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <Card>
          <CardBody>
            <p className="text-sm text-text-faint text-center py-4">
              {packages.length === 0
                ? 'No packages installed. Use the Install Package button or the Browse tab.'
                : 'No packages match the current filter.'}
            </p>
          </CardBody>
        </Card>
      ) : (
        <div className="rounded border border-border overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border bg-surface-el">
                <th className="px-3 py-2 text-left font-medium text-text-faint">Name</th>
                <th className="px-3 py-2 text-left font-medium text-text-faint">Type</th>
                <th className="px-3 py-2 text-left font-medium text-text-faint">Version</th>
                <th className="px-3 py-2 text-left font-medium text-text-faint">Source</th>
                <th className="px-3 py-2 text-left font-medium text-text-faint">Installed</th>
                <th className="px-3 py-2 text-left font-medium text-text-faint">Cache path</th>
                <th className="px-3 py-2 text-right font-medium text-text-faint">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((pkg, i) => {
                const updateResult = updateResults[pkg.name]
                const isUpdating = updatePkg.isPending && updatePkg.variables?.name === pkg.name
                return (
                  <>
                    <tr
                      key={pkg.name}
                      className={cn(
                        'border-b border-border last:border-0 hover:bg-surface-el/40 transition-colors',
                        i % 2 === 0 ? 'bg-bg' : 'bg-surface',
                      )}
                    >
                      <td className="px-3 py-2.5 font-mono font-medium text-text">{pkg.name}</td>
                      <td className="px-3 py-2.5"><TypeBadge type={pkg.type} /></td>
                      <td className="px-3 py-2.5 font-mono text-text-muted">{pkg.version}</td>
                      <td className="px-3 py-2.5 max-w-[200px]"><SourceLabel pkg={pkg} /></td>
                      <td className="px-3 py-2.5 text-text-faint whitespace-nowrap">
                        {new Date(pkg.installed_at).toLocaleDateString()}
                      </td>
                      <td className="px-3 py-2.5 max-w-[160px]">
                        {pkg.package_path ? (
                          <span
                            className="font-mono text-xs text-text-faint truncate block max-w-full"
                            title={pkg.package_path}
                          >
                            {pkg.package_path.replace(/^.*[\\/](.{0,40})$/, '…/$1')}
                          </span>
                        ) : (
                          <span className="text-text-faint">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="flex justify-end gap-1.5">
                          {pkg.git_url && (
                            <button
                              onClick={() => handleUpdate(pkg)}
                              disabled={isUpdating}
                              title="Update to latest"
                              className="p-1 rounded text-text-faint hover:text-accent hover:bg-accent/10 transition-colors disabled:opacity-50"
                            >
                              <ArrowUp size={13} />
                            </button>
                          )}
                          <button
                            onClick={() => setUninstallTarget(pkg)}
                            title="Uninstall"
                            className="p-1 rounded text-text-faint hover:text-danger hover:bg-danger/10 transition-colors"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                    {updateResult && (
                      <tr key={`${pkg.name}-result`} className="border-b border-border last:border-0">
                        <td colSpan={7} className="px-3 pb-2.5">
                          <InstallResultPanel result={updateResult} />
                        </td>
                      </tr>
                    )}
                  </>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <UninstallDialog
        pkg={uninstallTarget}
        onOpenChange={(open) => { if (!open) setUninstallTarget(null) }}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Browse tab
// ---------------------------------------------------------------------------

function BrowseTab({ onInstall }: { onInstall: (name: string) => void }) {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { data: packageList } = usePackageList()
  const installedNames = new Set((packageList?.items ?? []).map((p) => p.name))

  const { data, isLoading, isFetching } = usePackageSearch(debouncedQuery)

  const handleQueryChange = (v: string) => {
    setQuery(v)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedQuery(v), 350)
  }

  return (
    <div className="p-4 space-y-3">
      <div className="relative max-w-md">
        <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-faint pointer-events-none" />
        <input
          value={query}
          onChange={(e) => handleQueryChange(e.target.value)}
          placeholder="Filter packages…"
          className={cn(
            'w-full pl-8 pr-3 py-2 text-sm rounded border border-border bg-surface',
            'text-text placeholder:text-text-faint focus:outline-none focus:border-accent/40',
          )}
          autoFocus
        />
        {isFetching && (
          <RefreshCw size={11} className="absolute right-3 top-1/2 -translate-y-1/2 text-text-faint animate-spin" />
        )}
      </div>

      {isLoading && (
        <div className="text-sm text-text-muted">Loading packages…</div>
      )}

      {data && data.items.length === 0 && (
        <Card>
          <CardBody>
            <p className="text-sm text-text-faint text-center py-4">
              {debouncedQuery
                ? `No packages found for "${data.query}".`
                : 'No packages found. Add a registry in the Registries tab.'}
            </p>
          </CardBody>
        </Card>
      )}

      {data && data.items.length > 0 && (
        <>
          <p className="text-xs text-text-faint">
            {debouncedQuery
              ? `${data.total} result${data.total !== 1 ? 's' : ''} for "${data.query}"`
              : `${data.total} package${data.total !== 1 ? 's' : ''} available`}
          </p>
          <div className="space-y-2">
            {data.items.map((pkg) => (
              <BrowseResultCard
                key={pkg.name}
                pkg={pkg}
                installed={installedNames.has(pkg.name)}
                onInstall={() => onInstall(pkg.name)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function BrowseResultCard({
  pkg,
  installed,
  onInstall,
}: {
  pkg: PackageSearchResult
  installed: boolean
  onInstall: () => void
}) {
  return (
    <div className="rounded border border-border bg-surface hover:border-border-bright transition-colors p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-sm font-medium text-text">{pkg.name}</span>
            <TypeBadge type={pkg.type} />
            {installed && <Badge variant="success">installed</Badge>}
          </div>
          {pkg.description && (
            <p className="text-xs text-text-muted">{pkg.description}</p>
          )}
          <div className="flex items-center gap-3 text-xs text-text-faint">
            <span>
              <span className="text-text-faint">registry: </span>
              <span className="font-mono">{pkg.registry}</span>
            </span>
            {pkg.git_url && (
              <span className="font-mono truncate max-w-[220px]" title={pkg.git_url}>
                {pkg.git_url.replace(/^https?:\/\//, '')}
              </span>
            )}
          </div>
        </div>
        <Button
          variant={installed ? 'ghost' : 'primary'}
          onClick={onInstall}
          disabled={installed}
          className="shrink-0 text-xs"
        >
          {installed ? 'Installed' : 'Install'}
        </Button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Registries tab
// ---------------------------------------------------------------------------

function AddRegistryDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [name, setName] = useState('')
  const [gitUrl, setGitUrl] = useState('')
  const add = useAddRegistry()

  useEffect(() => {
    if (!open) { setName(''); setGitUrl(''); add.reset() }
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleAdd = () => {
    add.mutate({ name: name.trim(), git_url: gitUrl.trim() }, {
      onSuccess: () => onOpenChange(false),
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Add Registry">
      <div className="space-y-3">
        <div className="space-y-1">
          <label className="text-xs font-medium text-text-muted">Registry name *</label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="my-registry"
            className="font-mono text-xs"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium text-text-muted">Git URL *</label>
          <Input
            value={gitUrl}
            onChange={(e) => setGitUrl(e.target.value)}
            placeholder="https://github.com/org/makestack-registry"
            className="font-mono text-xs"
          />
          <p className="text-xs text-text-faint">
            The repo must contain an <code className="font-mono">index.json</code> at its root.
          </p>
        </div>
        {add.isError && (
          <div className="text-xs text-danger">
            {add.error instanceof ApiError ? add.error.message : 'Failed to add registry'}
          </div>
        )}
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button
            onClick={handleAdd}
            disabled={!name.trim() || !gitUrl.trim() || add.isPending}
          >
            {add.isPending ? 'Adding…' : 'Add Registry'}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}

function RegistriesTab() {
  const { data, isLoading } = useRegistries()
  const remove = useRemoveRegistry()
  const refresh = useRefreshRegistries()
  const [addOpen, setAddOpen] = useState(false)
  const [refreshResult, setRefreshResult] = useState<{
    refreshed: string[]
    errors: Record<string, string>
  } | null>(null)

  const registries = data?.items ?? []

  const handleRefreshAll = () => {
    refresh.mutate(undefined, {
      onSuccess: (res) => setRefreshResult(res),
    })
  }

  if (isLoading) {
    return <div className="p-6 text-sm text-text-muted">Loading registries…</div>
  }

  return (
    <div className="p-4 space-y-3">
      {/* Toolbar */}
      <div className="flex items-center gap-2">
        <Button onClick={() => setAddOpen(true)}>
          <Plus size={13} />
          Add Registry
        </Button>
        <Button
          variant="ghost"
          onClick={handleRefreshAll}
          disabled={refresh.isPending || registries.length === 0}
        >
          <RefreshCw size={13} className={refresh.isPending ? 'animate-spin' : ''} />
          Refresh All
        </Button>
      </div>

      {/* Refresh result */}
      {refreshResult && (
        <div className="rounded border border-border p-3 text-xs space-y-1">
          {refreshResult.refreshed.length > 0 && (
            <p className="text-success">
              <CheckCircle size={11} className="inline mr-1" />
              Refreshed: {refreshResult.refreshed.join(', ')}
            </p>
          )}
          {Object.entries(refreshResult.errors).map(([name, err]) => (
            <p key={name} className="text-danger">
              <XCircle size={11} className="inline mr-1" />
              {name}: {err}
            </p>
          ))}
        </div>
      )}

      {/* Registries list */}
      {registries.length === 0 ? (
        <Card>
          <CardBody>
            <p className="text-sm text-text-faint text-center py-4">
              No registries configured. Add one to browse and install packages by name.
            </p>
          </CardBody>
        </Card>
      ) : (
        <div className="rounded border border-border overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border bg-surface-el">
                <th className="px-3 py-2 text-left font-medium text-text-faint">Name</th>
                <th className="px-3 py-2 text-left font-medium text-text-faint">Git URL</th>
                <th className="px-3 py-2 text-left font-medium text-text-faint w-20">Packages</th>
                <th className="px-3 py-2 text-left font-medium text-text-faint">Added</th>
                <th className="px-3 py-2 text-left font-medium text-text-faint">Last Refreshed</th>
                <th className="px-3 py-2 text-right font-medium text-text-faint">Actions</th>
              </tr>
            </thead>
            <tbody>
              {registries.map((reg: RegistryRecord, i: number) => (
                <RegistryRow
                  key={reg.name}
                  reg={reg}
                  striped={i % 2 !== 0}
                  onRemove={() => remove.mutate(reg.name)}
                  removing={remove.isPending && remove.variables === reg.name}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <AddRegistryDialog open={addOpen} onOpenChange={setAddOpen} />
    </div>
  )
}

function RegistryRow({
  reg,
  striped,
  onRemove,
  removing,
}: {
  reg: RegistryRecord
  striped: boolean
  onRemove: () => void
  removing: boolean
}) {
  const gitShort = reg.git_url.replace(/^https?:\/\//, '').replace(/\.git$/, '')

  return (
    <tr className={cn(
      'border-b border-border last:border-0 hover:bg-surface-el/40 transition-colors',
      striped ? 'bg-surface' : 'bg-bg',
    )}>
      <td className="px-3 py-2.5 font-mono font-medium text-text">{reg.name}</td>
      <td className="px-3 py-2.5 max-w-[260px]">
        <span
          className="font-mono text-xs text-text-muted truncate block max-w-full"
          title={reg.git_url}
        >
          {gitShort}
        </span>
      </td>
      <td className="px-3 py-2.5 text-text-muted text-center">{reg.package_count}</td>
      <td className="px-3 py-2.5 text-text-faint whitespace-nowrap">
        {new Date(reg.added_at).toLocaleDateString()}
      </td>
      <td className="px-3 py-2.5 text-text-faint whitespace-nowrap">
        {reg.last_refreshed
          ? new Date(reg.last_refreshed).toLocaleString()
          : <span className="text-text-faint/50">never</span>}
      </td>
      <td className="px-3 py-2.5">
        <div className="flex justify-end">
          <button
            onClick={onRemove}
            disabled={removing}
            title="Remove registry"
            className="p-1 rounded text-text-faint hover:text-danger hover:bg-danger/10 transition-colors disabled:opacity-50"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </td>
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Root page
// ---------------------------------------------------------------------------

const TABS = [
  { value: 'installed', label: 'Installed' },
  { value: 'browse', label: 'Browse' },
  { value: 'registries', label: 'Registries' },
]

export function PackagesIndex() {
  const [tab, setTab] = useState('installed')
  const [installOpen, setInstallOpen] = useState(false)
  const [installPrefill, setInstallPrefill] = useState<string | undefined>()

  const { data } = usePackageList()
  const totalInstalled = data?.total ?? 0

  const handleInstallFromBrowse = (name: string) => {
    setInstallPrefill(name)
    setInstallOpen(true)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Page header */}
      <div className="px-6 py-4 border-b border-border flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2.5">
          <Package size={17} className="text-accent" />
          <h1 className="text-base font-semibold text-text">Packages</h1>
          {totalInstalled > 0 && (
            <Badge variant="muted">{totalInstalled} installed</Badge>
          )}
        </div>
        <Button onClick={() => { setInstallPrefill(undefined); setInstallOpen(true) }}>
          <Plus size={13} />
          Install Package
        </Button>
      </div>

      {/* Tabs */}
      <Tabs
        tabs={TABS}
        value={tab}
        onValueChange={setTab}
        className="flex-1 min-h-0"
      >
        <TabContent value="installed" className="flex-1 overflow-y-auto">
          <InstalledTab />
        </TabContent>
        <TabContent value="browse" className="flex-1 overflow-y-auto">
          <BrowseTab onInstall={handleInstallFromBrowse} />
        </TabContent>
        <TabContent value="registries" className="flex-1 overflow-y-auto">
          <RegistriesTab />
        </TabContent>
      </Tabs>

      {/* Install dialog */}
      <InstallDialog
        open={installOpen}
        onOpenChange={setInstallOpen}
        prefillName={installPrefill}
      />
    </div>
  )
}
