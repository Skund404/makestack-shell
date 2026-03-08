import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, User, BarChart2, Clock, Boxes, Wrench, AlertCircle, CheckCircle2 } from 'lucide-react'
import { apiGet, apiPut } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UserProfile {
  id: string
  name: string
  avatar_path: string | null
  bio: string
  timezone: string
  locale: string
  created_at: string
  updated_at: string
}

interface UserStats {
  workshops_count: number
  inventory_count: number
  stale_inventory_count: number
  modules_installed: number
  modules_enabled: number
  active_workshop_id: string | null
  active_workshop_name: string | null
}

// ---------------------------------------------------------------------------
// Stats panel
// ---------------------------------------------------------------------------

function StatsPanel() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['user-stats'],
    queryFn: () => apiGet<UserStats>('/api/users/me/stats'),
    refetchInterval: 60_000,
  })

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-text-muted">
        <Loader2 size={12} className="animate-spin" /> Loading stats…
      </div>
    )
  }
  if (isError || !data) {
    return <p className="text-sm text-danger/70">Could not load activity stats.</p>
  }

  const statItems = [
    { icon: Boxes, label: 'Workshops', value: data.workshops_count },
    { icon: BarChart2, label: 'Inventory', value: data.inventory_count },
    { icon: AlertCircle, label: 'Needs update', value: data.stale_inventory_count },
    { icon: Wrench, label: 'Modules', value: `${data.modules_enabled} / ${data.modules_installed}` },
  ]

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        {statItems.map(({ icon: Icon, label, value }) => (
          <div
            key={label}
            className="flex items-center gap-2.5 px-3 py-2.5 rounded border border-border bg-surface"
          >
            <Icon size={13} className="text-text-faint shrink-0" />
            <div className="min-w-0">
              <p className="text-xs text-text-muted">{label}</p>
              <p className="text-sm font-mono font-medium text-text leading-tight">{value}</p>
            </div>
          </div>
        ))}
      </div>

      {data.active_workshop_name && (
        <p className="text-xs text-text-muted">
          Active workshop:{' '}
          <span className="text-accent font-medium">{data.active_workshop_name}</span>
        </p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Editable field
// ---------------------------------------------------------------------------

function Field({
  label,
  value,
  onChange,
  placeholder,
  multiline,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  multiline?: boolean
}) {
  const base =
    'w-full bg-surface border border-border rounded px-3 py-1.5 text-sm text-text placeholder:text-text-faint focus:outline-none focus:border-accent/50 transition-colors'

  return (
    <div className="space-y-1">
      <label className="text-xs text-text-muted">{label}</label>
      {multiline ? (
        <textarea
          className={`${base} resize-none h-20`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
        />
      ) : (
        <input
          type="text"
          className={base}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Profile form
// ---------------------------------------------------------------------------

export function ProfileSettings() {
  const qc = useQueryClient()

  const { data: profile, isLoading, isError } = useQuery({
    queryKey: ['user-profile'],
    queryFn: () => apiGet<UserProfile>('/api/users/me'),
  })

  const [name, setName] = useState('')
  const [bio, setBio] = useState('')
  const [avatarPath, setAvatarPath] = useState('')
  const [timezone, setTimezone] = useState('')
  const [locale, setLocale] = useState('')
  const [saved, setSaved] = useState(false)

  // Sync state when profile loads
  useEffect(() => {
    if (profile) {
      setName(profile.name)
      setBio(profile.bio)
      setAvatarPath(profile.avatar_path ?? '')
      setTimezone(profile.timezone)
      setLocale(profile.locale)
    }
  }, [profile])

  const mutation = useMutation({
    mutationFn: () =>
      apiPut<UserProfile>('/api/users/me', {
        name: name.trim() || undefined,
        bio,
        avatar_path: avatarPath,
        timezone: timezone || 'UTC',
        locale: locale || 'en',
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['user-profile'] })
      void qc.invalidateQueries({ queryKey: ['user-stats'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-text-muted py-4">
        <Loader2 size={13} className="animate-spin" /> Loading profile…
      </div>
    )
  }

  if (isError || !profile) {
    return (
      <p className="text-sm text-danger/70 py-4">Could not load user profile.</p>
    )
  }

  const isDirty =
    name !== profile.name ||
    bio !== profile.bio ||
    avatarPath !== (profile.avatar_path ?? '') ||
    timezone !== profile.timezone ||
    locale !== profile.locale

  return (
    <div className="space-y-6">
      {/* Avatar preview + user id */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-surface-el border border-border flex items-center justify-center shrink-0">
          {avatarPath ? (
            <img
              src={avatarPath}
              alt="Avatar"
              className="w-full h-full rounded-full object-cover"
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
            />
          ) : (
            <User size={16} className="text-text-faint" />
          )}
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium text-text truncate">{profile.name}</p>
          <p className="text-xs text-text-faint font-mono">id: {profile.id}</p>
        </div>
      </div>

      {/* Editable fields */}
      <div className="space-y-3">
        <Field label="Display name" value={name} onChange={setName} placeholder="Your name" />
        <Field
          label="Avatar path or URL"
          value={avatarPath}
          onChange={setAvatarPath}
          placeholder="/img/avatar.png or https://…"
        />
        <Field
          label="Bio"
          value={bio}
          onChange={setBio}
          placeholder="A short description of your making practice…"
          multiline
        />
        <div className="grid grid-cols-2 gap-3">
          <Field label="Timezone" value={timezone} onChange={setTimezone} placeholder="UTC" />
          <Field label="Locale" value={locale} onChange={setLocale} placeholder="en" />
        </div>
      </div>

      {/* Timestamps */}
      <div className="flex gap-4 text-xs text-text-faint">
        <span className="flex items-center gap-1">
          <Clock size={10} />
          Created {new Date(profile.created_at).toLocaleDateString()}
        </span>
        <span className="flex items-center gap-1">
          <Clock size={10} />
          Updated {new Date(profile.updated_at).toLocaleDateString()}
        </span>
      </div>

      {/* Save button */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => mutation.mutate()}
          disabled={!isDirty || mutation.isPending || !name.trim()}
          className="px-4 py-1.5 text-sm rounded bg-accent text-bg font-medium disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 transition-opacity"
        >
          {mutation.isPending ? (
            <span className="flex items-center gap-1.5">
              <Loader2 size={12} className="animate-spin" /> Saving…
            </span>
          ) : (
            'Save profile'
          )}
        </button>

        {saved && (
          <span className="flex items-center gap-1 text-xs text-success">
            <CheckCircle2 size={12} /> Saved
          </span>
        )}
        {mutation.isError && (
          <span className="text-xs text-danger">Save failed — check Shell logs.</span>
        )}
      </div>

      {/* Stats */}
      <div className="space-y-2 pt-2 border-t border-border">
        <h3 className="text-xs font-semibold text-text-faint uppercase tracking-widest">Activity</h3>
        <StatsPanel />
      </div>
    </div>
  )
}
