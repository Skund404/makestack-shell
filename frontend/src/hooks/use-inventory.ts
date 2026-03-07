import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiDelete, apiGet, apiPost, apiPut } from '@/lib/api'
import type { InventoryItem, InventoryItemWithCatalogue, PaginatedList } from '@/lib/types'

const INV_LIST_KEY = 'inventory-list'
const INV_ITEM_KEY = 'inventory-item'
const INV_STALE_KEY = 'inventory-stale'

export function useInventoryList(workshopId?: string, type?: string, limit = 50, offset = 0) {
  return useQuery({
    queryKey: [INV_LIST_KEY, workshopId, type, limit, offset],
    queryFn: () =>
      apiGet<PaginatedList<InventoryItem>>('/api/inventory', {
        workshop_id: workshopId,
        type,
        limit,
        offset,
      }),
  })
}

export function useInventoryItem(id: string) {
  return useQuery({
    queryKey: [INV_ITEM_KEY, id],
    queryFn: () => apiGet<InventoryItemWithCatalogue>(`/api/inventory/${id}`),
    enabled: Boolean(id),
  })
}

export function useStaleItems() {
  return useQuery({
    queryKey: [INV_STALE_KEY],
    queryFn: () => apiGet<PaginatedList<InventoryItemWithCatalogue>>('/api/inventory/stale'),
  })
}

export function useAddToInventory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { catalogue_path: string; workshop_id?: string | null }) =>
      apiPost<InventoryItem>('/api/inventory', data),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [INV_LIST_KEY] })
      void qc.invalidateQueries({ queryKey: [INV_STALE_KEY] })
    },
  })
}

export function useUpdateInventoryItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string
      data: { workshop_id?: string | null; catalogue_hash?: string }
    }) => apiPut<InventoryItem>(`/api/inventory/${id}`, data),
    onSuccess: (_result, { id }) => {
      void qc.invalidateQueries({ queryKey: [INV_LIST_KEY] })
      void qc.invalidateQueries({ queryKey: [INV_ITEM_KEY, id] })
      void qc.invalidateQueries({ queryKey: [INV_STALE_KEY] })
    },
  })
}

export function useRemoveFromInventory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiDelete(`/api/inventory/${id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [INV_LIST_KEY] })
      void qc.invalidateQueries({ queryKey: [INV_STALE_KEY] })
    },
  })
}
