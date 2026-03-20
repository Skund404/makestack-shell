/**
 * ModuleAppSidebar — generic branded sidebar for modules in standalone app mode.
 *
 * Rendered from AppModeConfig data. Modules can register a custom sidebar
 * component to replace this if they need dynamic sections or custom badges.
 */
import { ArrowLeft } from 'lucide-react'
import { Link, useLocation, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { cn } from '@/lib/utils'
import { resolveIcon } from '@/lib/icons'
import { apiGet } from '@/lib/api'
import type { AppModeConfig, AppNavItem } from '@/modules/app-registry'

interface ModuleAppSidebarProps {
  config: AppModeConfig
}

function NavItemBadge({ endpoint }: { endpoint: string }) {
  const { data } = useQuery({
    queryKey: ['app-badge', endpoint],
    queryFn: () => apiGet<{ count: number }>(endpoint),
    staleTime: 30_000,
    refetchInterval: 60_000,
  })
  if (!data || data.count === 0) return null
  return (
    <span className="ml-auto text-[9px] font-medium px-1.5 py-px rounded-full bg-white/10 text-white/70">
      {data.count}
    </span>
  )
}

function AppNavLink({ item, theme }: { item: AppNavItem; theme?: AppModeConfig['theme'] }) {
  const loc = useLocation()
  const isActive = loc.pathname === item.route || loc.pathname.startsWith(item.route + '/')

  return (
    <Link to={item.route as never} className="block">
      <span
        className={cn(
          'flex items-center gap-2.5 px-3 py-2 rounded-md text-xs transition-colors w-full',
        )}
        style={{
          backgroundColor: isActive ? (theme?.sidebar_active_bg || 'rgba(255,255,255,0.08)') : 'transparent',
          color: isActive ? (theme?.sidebar_text || '#eddec8') : 'rgba(255,255,255,0.45)',
        }}
      >
        {resolveIcon(item.icon)}
        <span className="flex-1 truncate">{item.label}</span>
        {item.badge_endpoint && <NavItemBadge endpoint={item.badge_endpoint} />}
      </span>
    </Link>
  )
}

export function ModuleAppSidebar({ config }: ModuleAppSidebarProps) {
  const navigate = useNavigate()

  // Retrieve the originating workshop from sessionStorage
  const workshopId = (() => {
    try { return sessionStorage.getItem('app-mode-workshop-id') ?? '' } catch { return '' }
  })()
  const workshopName = (() => {
    try { return sessionStorage.getItem('app-mode-workshop-name') ?? 'Workshop' } catch { return 'Workshop' }
  })()

  const handleBack = () => {
    if (workshopId) {
      void navigate({ to: '/workshop/$id', params: { id: workshopId } })
    } else {
      void navigate({ to: '/workshops' })
    }
  }

  const { theme } = config

  return (
    <aside
      className="shrink-0 h-full flex flex-col"
      style={{
        width: config.sidebar_width,
        backgroundColor: theme?.sidebar_bg || '#15100b',
      }}
    >
      {/* Back link */}
      <button
        onClick={handleBack}
        className="flex items-center gap-1.5 px-3.5 py-2.5 text-[11px] cursor-pointer border-b transition-colors"
        style={{
          color: 'rgba(255,255,255,0.3)',
          borderColor: 'rgba(255,255,255,0.06)',
        }}
      >
        <ArrowLeft size={11} />
        <span className="truncate">{workshopName}</span>
      </button>

      {/* Branding */}
      <div className="px-3.5 pt-4 pb-3" style={{ borderBottom: '0.5px solid rgba(255,255,255,0.06)' }}>
        <div
          className="text-[23px] leading-none"
          style={{
            fontFamily: "'Cormorant Garamond', Georgia, serif",
            color: theme?.sidebar_text || '#eddec8',
            letterSpacing: '0.02em',
          }}
        >
          {config.title}
        </div>
        {config.subtitle && (
          <div
            className="text-[10px] mt-1"
            style={{
              letterSpacing: '0.1em',
              color: 'rgba(255,255,255,0.2)',
            }}
          >
            {config.subtitle}
          </div>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex-1 overflow-y-auto py-2 px-1.5 space-y-0.5">
        {config.nav_items.map((item) => (
          <AppNavLink key={item.id} item={item} theme={theme} />
        ))}
      </nav>
    </aside>
  )
}
