/**
 * Theme loader — fetches the active theme from the Shell API and injects
 * CSS custom properties on :root. Called once at app startup.
 */
import type { ThemeData } from './tokens'

export async function loadTheme(): Promise<void> {
  try {
    const res = await fetch('/api/settings/theme/data')
    if (!res.ok) return
    const theme = (await res.json()) as ThemeData
    applyTheme(theme)
  } catch {
    // Backend not available — CSS defaults in index.css remain active
  }
}

export function applyTheme(theme: ThemeData): void {
  const root = document.documentElement
  for (const [prop, value] of Object.entries(theme.variables)) {
    root.style.setProperty(prop, value)
  }
  root.setAttribute('data-theme', theme.name)
}
