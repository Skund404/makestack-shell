import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@/lib/api'
import type { DiffResponse, HistoryResponse } from '@/lib/types'

export function usePrimitiveHistory(path: string, limit = 50, offset = 0) {
  return useQuery({
    queryKey: ['history', path, limit, offset],
    queryFn: () =>
      apiGet<HistoryResponse>(`/api/catalogue/primitives/${path}/history`, { limit, offset }),
    enabled: Boolean(path),
  })
}

export function usePrimitiveDiff(path: string, fromHash?: string, toHash?: string) {
  return useQuery({
    queryKey: ['diff', path, fromHash, toHash],
    queryFn: () =>
      apiGet<DiffResponse>(`/api/catalogue/primitives/${path}/diff`, {
        from: fromHash,
        to: toHash,
      }),
    enabled: Boolean(path),
  })
}
