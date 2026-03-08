/**
 * Shell status polling hook.
 *
 * Polls GET /api/status every 30 seconds and exposes core connection state.
 * Components use this to show the connection indicator and stale data banner.
 */
import { useQuery } from '@tanstack/react-query'
import type { SystemStatus } from '@/lib/types'

export function useSystemStatus() {
  return useQuery<SystemStatus>({
    queryKey: ['system', 'status'],
    queryFn: async () => {
      const res = await fetch('/api/status')
      if (!res.ok) throw new Error(`Status fetch failed: ${res.status}`)
      return res.json()
    },
    // Poll every 30 seconds to track connection changes
    refetchInterval: 30_000,
    // Continue polling even when the window is not focused
    refetchIntervalInBackground: true,
    // Don't throw on error — we can still show the last known state
    retry: 1,
  })
}
