import {
  Box,
  BookOpen,
  Cog,
  Database,
  FlaskConical,
  Folder,
  GitFork,
  Hammer,
  Layers,
  Package,
  LayoutGrid,
  Search,
  Terminal,
  Wrench,
} from 'lucide-react'
import { Link, useLocation } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { cn } from '@/lib/utils'
import { Tooltip } from '@/components/ui/Tooltip'
import { useStaleItems } from '@/hooks/use-inventory'
import { useActiveWorkshop } from '@/hooks/use-workshops'
import { apiGet } from '@/lib/api'

interface NavItem {
  to: string
  label: string
  icon: React.ReactNode
  search?: Record<string, string>
  disabled?: boolean
  disabledReason?: string
}

const CATALOGUE_ITEMS: NavItem[] = [
  { to: '/catalogue', label: 'All Primitives', icon: <LayoutGrid size={14} /> },
  { to: '/catalogue', label: 'Tools',          icon: <Wrench size={14} />,     search: { type: 'tool' } },
  { to: '/catalogue', label: 'Materials',      icon: <Package size={14} />,    search: { type: 'material' } },
  { to: '/catalogue', label: 'Techniques',     icon: <BookOpen size={14} />,   search: { type: 'technique' } },
  { to: '/catalogue', label: 'Workflows',      icon: <GitFork size={14} />,    search: { type: 'workflow' } },
  { to: '/catalogue', label: 'Projects',       icon: <Folder size={14} />,     search: { type: 'project' } },
  { to: '/catalogue', label: 'Events',         icon: <Layers size={14} />,     search: { type: 'event' } },
  { to: '/catalogue/search', label: 'Search',  icon: <Search size={14} /> },
]

const PERSONAL_BASE_ITEMS: NavItem[] = [
  { to: '/inventory', label: 'Inventory', icon: <Box size={14} /> },
  { to: '/workshops', label: 'Workshops', icon: <FlaskConical size={14} /> },
]

const SYSTEM_ITEMS: NavItem[] = [
  { to: '/settings', label: 'Settings', icon: <Cog size={14} /> },
  { to: '/packages', label: 'Packages',  icon: <Package size={14} /> },
]

const DEV_ITEMS: NavItem[] = [
  { to: '/dev/keywords', label: 'Keywords',  icon: <Terminal size={14} /> },
  { to: '/dev/schema',   label: 'Schema',    icon: <Database size={14} /> },
  { to: '/dev/modules',  label: 'Modules',   icon: <Package size={14} /> },
]

function NavLink({ item, badge }: { item: NavItem; badge?: React.ReactNode }) {
  const loc = useLocation()
  const isActive = loc.pathname === item.to

  const inner = (
    <span
      className={cn(
        'flex items-center gap-2.5 px-3 py-1.5 rounded text-xs transition-colors w-full',
        item.disabled
          ? 'text-text-faint cursor-default opacity-50'
          : isActive
            ? 'bg-accent/10 text-accent border border-accent/20'
            : 'text-text-muted hover:bg-surface-el hover:text-text',
      )}
    >
      {item.icon}
      <span className="flex-1">{item.label}</span>
      {badge}
    </span>
  )

  if (item.disabled) {
    return item.disabledReason ? (
      <Tooltip content={item.disabledReason} side="right">
        <span className="block">{inner}</span>
      </Tooltip>
    ) : (
      <span className="block">{inner}</span>
    )
  }

  return (
    <Link
      to={item.to}
      search={item.search as never}
      className="block"
    >
      {inner}
    </Link>
  )
}

function NavSection({
  label,
  items,
  footer,
}: {
  label: string
  items: NavItem[]
  footer?: React.ReactNode
}) {
  return (
    <div>
      <p className="px-3 py-1 text-[10px] font-semibold uppercase tracking-widest text-text-faint mb-0.5">
        {label}
      </p>
      <div className="space-y-0.5">
        {items.map((item) => (
          <NavLink key={`${item.to}-${item.label}`} item={item} />
        ))}
      </div>
      {footer}
    </div>
  )
}

function PersonalSection() {
  const { data: staleData } = useStaleItems()
  const { data: activeWorkshop } = useActiveWorkshop()

  const staleCount = staleData?.total ?? 0

  const inventoryBadge =
    staleCount > 0 ? (
      <span className="text-[10px] bg-warning/15 text-warning rounded px-1 font-medium">
        {staleCount}
      </span>
    ) : undefined

  return (
    <div>
      <p className="px-3 py-1 text-[10px] font-semibold uppercase tracking-widest text-text-faint mb-0.5">
        Personal
      </p>
      <div className="space-y-0.5">
        {PERSONAL_BASE_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            item={item}
            badge={item.to === '/inventory' ? inventoryBadge : undefined}
          />
        ))}
      </div>
      {activeWorkshop && (
        <p className="px-3 pt-1.5 text-[10px] text-text-faint truncate">
          Active: <span className="text-text-muted">{activeWorkshop.name}</span>
        </p>
      )}
    </div>
  )
}

function DevSection() {
  const { data } = useQuery<{ dev_mode: boolean }>({
    queryKey: ['status'],
    queryFn: () => apiGet<{ dev_mode: boolean }>('/api/status'),
    select: (d: Record<string, unknown>) => ({ dev_mode: Boolean((d as Record<string, unknown>).dev_mode) }),
    staleTime: 60_000,
  })

  // Show dev section only when backend reports dev mode. Falls back gracefully.
  const isDevMode = (data as { dev_mode?: boolean } | undefined)?.dev_mode ?? false
  if (!isDevMode) return null

  return (
    <NavSection
      label="Dev Tools"
      items={DEV_ITEMS}
    />
  )
}

export function Sidebar() {
  return (
    <aside className="w-52 shrink-0 h-full border-r border-border bg-bg-secondary flex flex-col">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-border">
        <div className="flex items-center gap-2">
          <Hammer size={16} className="text-accent" />
          <span className="text-sm font-semibold text-text tracking-tight">Makestack</span>
        </div>
        <p className="text-xs text-text-faint mt-0.5">Maker's toolkit</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-4">
        <NavSection label="Catalogue" items={CATALOGUE_ITEMS} />
        <PersonalSection />
        <NavSection label="System" items={SYSTEM_ITEMS} />
        <DevSection />
      </nav>
    </aside>
  )
}
