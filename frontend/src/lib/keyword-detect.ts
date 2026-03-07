/**
 * Keyword detection utilities.
 * Keywords are JSON keys matching ^[A-Z][A-Z0-9_]*_ (uppercase, trailing underscore).
 */

const KEYWORD_PATTERN = /^[A-Z][A-Z0-9_]*_$/

export function isKeyword(key: string): boolean {
  return KEYWORD_PATTERN.test(key)
}

export interface KeywordEntry {
  keyword: string
  value: unknown
}

export function extractKeywords(obj: Record<string, unknown>): KeywordEntry[] {
  return Object.entries(obj)
    .filter(([key]) => isKeyword(key))
    .map(([keyword, value]) => ({ keyword, value }))
}

/** Parse a duration string like "30min", "2h", "45s" into total seconds. */
export function parseDuration(input: string): number {
  const str = input.trim().toLowerCase()
  const match = str.match(/^(\d+(?:\.\d+)?)\s*(h|hr|hours?|m|min|minutes?|s|sec|seconds?)?$/)
  if (!match) return 0
  const n = parseFloat(match[1])
  const unit = match[2] ?? 'm'
  if (unit.startsWith('h')) return Math.round(n * 3600)
  if (unit.startsWith('s')) return Math.round(n)
  return Math.round(n * 60) // default to minutes
}

/** Format seconds as "Hh Mm Ss" display string. */
export function formatDuration(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600)
  const m = Math.floor((totalSeconds % 3600) / 60)
  const s = totalSeconds % 60
  if (h > 0) return `${h}h ${m.toString().padStart(2, '0')}m ${s.toString().padStart(2, '0')}s`
  if (m > 0) return `${m}m ${s.toString().padStart(2, '0')}s`
  return `${s}s`
}
