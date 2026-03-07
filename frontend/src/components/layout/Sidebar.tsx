import {
  Box,
  BookOpen,
  Cog,
  FlaskConical,
  Folder,
  GitFork,
  Hammer,
  Layers,
  Package,
  LayoutGrid,
  Search,
  Wrench,
} from 'lucide-react'
import { Link, useLocation } from '@tanstack/react-router'
import { cn } from '@/lib/utils'
import { Tooltip } from '@/components/ui/Tooltip'

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

const PERSONAL_ITEMS: NavItem[] = [
  {
    to: '/inventory',
    label: 'Inventory',
    icon: <Box size={14} />,
    disabled: true,
    disabledReason: 'Phase 4',
  },
  {
    to: '/workshops',
    label: 'Workshops',
    icon: <FlaskConical size={14} />,
    disabled: true,
    disabledReason: 'Phase 4',
  },
]

const SYSTEM_ITEMS: NavItem[] = [
  { to: '/settings', label: 'Settings', icon: <Cog size={14} />, disabled: true, disabledReason: 'Phase 4' },
]

function NavLink({ item }: { item: NavItem }) {
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
      {item.label}
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

function NavSection({ label, items }: { label: string; items: NavItem[] }) {
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
    </div>
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
        <NavSection label="Personal" items={PERSONAL_ITEMS} />
        <NavSection label="System" items={SYSTEM_ITEMS} />
      </nav>
    </aside>
  )
}
