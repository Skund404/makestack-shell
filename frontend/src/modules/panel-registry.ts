/**
 * Panel registry.
 *
 * Build-time map of panelId → React component, following the same pattern as
 * keyword-resolver.ts. Modules register their panels here; the workshop home
 * page resolves them at render time.
 *
 * To register: registerPanel('my-module.stats', StatsPanel)
 * To resolve:  resolvePanel('my-module.stats') → component or null
 */
import type { ComponentType } from 'react'

export interface PanelProps {
  workshopId: string
  panelId: string
}

export type PanelComponent = ComponentType<PanelProps>

const _registry = new Map<string, PanelComponent>()

export function registerPanel(panelId: string, component: PanelComponent): void {
  _registry.set(panelId, component)
}

export function resolvePanel(panelId: string): PanelComponent | null {
  return _registry.get(panelId) ?? null
}
