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

export interface InventoryItem {
  id: string
  catalogue_path: string
  catalogue_hash: string
  primitive_type: string
  workshop_id: string | null
  added_at: string
  updated_at: string
}

export interface InventoryItemWithCatalogue extends InventoryItem {
  catalogue_data: Primitive | null
  is_stale: boolean
  current_hash: string | null
}

export interface Workshop {
  id: string
  name: string
  slug: string
  description: string
  icon: string
  color: string
  sort_order: number
  created_at: string
  updated_at: string
}

export interface WorkshopMember {
  primitive_path: string
  primitive_type: string
  added_at: string
}

export interface WorkshopWithMembers extends Workshop {
  members: WorkshopMember[]
}

export interface WorkshopCreate {
  name: string
  description?: string
  icon?: string
  color?: string
}

export interface WorkshopUpdate {
  name?: string
  description?: string
  icon?: string
  color?: string
  sort_order?: number
}

export interface SystemStatus {
  shell_version: string
  core_connected: boolean
  core_url: string
  last_core_check: string | null
  modules_loaded: number
  modules_failed: number
  userdb_path: string
  uptime_seconds: number
  cache_size: number
  dev_mode?: boolean
}
