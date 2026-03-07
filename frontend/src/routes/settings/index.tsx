import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Server, Database, Clock } from 'lucide-react'
import { apiGet, apiPut } from '@/lib/api'
import { applyTheme } from '@/theme/loader'
import { Separator } from '@/components/ui/Separator'
import { cn } from '@/lib/utils'
import type { SystemStatus } from '@/lib/types'
import type { ThemeData } from '@/theme/tokens'

const THEMES = [
  { value: 'cyberpunk', label: 'Cyberpunk' },
  { value: 'workshop', label: 'Workshop' },
  { value: 'daylight', label: 'Daylight' },
  { value: 'high-contrast', label: 'High Contrast' },
]

const THEME_SWATCHES: Record<string, string[]> = {
  cyberpunk: ['#09090f', '#00e5ff', '#bf5fff', '#00e676'],
  workshop: ['#1a1210', '#ff9800', '#ce93d8', '#66bb6a'],
  daylight: ['#f8f9fa', '#0066cc', '#7b3fe4', '#1a7f37'],
  'high-contrast': ['#000000', '#ffff00', '#ff80ff', '#00ff00'],
}

function ThemeSwatches({ name }: { name: string }) {
  const colors = THEME_SWATCHES[name] ?? []
  return (
    <div className="flex gap-1">
      {colors.map((c) => (
        <span
          key={c}
          className="w-4 h-4 rounded-sm border border-black/20"
          style={{ backgroundColor: c }}
        />
      ))}
    </div>
  )
}

function SystemInfo() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['system-status'],
    queryFn: () => apiGet<SystemStatus>('/api/status'),
  })

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-text-muted">
        <Loader2 size={12} className="animate-spin" /> Loading…
      </div>
    )
  }

  if (isError || !data) {
    return <p className="text-sm text-danger/70">Failed to load system status.</p>
  }

  const uptime =
    data.uptime_seconds < 60
      ? `${Math.round(data.uptime_seconds)}s`
      : data.uptime_seconds < 3600
        ? `${Math.round(data.uptime_seconds / 60)}m`
        : `${Math.round(data.uptime_seconds / 3600)}h`

  return (
    <div className="space-y-3 text-sm">
      <div className="flex items-center gap-3">
        <Server size={13} className="text-text-faint shrink-0" />
        <span className="text-text-muted w-20 shrink-0">Shell</span>
        <span className="text-text font-mono text-xs">{data.shell_version}</span>
      </div>
      <div className="flex items-center gap-3">
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${data.core_connected ? 'bg-success' : 'bg-danger'}`}
        />
        <span className="text-text-muted w-20 shrink-0">Core</span>
        <span className="text-text-faint text-xs">
          {data.core_connected ? 'Connected' : 'Disconnected'} · {data.core_url}
        </span>
      </div>
      <div className="flex items-center gap-3">
        <Database size={13} className="text-text-faint shrink-0" />
        <span className="text-text-muted w-20 shrink-0">UserDB</span>
        <span className="text-text-faint text-xs font-mono truncate">{data.userdb_path}</span>
      </div>
      <div className="flex items-center gap-3">
        <Clock size={13} className="text-text-faint shrink-0" />
        <span className="text-text-muted w-20 shrink-0">Uptime</span>
        <span className="text-text-faint text-xs">{uptime}</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="w-2 h-2 rounded-full shrink-0 bg-text-faint/50" />
        <span className="text-text-muted w-20 shrink-0">Modules</span>
        <span className="text-text-faint text-xs">{data.modules_loaded} loaded</span>
      </div>
    </div>
  )
}

export function SettingsIndex() {
  const qc = useQueryClient()

  const { data: themeData } = useQuery({
    queryKey: ['active-theme'],
    queryFn: () => apiGet<{ name: string }>('/api/settings/theme'),
  })

  const themeMutation = useMutation({
    mutationFn: async (name: string) => {
      await apiPut<{ name: string }>('/api/settings/theme', { name })
      const vars = await apiGet<ThemeData>('/api/settings/theme/data')
      applyTheme(vars)
      return name
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['active-theme'] })
    },
  })

  const activeTheme = themeData?.name ?? 'cyberpunk'

  return (
    <div className="p-4 max-w-2xl space-y-6">
      <h1 className="text-base font-semibold text-text">Settings</h1>

      {/* Theme */}
      <section className="space-y-3">
        <h2 className="text-xs font-semibold text-text-faint uppercase tracking-widest">Theme</h2>
        <div className="space-y-2">
          {THEMES.map((t) => (
            <button
              key={t.value}
              onClick={() => themeMutation.mutate(t.value)}
              disabled={themeMutation.isPending}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded border text-sm transition-colors text-left',
                activeTheme === t.value
                  ? 'border-accent/40 bg-accent/5 text-text'
                  : 'border-border hover:border-border-bright text-text-muted hover:text-text',
              )}
            >
              <ThemeSwatches name={t.value} />
              <span className="flex-1">{t.label}</span>
              {activeTheme === t.value && (
                <span className="text-xs text-accent">Active</span>
              )}
              {themeMutation.isPending && themeMutation.variables === t.value && (
                <Loader2 size={12} className="animate-spin text-text-faint" />
              )}
            </button>
          ))}
        </div>
      </section>

      <Separator />

      {/* System info */}
      <section className="space-y-3">
        <h2 className="text-xs font-semibold text-text-faint uppercase tracking-widest">System</h2>
        <SystemInfo />
      </section>
    </div>
  )
}
