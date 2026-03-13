/**
 * WorkshopContext — runtime state for the active workshop.
 *
 * Owns:
 *   activeWorkshop   — the currently selected workshop (or null for "All")
 *   workshopModules  — enabled module names for the active workshop (from DB)
 *   workshopNav      — computed nav items (intersection of DB + loaded registry)
 *   switchWorkshop   — change the active workshop; fetches nav + modules once
 *
 * Rules:
 *   - Workshop switch is a STATE CHANGE ONLY. Zero page reloads.
 *   - Nav fetch on context switch, not on every render.
 *   - Nav is cached in context state; only refetched when switchWorkshop is called.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { apiGet, apiPut } from '@/lib/api'
import { useActiveWorkshop, useWorkshopList } from '@/hooks/use-workshops'
import type { NavItem, Workshop, WorkshopModule, WorkshopNav } from '@/lib/types'

// ---------------------------------------------------------------------------
// Shell fallback nav — shown when no workshop is active
// ---------------------------------------------------------------------------

const SHELL_NAV_DEFAULTS: NavItem[] = [
  { id: 'inventory',  label: 'Inventory',  route: '/inventory',  icon: 'package', source: 'shell', replaces_shell_view: null },
  { id: 'catalogue',  label: 'Catalogue',  route: '/catalogue',  icon: 'book',    source: 'shell', replaces_shell_view: null },
  { id: 'workshops',  label: 'Workshops',  route: '/workshops',  icon: 'layers',  source: 'shell', replaces_shell_view: null },
]

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------

interface WorkshopContextValue {
  activeWorkshop: Workshop | null
  /** Enabled module names for the active workshop (from workshop_modules table). */
  workshopModules: string[]
  /** Computed nav items from GET /api/workshops/{id}/nav. */
  workshopNav: NavItem[]
  /** Switch active workshop. Fetches nav + modules; persists to backend. */
  switchWorkshop: (id: string | null) => void
}

const WorkshopContext = createContext<WorkshopContextValue>({
  activeWorkshop: null,
  workshopModules: [],
  workshopNav: SHELL_NAV_DEFAULTS,
  switchWorkshop: () => {},
})

// ---------------------------------------------------------------------------
// Data fetcher — called once per workshop switch
// ---------------------------------------------------------------------------

async function fetchWorkshopData(id: string): Promise<{ nav: NavItem[]; modules: string[] }> {
  const [navData, modulesData] = await Promise.all([
    apiGet<WorkshopNav>(`/api/workshops/${id}/nav`),
    apiGet<WorkshopModule[]>(`/api/workshops/${id}/modules`),
  ])
  return {
    nav: navData.items,
    modules: modulesData.filter((m) => m.enabled).map((m) => m.module_name),
  }
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function WorkshopContextProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const { data: initialWorkshop, isLoading: isLoadingInitial } = useActiveWorkshop()
  const { data: workshopList } = useWorkshopList()

  const [activeWorkshop, setActiveWorkshop] = useState<Workshop | null>(null)
  const [workshopModules, setWorkshopModules] = useState<string[]>([])
  const [workshopNav, setWorkshopNav] = useState<NavItem[]>(SHELL_NAV_DEFAULTS)

  // Sync from the backend active workshop exactly once on initial load.
  // After that, only switchWorkshop mutates context state.
  const syncedRef = useRef(false)

  useEffect(() => {
    if (syncedRef.current) return
    if (isLoadingInitial) return

    syncedRef.current = true

    if (initialWorkshop) {
      setActiveWorkshop(initialWorkshop)
      void fetchWorkshopData(initialWorkshop.id).then(({ nav, modules }) => {
        setWorkshopNav(nav)
        setWorkshopModules(modules)
      })
    }
    // No active workshop → keep SHELL_NAV_DEFAULTS (already the initial state)
  }, [isLoadingInitial, initialWorkshop])

  const switchWorkshop = useCallback(
    (id: string | null) => {
      // Persist to backend; invalidate the TanStack Query active-workshop cache
      // so components using useActiveWorkshop() stay in sync.
      void apiPut<{ active_workshop_id: string | null }>('/api/workshops/active', {
        workshop_id: id,
      }).then(() => {
        void qc.invalidateQueries({ queryKey: ['workshop-active'] })
      })

      if (!id) {
        setActiveWorkshop(null)
        setWorkshopModules([])
        setWorkshopNav(SHELL_NAV_DEFAULTS)
        void navigate({ to: '/workshops', search: {} })
        return
      }

      // Optimistically set from cached workshop list (user just picked from the list).
      const ws = workshopList?.items.find((w) => w.id === id) ?? null
      setActiveWorkshop(ws)

      // Fetch nav and modules for the selected workshop, then navigate to its home.
      void fetchWorkshopData(id).then(({ nav, modules }) => {
        setWorkshopNav(nav)
        setWorkshopModules(modules)
        void navigate({ to: '/workshop/$id', params: { id } })
      })
    },
    [qc, workshopList, navigate],
  )

  const value = useMemo<WorkshopContextValue>(
    () => ({ activeWorkshop, workshopModules, workshopNav, switchWorkshop }),
    [activeWorkshop, workshopModules, workshopNav, switchWorkshop],
  )

  return <WorkshopContext.Provider value={value}>{children}</WorkshopContext.Provider>
}

// ---------------------------------------------------------------------------
// Consumer hook
// ---------------------------------------------------------------------------

export function useWorkshopContext(): WorkshopContextValue {
  return useContext(WorkshopContext)
}
