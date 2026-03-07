/**
 * Dev: Module Inspector
 *
 * Shows each loaded module with its manifest details:
 * keywords, panels, API endpoints, UserDB tables, and load errors.
 */
import { useQuery } from '@tanstack/react-query'
import { Box, AlertTriangle, CheckCircle, ChevronDown, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { apiGet } from '@/lib/api'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/utils'

interface ModuleKeyword {
  keyword: string
  description: string
  renderer: string
}

interface ModuleEndpoint {
  method: string
  path: string
  description: string
}

interface ModulePanel {
  id: string
  display_name: string
  location: string
  component: string
}

interface ModuleTable {
  name: string
  description: string
}

interface LoadedModuleInfo {
  name: string
  version: string
  display_name: string
  description: string
  package_path: string | null
  has_backend: boolean
  has_frontend: boolean
  mount_prefix: string
  keywords: ModuleKeyword[]
  api_endpoints: ModuleEndpoint[]
  panels: ModulePanel[]
  userdb_tables: ModuleTable[]
}

interface FailedModuleInfo {
  name: string
  error: string
}

interface ModulesData {
  loaded: LoadedModuleInfo[]
  failed: FailedModuleInfo[]
  total_loaded: number
  total_failed: number
}

const METHOD_COLORS: Record<string, string> = {
  GET: 'text-success',
  POST: 'text-accent',
  PUT: 'text-warning',
  DELETE: 'text-danger',
}

export function DevModules() {
  const { data, isLoading } = useQuery<ModulesData>({
    queryKey: ['dev', 'modules'],
    queryFn: () => apiGet<ModulesData>('/api/dev/modules'),
  })

  if (isLoading) {
    return <div className="p-6 text-sm text-text-muted">Loading…</div>
  }

  const loaded = data?.loaded ?? []
  const failed = data?.failed ?? []

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div className="flex items-center gap-2 mb-4">
        <Box size={18} className="text-accent" />
        <h1 className="text-lg font-semibold text-text">Module Inspector</h1>
        <Badge>{data?.total_loaded ?? 0} loaded</Badge>
        {(data?.total_failed ?? 0) > 0 && (
          <Badge variant="danger">{data?.total_failed} failed</Badge>
        )}
      </div>

      {loaded.length === 0 && failed.length === 0 && (
        <Card>
          <CardBody>
            <p className="text-sm text-text-faint">
              No modules installed. Use{' '}
              <code className="font-mono text-xs">makestack dev --module ./path</code>{' '}
              to load a local module.
            </p>
          </CardBody>
        </Card>
      )}

      {loaded.map((m) => (
        <ModuleCard key={m.name} module={m} />
      ))}

      {failed.map((f) => (
        <Card key={f.name} className="border-danger/30">
          <CardHeader>
            <div className="flex items-center gap-2">
              <AlertTriangle size={14} className="text-danger" />
              <span className="text-sm font-medium text-danger">{f.name}</span>
              <Badge variant="danger">failed to load</Badge>
            </div>
          </CardHeader>
          <CardBody>
            <pre className="text-xs text-danger/80 font-mono whitespace-pre-wrap">{f.error}</pre>
          </CardBody>
        </Card>
      ))}
    </div>
  )
}

function ModuleCard({ module: m }: { module: LoadedModuleInfo }) {
  const [open, setOpen] = useState(true)

  return (
    <Card>
      <div
        className="px-4 py-3 border-b border-border cursor-pointer flex items-center gap-2"
        onClick={() => setOpen(!open)}
      >
        <CheckCircle size={14} className="text-success" />
        <span className="text-sm font-medium text-text">{m.display_name}</span>
        <span className="text-xs text-text-faint">v{m.version}</span>
        <Badge variant="success">loaded</Badge>
        {m.has_backend && <Badge>backend</Badge>}
        {m.has_frontend && <Badge>frontend</Badge>}
        <div className="flex-1" />
        {open ? <ChevronDown size={14} className="text-text-muted" /> : <ChevronRight size={14} className="text-text-muted" />}
      </div>

      {open && (
        <CardBody className="space-y-4">
          <div className="text-xs text-text-muted space-y-1">
            <p>{m.description}</p>
            {m.package_path && (
              <p><span className="text-text-faint">Path: </span><code className="font-mono">{m.package_path}</code></p>
            )}
            {m.has_backend && (
              <p><span className="text-text-faint">Mount: </span><code className="font-mono">{m.mount_prefix}/</code></p>
            )}
          </div>

          {m.keywords.length > 0 && (
            <Section label="Keywords" count={m.keywords.length}>
              {m.keywords.map((kw) => (
                <div key={kw.keyword} className="flex items-start gap-3">
                  <code className="text-xs font-mono text-accent w-36 shrink-0">{kw.keyword}</code>
                  <span className="text-xs text-text-muted">{kw.description}</span>
                </div>
              ))}
            </Section>
          )}

          {m.api_endpoints.length > 0 && (
            <Section label="API Endpoints" count={m.api_endpoints.length}>
              {m.api_endpoints.map((ep, i) => (
                <div key={i} className="flex items-start gap-3">
                  <code className={cn('text-xs font-mono w-12 shrink-0 font-bold', METHOD_COLORS[ep.method] ?? 'text-text')}>
                    {ep.method}
                  </code>
                  <code className="text-xs font-mono text-text-muted w-40 shrink-0">{ep.path}</code>
                  <span className="text-xs text-text-muted">{ep.description}</span>
                </div>
              ))}
            </Section>
          )}

          {m.userdb_tables.length > 0 && (
            <Section label="UserDB Tables" count={m.userdb_tables.length}>
              {m.userdb_tables.map((t) => (
                <div key={t.name} className="flex items-start gap-3">
                  <code className="text-xs font-mono text-text w-48 shrink-0">{t.name}</code>
                  <span className="text-xs text-text-muted">{t.description}</span>
                </div>
              ))}
            </Section>
          )}

          {m.panels.length > 0 && (
            <Section label="Panels" count={m.panels.length}>
              {m.panels.map((p) => (
                <div key={p.id} className="flex items-start gap-3">
                  <code className="text-xs font-mono text-text w-32 shrink-0">{p.id}</code>
                  <span className="text-xs text-text-muted">{p.display_name} — {p.location}</span>
                </div>
              ))}
            </Section>
          )}
        </CardBody>
      )}
    </Card>
  )
}

function Section({ label, count, children }: { label: string; count: number; children: React.ReactNode }) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-text-faint">{label}</span>
        <Badge>{count}</Badge>
      </div>
      <div className="space-y-1.5 pl-2 border-l-2 border-border">{children}</div>
    </div>
  )
}
