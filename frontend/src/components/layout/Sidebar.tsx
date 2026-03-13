import {
  Blocks,
  BookOpen,
  Box,
  ChevronRight,
  Cog,
  Cpu,
  Database,
  FlaskConical,
  Folder,
  GitFork,
  Globe,
  Hammer,
  Layers,
  LayoutGrid,
  Package,
  Puzzle,
  Search,
  ShieldCheck,
  Star,
  Tag,
  Terminal,
  Wrench,
  X,
  Zap,
  type LucideIcon,
} from 'lucide-react'
import { Link, useLocation } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { cn } from '@/lib/utils'
import { Tooltip } from '@/components/ui/Tooltip'
import { useStaleItems } from '@/hooks/use-inventory'
import { useWorkshopContext } from '@/context/WorkshopContext'
import { apiGet } from '@/lib/api'
import type { NavItem as ContextNavItem } from '@/lib/types'

// ---------------------------------------------------------------------------
// Icon resolution — maps nav item icon strings to Lucide components
// ---------------------------------------------------------------------------

const ICON_MAP: Record<string, LucideIcon> = {
  package:       Package,
  box:           Box,
  book:          BookOpen,
  layers:        Layers,
  folder:        Folder,
  search:        Search,
  cog:           Cog,
  wrench:        Wrench,
  terminal:      Terminal,
  database:      Database,
  'layout-grid': LayoutGrid,
  'git-fork':    GitFork,
  hammer:        Hammer,
  blocks:        Blocks,
  puzzle:        Puzzle,
  star:          Star,
  tag:           Tag,
  zap:           Zap,
  cpu:           Cpu,
  globe:         Globe,
  shield:        ShieldCheck,
}

/** Resolve a Lucide icon name string → rendered icon node. Falls back to Box. */
function resolveIcon(name: string): React.ReactNode {
  const Icon = ICON_MAP[name?.toLowerCase() ?? ''] ?? Box
  return <Icon size={14} />
}

// ---------------------------------------------------------------------------
// Internal sidebar item shape (distinct from the context NavItem type)
// ---------------------------------------------------------------------------

interface SidebarItem {
  to: string
  label: string
  icon: React.ReactNode
  search?: Record<string, string>
  disabled?: boolean
  disabledReason?: string
}

// ---------------------------------------------------------------------------
// Static item lists
// ---------------------------------------------------------------------------

const CATALOGUE_ITEMS: SidebarItem[] = [
  { to: '/catalogue', label: 'All Primitives', icon: <LayoutGrid size={14} /> },
  { to: '/catalogue', label: 'Tools',          icon: <Wrench size={14} />,     search: { type: 'tool' } },
  { to: '/catalogue', label: 'Materials',      icon: <Package size={14} />,    search: { type: 'material' } },
  { to: '/catalogue', label: 'Techniques',     icon: <BookOpen size={14} />,   search: { type: 'technique' } },
  { to: '/catalogue', label: 'Workflows',      icon: <GitFork size={14} />,    search: { type: 'workflow' } },
  { to: '/catalogue', label: 'Projects',       icon: <Folder size={14} />,     search: { type: 'project' } },
  { to: '/catalogue', label: 'Events',         icon: <Layers size={14} />,     search: { type: 'event' } },
  { to: '/catalogue/search', label: 'Search',  icon: <Search size={14} /> },
]

const SYSTEM_ITEMS: SidebarItem[] = [
  { to: '/settings', label: 'Settings', icon: <Cog size={14} /> },
  { to: '/packages', label: 'Packages', icon: <Package size={14} /> },
]

const DEV_ITEMS: SidebarItem[] = [
  { to: '/dev/keywords', label: 'Keywords', icon: <Terminal size={14} /> },
  { to: '/dev/schema',   label: 'Schema',   icon: <Database size={14} /> },
  { to: '/dev/modules',  label: 'Modules',  icon: <Package size={14} /> },
]

// ---------------------------------------------------------------------------
// NavLink — renders a single sidebar link with active state
// ---------------------------------------------------------------------------

function NavLink({ item, badge }: { item: SidebarItem; badge?: React.ReactNode }) {
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
    <Link to={item.to} search={item.search as never} className="block">
      {inner}
    </Link>
  )
}

// ---------------------------------------------------------------------------
// Section label — two visual modes: standard and dimmed (shell layer)
// ---------------------------------------------------------------------------

function SectionLabel({ children, dimmed }: { children: React.ReactNode; dimmed?: boolean }) {
  return (
    <p
      className={cn(
        'px-3 py-1 uppercase tracking-widest mb-0.5',
        dimmed
          ? 'text-[9px] text-text-faint/50 font-medium'
          : 'text-[10px] font-semibold text-text-faint',
      )}
    >
      {children}
    </p>
  )
}

// ---------------------------------------------------------------------------
// Section — label + list of NavLinks
// ---------------------------------------------------------------------------

function NavSection({
  label,
  items,
  dimmed,
  footer,
}: {
  label: string
  items: SidebarItem[]
  dimmed?: boolean
  footer?: React.ReactNode
}) {
  return (
    <div>
      <SectionLabel dimmed={dimmed}>{label}</SectionLabel>
      <div className="space-y-0.5">
        {items.map((item) => (
          <NavLink key={`${item.to}-${item.label}`} item={item} />
        ))}
      </div>
      {footer}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Section 1 — Workshop header
// ---------------------------------------------------------------------------

function WorkshopSection() {
  const { activeWorkshop, switchWorkshop } = useWorkshopContext()
  if (!activeWorkshop) return null

  return (
    <div>
      <SectionLabel>Workshop</SectionLabel>
      <div className="px-3 py-1.5 flex items-center gap-1.5">
        <span className="flex-1 text-xs text-text font-medium truncate">
          {activeWorkshop.name}
        </span>
        <button
          onClick={() => switchWorkshop(null)}
          className="shrink-0 text-text-faint hover:text-text transition-colors rounded p-0.5"
          title="Clear active workshop"
          aria-label="Clear active workshop"
        >
          <X size={11} />
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Section 2 — Module views (source = 'module' from workshopNav)
// ---------------------------------------------------------------------------

function ModuleViewsSection({ items }: { items: ContextNavItem[] }) {
  const loc = useLocation()

  return (
    <div>
      <SectionLabel>Modules</SectionLabel>
      <div className="space-y-0.5">
        {items.map((item) => {
          const isActive = loc.pathname === item.route
          return (
            <Link key={item.id} to={item.route as never} className="block">
              <span
                className={cn(
                  'flex items-center gap-2.5 px-3 py-1.5 rounded text-xs transition-colors w-full',
                  isActive
                    ? 'bg-accent/10 text-accent border border-accent/20'
                    : 'text-text-muted hover:bg-surface-el hover:text-text',
                )}
              >
                {resolveIcon(item.icon)}
                <span className="flex-1 truncate">{item.label}</span>
                {item.replaces_shell_view && (
                  <ChevronRight size={10} className="shrink-0 opacity-40" />
                )}
              </span>
            </Link>
          )
        })}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Dev section — conditional on dev mode flag from /api/status
// ---------------------------------------------------------------------------

function DevSection({ dimmed }: { dimmed?: boolean }) {
  const { data } = useQuery({
    queryKey: ['status'],
    queryFn: () => apiGet<{ dev_mode: boolean }>('/api/status'),
    select: (d: Record<string, unknown>) => ({ dev_mode: Boolean(d.dev_mode) }),
    staleTime: 60_000,
  })

  if (!data?.dev_mode) return null

  return <NavSection label="Dev Tools" items={DEV_ITEMS} dimmed={dimmed} />
}

// ---------------------------------------------------------------------------
// Section 3 — Shell layer
//
// Always present. Visually dimmed when module views are active.
// Catalogue expands fully when not dimmed; collapses to a single link when dimmed.
// Shell items that have a module replacement get a subtle indicator.
// ---------------------------------------------------------------------------

function ShellLayer({
  dimmed,
  replacedViews,
}: {
  dimmed: boolean
  /** Shell view ids claimed by loaded module views (used for visual indicator). */
  replacedViews: Set<string>
}) {
  const { data: staleData } = useStaleItems()
  const staleCount = staleData?.total ?? 0

  const inventoryBadge =
    staleCount > 0 ? (
      <span className="text-[10px] bg-warning/15 text-warning rounded px-1 font-medium">
        {staleCount}
      </span>
    ) : undefined

  const inventoryItem: SidebarItem = {
    to: '/inventory',
    label: 'Inventory',
    icon: <Box size={14} className={replacedViews.has('inventory') ? 'opacity-50' : undefined} />,
  }

  const workshopsItem: SidebarItem = {
    to: '/workshops',
    label: 'Workshops',
    icon: <FlaskConical size={14} className={replacedViews.has('workshops') ? 'opacity-50' : undefined} />,
  }

  const catalogueSingleItem: SidebarItem = {
    to: '/catalogue',
    label: 'Catalogue',
    icon: <LayoutGrid size={14} className={replacedViews.has('catalogue') ? 'opacity-50' : undefined} />,
  }

  return (
    <div className="space-y-4">
      {/* Catalogue — full sub-items when not dimmed, single link when dimmed */}
      {dimmed ? (
        <div>
          <SectionLabel dimmed>Catalogue</SectionLabel>
          <div className="space-y-0.5">
            <NavLink item={catalogueSingleItem} />
          </div>
        </div>
      ) : (
        <NavSection label="Catalogue" items={CATALOGUE_ITEMS} />
      )}

      {/* Personal shell views — Inventory + Workshops */}
      <div>
        <SectionLabel dimmed={dimmed}>Personal</SectionLabel>
        <div className="space-y-0.5">
          <NavLink item={inventoryItem} badge={inventoryBadge} />
          <NavLink item={workshopsItem} />
        </div>
      </div>

      {/* System */}
      <NavSection label="System" items={SYSTEM_ITEMS} dimmed={dimmed} />

      {/* Dev tools */}
      <DevSection dimmed={dimmed} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Root Sidebar
// ---------------------------------------------------------------------------

export function Sidebar() {
  const { workshopNav, activeWorkshop } = useWorkshopContext()

  const moduleItems = workshopNav.filter((n) => n.source === 'module')
  const hasModuleViews = moduleItems.length > 0

  // Collect shell view ids that are claimed (replaced) by a module view.
  const replacedViews = new Set(
    moduleItems
      .map((n) => n.replaces_shell_view)
      .filter((v): v is string => v !== null),
  )

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
        {/* 1. Workshop header */}
        {activeWorkshop && <WorkshopSection />}

        {/* 2. Module views — only when a workshop has loaded module views */}
        {hasModuleViews && <ModuleViewsSection items={moduleItems} />}

        {/* Divider when shell layer is demoted */}
        {hasModuleViews && (
          <div className="mx-3 border-t border-border/40" />
        )}

        {/* 3. Shell layer — always present */}
        <ShellLayer dimmed={hasModuleViews} replacedViews={replacedViews} />
      </nav>
    </aside>
  )
}
