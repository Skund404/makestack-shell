/**
 * View registry — runtime map of route pattern → React component.
 *
 * Module frontends call registerView() during init (triggered by
 * registerAllModules() in main.tsx). The shell's ModuleViewRenderer
 * catches unmatched routes and looks up the path here.
 *
 * Supports path parameters:
 *   registerView('/kitchen/recipes/:id', KitchenRecipeDetail)
 *   resolveView('/kitchen/recipes/abc123') → { component, params: { id: 'abc123' } }
 *
 * To register: registerView('/my/route', MyComponent)
 * To register with params: registerView('/my/route/:id', MyDetailComponent)
 * To resolve: resolveView('/my/route/123') → { component, params } | null
 */
import type { ComponentType } from 'react'

interface RegistryEntry {
  pattern: string
  regex: RegExp
  paramNames: string[]
  component: ComponentType<Record<string, string>>
}

const _registry: RegistryEntry[] = []

function compilePattern(pattern: string): { regex: RegExp; paramNames: string[] } {
  const paramNames: string[] = []
  const regexStr = pattern.replace(/:([^/]+)/g, (_, name: string) => {
    paramNames.push(name)
    return '([^/]+)'
  })
  return { regex: new RegExp(`^${regexStr}$`), paramNames }
}

export function registerView(
  pattern: string,
  component: ComponentType<Record<string, string>>,
): void {
  const { regex, paramNames } = compilePattern(pattern)
  _registry.push({ pattern, regex, paramNames, component })
}

export interface ResolvedView {
  component: ComponentType<Record<string, string>>
  params: Record<string, string>
}

export function resolveView(pathname: string): ResolvedView | null {
  for (const entry of _registry) {
    const match = pathname.match(entry.regex)
    if (match) {
      const params: Record<string, string> = {}
      entry.paramNames.forEach((name, i) => {
        params[name] = match[i + 1]
      })
      return { component: entry.component, params }
    }
  }
  return null
}
