/**
 * Keyword renderer registry.
 *
 * Resolution chain: module widgets → widget pack widgets → core widgets → raw text
 *
 * To register: registerKeyword('TIMER_', TimerWidget, 'core', meta)
 * To render: use the KeywordValue component (handles all resolution + fallback)
 * To enumerate: getAll() returns all registered widgets with metadata (used by DocsPanel 9E)
 */
import type { ComponentType } from 'react'

export interface KeywordContext {
  primitiveType: string
  primitivePath: string
  parentType?: string
  stepIndex?: number
  workshopId?: string
}

export type KeywordRenderer = ComponentType<{
  keyword: string
  value: unknown
  context: KeywordContext
}>

/** Metadata contract for DocsPanel (9E). */
export interface WidgetMeta {
  keyword: string
  description: string
  /** Example accepted values (shown in docs). */
  accepts: string[]
  /** 'core' | widget-pack name | module name */
  source: string
}

// Three-layer registry (higher index = higher priority)
type Layer = 'core' | 'pack' | 'module'

const registries: Record<Layer, Map<string, KeywordRenderer>> = {
  core: new Map(),
  pack: new Map(),
  module: new Map(),
}

const metaStore: Map<string, WidgetMeta> = new Map()

export function registerKeyword(
  keyword: string,
  renderer: KeywordRenderer,
  layer: Layer = 'core',
  meta?: Omit<WidgetMeta, 'keyword'>,
): void {
  registries[layer].set(keyword, renderer)
  if (meta) {
    metaStore.set(keyword, { keyword, ...meta })
  }
}

export function resolveKeyword(keyword: string): KeywordRenderer | null {
  return (
    registries.module.get(keyword) ??
    registries.pack.get(keyword) ??
    registries.core.get(keyword) ??
    null
  )
}

/** Return all registered widgets that have metadata (used by DocsPanel). */
export function getAll(): WidgetMeta[] {
  return Array.from(metaStore.values())
}
