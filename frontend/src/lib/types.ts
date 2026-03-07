/**
 * TypeScript types matching the Shell REST API response shapes (Pydantic models).
 */

export interface Primitive {
  id: string
  type: string
  name: string
  slug: string
  path: string
  created: string
  modified: string
  description: string
  tags: string[]
  properties: Record<string, unknown> | null
  parent_project: string
  manifest: Record<string, unknown>
  commit_hash: string
}

export interface PaginatedList<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface Relationship {
  source_path: string
  source_type: string
  relationship_type: string
  target_path: string
  target_type: string
  metadata: Record<string, unknown> | null
}

export interface CommitInfo {
  hash: string
  message: string
  author: string
  timestamp: string
}

export interface HistoryResponse {
  path: string
  total: number
  commits: CommitInfo[]
}

export interface FieldChange {
  field: string
  type: 'added' | 'removed' | 'modified'
  old_value: unknown
  new_value: unknown
}

export interface DiffResponse {
  path: string
  from_hash: string
  to_hash: string
  from_timestamp: string
  to_timestamp: string
  changes: FieldChange[]
}

export interface PrimitiveCreate {
  type: string
  name: string
  description?: string
  tags?: string[]
  properties?: Record<string, unknown>
  steps?: unknown[]
  parent_project?: string
  relationships?: Array<{ type: string; target: string }>
}

export interface PrimitiveUpdate {
  id: string
  type: string
  name: string
  slug: string
  description?: string
  tags?: string[]
  properties?: Record<string, unknown>
  steps?: unknown[]
  parent_project?: string
  relationships?: Array<{ type: string; target: string }>
}

export interface SystemStatus {
  shell_version: string
  core_connected: boolean
  core_url: string
  modules_loaded: number
  modules_failed: number
  userdb_path: string
  uptime_seconds: number
}
