import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiDelete, apiGet, apiPost, apiPut } from '@/lib/api'
import type {
  PaginatedList,
  Workshop,
  WorkshopCreate,
  WorkshopMember,
  WorkshopUpdate,
  WorkshopWithMembers,
} from '@/lib/types'

const WS_LIST_KEY = 'workshop-list'
const WS_KEY = 'workshop'
const WS_ACTIVE_KEY = 'workshop-active'

export function useWorkshopList() {
  return useQuery({
    queryKey: [WS_LIST_KEY],
    queryFn: () => apiGet<PaginatedList<Workshop>>('/api/workshops'),
  })
}

export function useWorkshop(id: string) {
  return useQuery({
    queryKey: [WS_KEY, id],
    queryFn: () => apiGet<WorkshopWithMembers>(`/api/workshops/${id}`),
    enabled: Boolean(id),
  })
}

export function useActiveWorkshop() {
  return useQuery({
    queryKey: [WS_ACTIVE_KEY],
    queryFn: async () => {
      const settings = await apiGet<{ preferences: Record<string, unknown> }>('/api/settings')
      const activeId = settings.preferences.active_workshop_id as string | null | undefined
      if (!activeId) return null
      try {
        return await apiGet<WorkshopWithMembers>(`/api/workshops/${activeId}`)
      } catch {
        return null
      }
    },
  })
}

export function useCreateWorkshop() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: WorkshopCreate) => apiPost<Workshop>('/api/workshops', data),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [WS_LIST_KEY] })
    },
  })
}

export function useUpdateWorkshop() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: WorkshopUpdate }) =>
      apiPut<Workshop>(`/api/workshops/${id}`, data),
    onSuccess: (_result, { id }) => {
      void qc.invalidateQueries({ queryKey: [WS_LIST_KEY] })
      void qc.invalidateQueries({ queryKey: [WS_KEY, id] })
    },
  })
}

export function useDeleteWorkshop() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiDelete(`/api/workshops/${id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [WS_LIST_KEY] })
      void qc.invalidateQueries({ queryKey: [WS_ACTIVE_KEY] })
    },
  })
}

export function useAddToWorkshop() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      workshopId,
      primitive_path,
      primitive_type,
    }: {
      workshopId: string
      primitive_path: string
      primitive_type: string
    }) =>
      apiPost<WorkshopMember>(`/api/workshops/${workshopId}/members`, {
        primitive_path,
        primitive_type,
      }),
    onSuccess: (_result, { workshopId }) => {
      void qc.invalidateQueries({ queryKey: [WS_KEY, workshopId] })
    },
  })
}

export function useRemoveFromWorkshop() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ workshopId, primitivePath }: { workshopId: string; primitivePath: string }) =>
      apiDelete(`/api/workshops/${workshopId}/members/${primitivePath}`),
    onSuccess: (_result, { workshopId }) => {
      void qc.invalidateQueries({ queryKey: [WS_KEY, workshopId] })
    },
  })
}

export function useSetActiveWorkshop() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (workshopId: string | null) =>
      apiPut<{ active_workshop_id: string | null }>('/api/workshops/active', {
        workshop_id: workshopId,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [WS_ACTIVE_KEY] })
    },
  })
}
