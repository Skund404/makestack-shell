import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiDelete, apiGet, apiPost, apiPut } from '@/lib/api'
import type { PaginatedList, Primitive, PrimitiveCreate, PrimitiveUpdate, Relationship } from '@/lib/types'

const PRIMITIVE_LIST_KEY = 'primitives'
const PRIMITIVE_KEY = 'primitive'
const SEARCH_KEY = 'catalogue-search'
const RELATIONSHIPS_KEY = 'relationships'

export function usePrimitiveList(type?: string, limit = 50, offset = 0) {
  return useQuery({
    queryKey: [PRIMITIVE_LIST_KEY, type, limit, offset],
    queryFn: () =>
      apiGet<PaginatedList<Primitive>>('/api/catalogue/primitives', {
        type,
        limit,
        offset,
      }),
  })
}

export function usePrimitive(path: string, at?: string) {
  return useQuery({
    queryKey: [PRIMITIVE_KEY, path, at],
    queryFn: () =>
      apiGet<Primitive>(`/api/catalogue/primitives/${path}`, at ? { at } : undefined),
    enabled: Boolean(path),
  })
}

export function useSearch(query: string, enabled = true) {
  return useQuery({
    queryKey: [SEARCH_KEY, query],
    queryFn: () =>
      apiGet<PaginatedList<Primitive>>('/api/catalogue/search', { q: query }),
    enabled: enabled && query.trim().length > 0,
  })
}

export function useRelationships(path: string) {
  return useQuery({
    queryKey: [RELATIONSHIPS_KEY, path],
    queryFn: () =>
      apiGet<Relationship[]>(`/api/catalogue/relationships/${path}`),
    enabled: Boolean(path),
  })
}

export function useCreatePrimitive() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: PrimitiveCreate) =>
      apiPost<Primitive>('/api/catalogue/primitives', data),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [PRIMITIVE_LIST_KEY] })
    },
  })
}

export function useUpdatePrimitive() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ path, data }: { path: string; data: PrimitiveUpdate }) =>
      apiPut<Primitive>(`/api/catalogue/primitives/${path}`, data),
    onSuccess: (_result, { path }) => {
      void qc.invalidateQueries({ queryKey: [PRIMITIVE_LIST_KEY] })
      void qc.invalidateQueries({ queryKey: [PRIMITIVE_KEY, path] })
    },
  })
}

export function useDeletePrimitive() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (path: string) =>
      apiDelete(`/api/catalogue/primitives/${path}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [PRIMITIVE_LIST_KEY] })
    },
  })
}
