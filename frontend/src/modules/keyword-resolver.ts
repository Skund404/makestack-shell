/**
 * Keyword renderer registry.
 *
 * Resolution chain: module widgets → widget pack widgets → core widgets → raw text
 *
 * To register: registerKeyword('TIMER_', TimerWidget)
 * To render: use the KeywordValue component (handles all resolution + fallback)
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

// Three-layer registry (higher index = higher priority)
type Layer = 'core' | 'pack' | 'module'

const registries: Record<Layer, Map<string, KeywordRenderer>> = {
  core: new Map(),
  pack: new Map(),
  module: new Map(),
}

export function registerKeyword(keyword: string, renderer: KeywordRenderer, layer: Layer = 'core'): void {
  registries[layer].set(keyword, renderer)
}

export function resolveKeyword(keyword: string): KeywordRenderer | null {
  return (
    registries.module.get(keyword) ??
    registries.pack.get(keyword) ??
    registries.core.get(keyword) ??
    null
  )
}
