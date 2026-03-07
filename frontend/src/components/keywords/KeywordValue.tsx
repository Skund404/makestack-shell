/**
 * KeywordValue — renders a single keyword/value pair using the registry.
 * Falls back to raw JSON if no renderer is registered.
 */
import { resolveKeyword } from '@/modules/keyword-resolver'
import type { KeywordContext } from '@/modules/keyword-resolver'

interface KeywordValueProps {
  keyword: string
  value: unknown
  context: KeywordContext
}

export function KeywordValue({ keyword, value, context }: KeywordValueProps) {
  const Renderer = resolveKeyword(keyword)

  if (Renderer) {
    return <Renderer keyword={keyword} value={value} context={context} />
  }

  // Graceful fallback — show raw value as text
  const display = typeof value === 'object' ? JSON.stringify(value) : String(value ?? '')
  return <span className="font-mono text-sm text-text-muted">{display}</span>
}
