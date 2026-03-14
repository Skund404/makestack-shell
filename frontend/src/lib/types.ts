/**
 * TypeScript types matching the Shell REST API response shapes (Pydantic models).
 */

// ---------------------------------------------------------------------------
// Typed Step sub-types (Primitives Evolution — Core-2)
// ---------------------------------------------------------------------------

/** A {value, unit} measurement object used in step duration and parameters. */
export interface StepDuration {
  value: number
  unit: string
}

/** A single parameter entry: key maps to a measurement object. */
export type StepParameter = Record<string, StepDuration>

/** A material or tool requirement declared within a step. */
export interface StepRequirement {
  type: string
  target: string
  quantity?: number
  unit?: string
  notes?: string
}

/**
 * A typed step in a technique or workflow's steps array.
 * Old-style plain-string or unstructured-object steps remain valid;
 * this interface describes steps that carry an 'order' field.
 */
export interface Step {
  order: number
  title: string
  notes?: string
  technique_ref?: string
  duration?: StepDuration
  parameters?: StepParameter
  requirements?: StepRequirement[]
}

// ---------------------------------------------------------------------------
// Primitive
// ---------------------------------------------------------------------------

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
  /** Domain pack affiliation (Primitives Evolution — Core-1). */
  domain?: string | null
  /** Unit of measure for material primitives (Core-1). */
  unit?: string | null
  /** Material subtype: consumable | component | product | organism (Core-1). */
  subtype?: string | null
  /** ISO8601 timestamp for event primitives (Core-1). */
  occurred_at?: string | null
  /** Lifecycle status for project primitives (Core-1). */
  status?: string | null
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
  domain?: string
  unit?: string
  subtype?: string
  occurred_at?: string
  status?: string
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
  domain?: string
  unit?: string
  subtype?: string
  occurred_at?: string
  status?: string
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

export interface WorkshopModule {
  workshop_id: string
  module_name: string
  sort_order: number
  enabled: boolean
}

/** A single nav entry for a workshop — either module-contributed or a shell fallback. */
export interface NavItem {
  id: string
  label: string
  route: string
  icon: string
  source: 'module' | 'shell'
  /** If set, signals the frontend to demote this shell view to secondary position. */
  replaces_shell_view: string | null
}

export interface WorkshopNav {
  items: NavItem[]
}

// ---------------------------------------------------------------------------
// Module types
// ---------------------------------------------------------------------------

export interface InstalledModule {
  name: string
  version: string
  installed_at: string
  enabled: boolean
  last_migration: string | null
  package_path: string | null
  loaded: boolean
  load_error: string | null
  manifest: Record<string, unknown> | null
}

// ---------------------------------------------------------------------------
// Package and registry types
// ---------------------------------------------------------------------------

export interface InstalledPackage {
  name: string
  type: string              // module | widget-pack | catalogue | data
  version: string
  installed_at: string
  package_path: string | null
  git_url: string | null
  registry_name: string | null
}

export interface PackageSearchResult {
  name: string
  type: string
  description: string | null
  git_url: string | null
  registry: string
}

export interface InstallResult {
  success: boolean
  package_name: string
  package_type: string
  version: string
  restart_required: boolean
  message: string
  warnings: string[]
}

export interface RegistryRecord {
  name: string
  git_url: string
  added_at: string
  last_refreshed: string | null
  package_count: number
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
