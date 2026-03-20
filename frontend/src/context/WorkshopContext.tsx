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

async function fetchWorkshopData(id: string): Promise<{ nav: NavItem[]; modules: string[]; workshop: Workshop }> {
  const [navData, modulesData, workshop] = await Promise.all([
    apiGet<WorkshopNav>(`/api/workshops/${id}/nav`),
    apiGet<WorkshopModule[]>(`/api/workshops/${id}/modules`),
    apiGet<Workshop>(`/api/workshops/${id}`),
  ])
  return {
    nav: navData.items,
    modules: modulesData.filter((m) => m.enabled).map((m) => m.module_name),
    workshop,
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

  // Sync from the backend active workshop on initial load and after remount.
  // Tracks which workshop ID was last synced — on remount the ref resets to
  // null so the effect re-fires and restores state from the query cache.
  const lastSyncedId = useRef<string | null | undefined>(undefined)

  useEffect(() => {
    if (isLoadingInitial) return

    const targetId = initialWorkshop?.id ?? null

    // Already synced to this workshop (and component hasn't remounted)
    if (lastSyncedId.current === targetId) return
    lastSyncedId.current = targetId

    if (!initialWorkshop) {
      setActiveWorkshop(null)
      setWorkshopModules([])
      setWorkshopNav(SHELL_NAV_DEFAULTS)
      return
    }

    setActiveWorkshop(initialWorkshop)
    void fetchWorkshopData(initialWorkshop.id)
      .then(({ nav, modules }) => {
        setWorkshopNav(nav)
        setWorkshopModules(modules)
      })
      .catch(() => {
        // Keep current state on transient error — don't reset to defaults
      })
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

      // Update the sync ref so the useEffect doesn't redundantly re-fetch
      lastSyncedId.current = id

      if (!id) {
        setActiveWorkshop(null)
        setWorkshopModules([])
        setWorkshopNav(SHELL_NAV_DEFAULTS)
        void navigate({ to: '/workshops', search: {} })
        return
      }

      // Optimistically set from cached workshop list if available.
      // Only apply if found — never set null optimistically (list may not be loaded yet).
      const ws = workshopList?.items.find((w) => w.id === id)
      if (ws) setActiveWorkshop(ws)

      // Fetch nav, modules, and the workshop itself, then navigate to its home.
      // setActiveWorkshop from the API response ensures it's always set correctly,
      // even when workshopList hasn't loaded (e.g. direct URL navigation).
      void fetchWorkshopData(id)
        .then(({ nav, modules, workshop }) => {
          setActiveWorkshop(workshop)
          setWorkshopNav(nav)
          setWorkshopModules(modules)
          void navigate({ to: '/workshop/$id', params: { id } })
        })
        .catch(() => {
          // Revert optimistic state on failure
          lastSyncedId.current = undefined
          setActiveWorkshop(null)
          setWorkshopModules([])
          setWorkshopNav(SHELL_NAV_DEFAULTS)
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
