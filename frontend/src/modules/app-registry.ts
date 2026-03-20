/**
 * App registry — runtime map of route prefix → standalone app mode configuration.
 *
 * Modules that declare app_mode call registerAppMode() during init. The shell's
 * Layout component calls resolveAppMode(pathname) to determine whether the current
 * route should render in standalone module mode (branded sidebar, no shell chrome)
 * or in the default shell layout.
 *
 * Uses longest-prefix-match to avoid collisions between e.g. /kitchen and /kitchen-pro.
 */
import type { ComponentType } from 'react'

export interface AppNavItem {
  id: string
  label: string
  icon: string
  route: string
  badge_endpoint?: string | null
}

export interface AppTheme {
  sidebar_bg: string
  sidebar_text: string
  sidebar_active_bg: string
  accent: string
}

export interface AppModeConfig {
  module_name: string
  title: string
  subtitle: string
  sidebar_width: number
  home_route: string
  nav_items: AppNavItem[]
  theme?: AppTheme | null
  /** Optional custom sidebar component — if set, replaces the generic ModuleAppSidebar. */
  custom_sidebar?: ComponentType<{ config: AppModeConfig }> | null
}

const _registry: AppModeConfig[] = []

export function registerAppMode(config: AppModeConfig): void {
  _registry.push(config)
  // Sort by home_route length descending for longest-prefix-match
  _registry.sort((a, b) => b.home_route.length - a.home_route.length)
}

/**
 * Resolve whether the given pathname falls under a registered app mode.
 * Returns the matching config or null if the path is a shell route.
 */
export function resolveAppMode(pathname: string): AppModeConfig | null {
  for (const config of _registry) {
    if (pathname === config.home_route || pathname.startsWith(config.home_route + '/')) {
      return config
    }
  }
  return null
}

/** Get all registered app mode configs. */
export function getAllAppModes(): AppModeConfig[] {
  return [..._registry]
}
