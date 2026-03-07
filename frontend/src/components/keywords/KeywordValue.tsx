/**
 * KeywordValue — renders a single keyword/value pair using the registry.
 * Falls back to raw JSON if no renderer is registered.
 *
 * Module-sourced renderers are wrapped in a ModuleErrorBoundary so a crash
 * in a module's widget does not take down the entire page.
 * Core widgets are trusted and rendered directly.
 */
import { resolveKeyword } from '@/modules/keyword-resolver'
import type { KeywordContext } from '@/modules/keyword-resolver'
import { ModuleErrorBoundary } from '@/components/modules/ModuleErrorBoundary'

interface KeywordValueProps {
  keyword: string
  value: unknown
  context: KeywordContext
}

/** Core keywords — these are trusted and do NOT need an error boundary. */
const CORE_KEYWORDS = new Set([
  'TIMER_', 'MEASUREMENT_', 'MATERIAL_REF_', 'TOOL_REF_',
  'TECHNIQUE_REF_', 'IMAGE_', 'LINK_', 'NOTE_', 'CHECKLIST_',
])

export function KeywordValue({ keyword, value, context }: KeywordValueProps) {
  const Renderer = resolveKeyword(keyword)

  if (!Renderer) {
    // Graceful fallback — show raw value as text
    const display = typeof value === 'object' ? JSON.stringify(value) : String(value ?? '')
    return <span className="font-mono text-sm text-text-muted">{display}</span>
  }

  const rendered = <Renderer keyword={keyword} value={value} context={context} />

  // Core widgets are trusted — render directly without the boundary overhead.
  if (CORE_KEYWORDS.has(keyword)) {
    return rendered
  }

  // Module and widget-pack renderers are untrusted — wrap in error boundary.
  // Extract module name from the keyword if possible (best-effort for diagnostics).
  const moduleName = keyword.replace(/_+$/, '').toLowerCase().replace(/_/g, '-')

  return (
    <ModuleErrorBoundary
      moduleName={moduleName}
      componentName={Renderer.displayName ?? Renderer.name}
      keyword={keyword}
    >
      {rendered}
    </ModuleErrorBoundary>
  )
}
