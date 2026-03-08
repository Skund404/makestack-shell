/**
 * Hooks for package and registry management.
 * Wraps /api/packages/* and /api/registries/* endpoints.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, ApiError } from '@/lib/api'
import type { InstalledPackage, PackageSearchResult, InstallResult, RegistryRecord } from '@/lib/types'

const PKGS_KEY = ['packages']
const REGS_KEY = ['registries']

// ---------------------------------------------------------------------------
// Helpers — typed delete (apiDelete discards body)
// ---------------------------------------------------------------------------

async function apiDeleteJson<T>(path: string): Promise<T> {
  const res = await fetch(path, { method: 'DELETE' })
  if (!res.ok) {
    let detail: unknown
    try { detail = await res.json() } catch { detail = null }
    const message =
      typeof detail === 'object' && detail !== null && 'error' in detail
        ? String((detail as Record<string, unknown>).error)
        : `HTTP ${res.status}`
    throw new ApiError(res.status, message, detail)
  }
  return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Installed packages
// ---------------------------------------------------------------------------

export interface PackageListResponse {
  items: InstalledPackage[]
  total: number
  limit: number
  offset: number
}

export function usePackageList() {
  return useQuery<PackageListResponse>({
    queryKey: PKGS_KEY,
    queryFn: () => apiGet<PackageListResponse>('/api/packages'),
  })
}

// ---------------------------------------------------------------------------
// Registry search
// ---------------------------------------------------------------------------

export interface PackageSearchResponse {
  items: PackageSearchResult[]
  total: number
  query: string
}

export function usePackageSearch(q: string) {
  return useQuery<PackageSearchResponse>({
    queryKey: ['packages', 'search', q],
    queryFn: () => apiGet<PackageSearchResponse>('/api/packages/search', { q }),
    enabled: true,
    staleTime: 30_000,
  })
}

// ---------------------------------------------------------------------------
// Install / uninstall / update
// ---------------------------------------------------------------------------

export interface InstallRequest {
  name?: string
  source?: string
  version?: string
}

export function useInstallPackage() {
  const qc = useQueryClient()
  return useMutation<InstallResult, ApiError, InstallRequest>({
    mutationFn: (body) => apiPost<InstallResult>('/api/packages/install', body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: PKGS_KEY })
    },
  })
}

export function useUninstallPackage() {
  const qc = useQueryClient()
  return useMutation<InstallResult, ApiError, string>({
    mutationFn: (name) => apiDeleteJson<InstallResult>(`/api/packages/${encodeURIComponent(name)}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: PKGS_KEY })
    },
  })
}

export function useUpdatePackage() {
  const qc = useQueryClient()
  return useMutation<InstallResult, ApiError, { name: string; version?: string }>({
    mutationFn: ({ name, version }) =>
      apiPost<InstallResult>(`/api/packages/${encodeURIComponent(name)}/update`, version ? { version } : {}),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: PKGS_KEY })
    },
  })
}

// ---------------------------------------------------------------------------
// Registries
// ---------------------------------------------------------------------------

export interface RegistryListResponse {
  items: RegistryRecord[]
  total: number
}

export function useRegistries() {
  return useQuery<RegistryListResponse>({
    queryKey: REGS_KEY,
    queryFn: () => apiGet<RegistryListResponse>('/api/registries'),
  })
}

export function useAddRegistry() {
  const qc = useQueryClient()
  return useMutation<RegistryRecord, ApiError, { name: string; git_url: string }>({
    mutationFn: (body) => apiPost<RegistryRecord>('/api/registries', body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: REGS_KEY })
    },
  })
}

export function useRemoveRegistry() {
  const qc = useQueryClient()
  return useMutation<{ removed: string }, ApiError, string>({
    mutationFn: (name) => apiDeleteJson<{ removed: string }>(`/api/registries/${encodeURIComponent(name)}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: REGS_KEY })
    },
  })
}

export function useRefreshRegistries() {
  const qc = useQueryClient()
  return useMutation<{ refreshed: string[]; errors: Record<string, string> }, ApiError, void>({
    mutationFn: () =>
      apiPost<{ refreshed: string[]; errors: Record<string, string> }>('/api/registries/refresh', {}),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: REGS_KEY })
      void qc.invalidateQueries({ queryKey: ['packages', 'search'] })
    },
  })
}
