import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Server, Database, Clock, Power, RotateCcw } from 'lucide-react'
import { apiGet, apiPut, apiPost } from '@/lib/api'
import { applyTheme } from '@/theme/loader'
import { cn } from '@/lib/utils'
import type { SystemStatus } from '@/lib/types'
import type { ThemeData } from '@/theme/tokens'
import { ProfileSettings } from './profile'

// ---------------------------------------------------------------------------
// Theme tab
// ---------------------------------------------------------------------------

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

function ThemeSettings() {
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
  )
}

// ---------------------------------------------------------------------------
// System tab
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// System controls — shutdown / restart
// ---------------------------------------------------------------------------

type ControlAction = 'shell-restart' | 'shell-shutdown' | 'core-shutdown' | null

function SystemControls() {
  const [confirm, setConfirm] = useState<ControlAction>(null)
  const [done, setDone] = useState<string | null>(null)

  const shellRestart = useMutation({
    mutationFn: () => apiPost<{ message: string }>('/api/system/restart', {}),
    onSuccess: (data) => {
      setConfirm(null)
      setDone(data.message)
    },
  })

  const shellShutdown = useMutation({
    mutationFn: () => apiPost<{ message: string }>('/api/system/shutdown', {}),
    onSuccess: (data) => {
      setConfirm(null)
      setDone(data.message)
    },
  })

  const coreShutdown = useMutation({
    mutationFn: () => apiPost<{ message: string }>('/api/system/core/shutdown', {}),
    onSuccess: (data) => {
      setConfirm(null)
      setDone(data.message)
    },
  })

  if (done) {
    return (
      <div className="rounded border border-border bg-surface p-3 text-sm text-text-muted">
        {done}
      </div>
    )
  }

  const ACTIONS: { id: ControlAction; label: string; description: string; icon: React.ReactNode; danger: boolean; mutation: typeof shellRestart }[] = [
    {
      id: 'shell-restart',
      label: 'Restart Shell',
      description: 'Reload modules and apply config changes without stopping Core.',
      icon: <RotateCcw size={13} />,
      danger: false,
      mutation: shellRestart,
    },
    {
      id: 'shell-shutdown',
      label: 'Shutdown Shell',
      description: 'Stop the Shell process. Core keeps running.',
      icon: <Power size={13} />,
      danger: true,
      mutation: shellShutdown,
    },
    {
      id: 'core-shutdown',
      label: 'Shutdown Core',
      description: 'Stop the Core process. Catalogue will be unavailable.',
      icon: <Power size={13} />,
      danger: true,
      mutation: coreShutdown,
    },
  ]

  return (
    <div className="space-y-2">
      {ACTIONS.map((action) => {
        const isPending = action.mutation.isPending
        const isConfirming = confirm === action.id

        return (
          <div key={action.id} className="rounded border border-border bg-surface">
            <div className="flex items-center gap-3 px-3 py-2.5">
              <span className={cn('shrink-0', action.danger ? 'text-danger/70' : 'text-text-faint')}>
                {action.icon}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-text">{action.label}</p>
                <p className="text-xs text-text-faint">{action.description}</p>
              </div>
              {!isConfirming ? (
                <button
                  onClick={() => setConfirm(action.id)}
                  disabled={isPending || confirm !== null}
                  className={cn(
                    'px-2.5 py-1 rounded text-xs font-medium transition-colors shrink-0',
                    action.danger
                      ? 'border border-danger/30 text-danger/80 hover:bg-danger/10 disabled:opacity-40'
                      : 'border border-border text-text-muted hover:border-border-bright hover:text-text disabled:opacity-40',
                  )}
                >
                  {action.label.split(' ')[0]}
                </button>
              ) : (
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className="text-xs text-text-muted">Sure?</span>
                  <button
                    onClick={() => action.mutation.mutate()}
                    disabled={isPending}
                    className="px-2 py-1 rounded text-xs font-medium bg-danger/20 text-danger hover:bg-danger/30 disabled:opacity-60 flex items-center gap-1"
                  >
                    {isPending && <Loader2 size={10} className="animate-spin" />}
                    Yes
                  </button>
                  <button
                    onClick={() => setConfirm(null)}
                    disabled={isPending}
                    className="px-2 py-1 rounded text-xs text-text-muted hover:text-text"
                  >
                    No
                  </button>
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Settings page — tabbed
// ---------------------------------------------------------------------------

const TABS = [
  { id: 'profile', label: 'Profile' },
  { id: 'theme',   label: 'Theme' },
  { id: 'system',  label: 'System' },
] as const

type TabId = typeof TABS[number]['id']

export function SettingsIndex() {
  const [activeTab, setActiveTab] = useState<TabId>('profile')

  return (
    <div className="p-4 max-w-2xl space-y-4">
      <h1 className="text-base font-semibold text-text">Settings</h1>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-border">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'px-3 py-1.5 text-sm transition-colors -mb-px border-b-2',
              activeTab === tab.id
                ? 'text-text border-accent'
                : 'text-text-muted border-transparent hover:text-text hover:border-border-bright',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="pt-1">
        {activeTab === 'profile' && <ProfileSettings />}

        {activeTab === 'theme' && (
          <section className="space-y-3">
            <h2 className="text-xs font-semibold text-text-faint uppercase tracking-widest">Theme</h2>
            <ThemeSettings />
          </section>
        )}

        {activeTab === 'system' && (
          <section className="space-y-6">
            <div className="space-y-3">
              <h2 className="text-xs font-semibold text-text-faint uppercase tracking-widest">System</h2>
              <SystemInfo />
            </div>
            <div className="space-y-3">
              <h2 className="text-xs font-semibold text-text-faint uppercase tracking-widest">Controls</h2>
              <SystemControls />
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
