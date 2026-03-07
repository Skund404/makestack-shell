/**
 * TypeScript types for the Makestack theme structure.
 * Matches the ThemeData response from GET /api/settings/theme/data.
 */

export interface ThemeData {
  name: string
  variables: Record<string, string>
}

export const THEME_NAMES = ['cyberpunk', 'workshop', 'daylight', 'high-contrast'] as const
export type ThemeName = typeof THEME_NAMES[number]
