import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiDelete, apiGet, apiPatch, apiPost } from '@/lib/api'
import type { InstalledModule, PaginatedList, WorkshopModule } from '@/lib/types'

// ---------------------------------------------------------------------------
// Workshop-module associations
// ---------------------------------------------------------------------------

export function useWorkshopModuleList(workshopId: string) {
  return useQuery({
    queryKey: ['workshop-modules', workshopId],
    queryFn: () => apiGet<WorkshopModule[]>(`/api/workshops/${workshopId}/modules`),
    enabled: Boolean(workshopId),
  })
}

export function useAddWorkshopModule(workshopId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ module_name, sort_order }: { module_name: string; sort_order?: number }) =>
      apiPost<WorkshopModule>(`/api/workshops/${workshopId}/modules`, {
        module_name,
        sort_order: sort_order ?? 0,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['workshop-modules', workshopId] })
      void qc.invalidateQueries({ queryKey: ['workshop-nav', workshopId] })
    },
  })
}

export function useRemoveWorkshopModule(workshopId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (module_name: string) =>
      apiDelete(`/api/workshops/${workshopId}/modules/${module_name}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['workshop-modules', workshopId] })
      void qc.invalidateQueries({ queryKey: ['workshop-nav', workshopId] })
    },
  })
}

export function useUpdateWorkshopModuleSortOrder(workshopId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ module_name, sort_order }: { module_name: string; sort_order: number }) =>
      apiPatch<WorkshopModule>(`/api/workshops/${workshopId}/modules/${module_name}`, { sort_order }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['workshop-modules', workshopId] })
    },
  })
}

// ---------------------------------------------------------------------------
// All installed modules (for "add module" picker)
// ---------------------------------------------------------------------------

export function useInstalledModules() {
  return useQuery({
    queryKey: ['installed-modules'],
    queryFn: () => apiGet<PaginatedList<InstalledModule>>('/api/modules'),
    staleTime: 30_000,
  })
}
