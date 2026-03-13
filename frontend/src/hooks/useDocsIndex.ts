/**
 * useDocsIndex — composed docs index for DocsPanel (9E).
 *
 * Two sources:
 *   1. GET /api/terminal/docs → { api: Capability[], commands: CliCommand[] }
 *      (backend-owned — API operations + CLI keyword table)
 *   2. KeywordRegistry.getAll() → WidgetMeta[]
 *      (frontend-owned — widget metadata, never sent to backend)
 *
 * The two sources are combined client-side. The backend never returns widget data.
 */
import { useQuery } from '@tanstack/react-query'
import { getAll } from '@/modules/keyword-resolver'
import type { WidgetMeta } from '@/modules/keyword-resolver'

// ---------------------------------------------------------------------------
// Types matching GET /api/terminal/docs response
// ---------------------------------------------------------------------------

export interface Capability {
  method: string
  path: string
  summary: string
  tags: string[]
}

export interface CliCommand {
  keyword: string
  method: string
  path: string
  description: string
  accepts_arg: boolean
}

interface DocsApiResponse {
  api: Capability[]
  commands: CliCommand[]
}

// ---------------------------------------------------------------------------
// Composed index type returned by the hook
// ---------------------------------------------------------------------------

export interface DocsIndex {
  /** All Shell API operations from GET /api/capabilities. */
  api: Capability[]
  /** CLI keyword → HTTP translation table (backend-owned). */
  commands: CliCommand[]
  /** Widget entries (frontend-owned, from KeywordRegistry). */
  widgets: WidgetMeta[]
  isLoading: boolean
  isError: boolean
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

async function fetchDocsApi(): Promise<DocsApiResponse> {
  const res = await fetch('/api/terminal/docs')
  if (!res.ok) throw new Error(`docs fetch failed: ${res.status}`)
  return res.json() as Promise<DocsApiResponse>
}

export function useDocsIndex(): DocsIndex {
  const { data, isLoading, isError } = useQuery<DocsApiResponse>({
    queryKey: ['terminal', 'docs'],
    queryFn: fetchDocsApi,
    staleTime: 5 * 60 * 1000, // 5 min — capabilities rarely change at runtime
  })

  return {
    api: data?.api ?? [],
    commands: data?.commands ?? [],
    widgets: getAll(),
    isLoading,
    isError,
  }
}
