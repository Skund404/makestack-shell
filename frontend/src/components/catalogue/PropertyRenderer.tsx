/**
 * Renders a properties object, detecting and rendering keywords as widgets.
 * Non-keyword keys render as regular key-value pairs.
 */
import { isKeyword } from '@/lib/keyword-detect'
import { KeywordValue } from '@/components/keywords/KeywordValue'
import type { KeywordContext } from '@/modules/keyword-resolver'

interface PropertyRendererProps {
  properties: Record<string, unknown>
  context: KeywordContext
}

export function PropertyRenderer({ properties, context }: PropertyRendererProps) {
  const entries = Object.entries(properties)
  if (entries.length === 0) return null

  return (
    <dl className="space-y-2">
      {entries.map(([key, value]) => (
        <div key={key} className="flex items-start gap-3">
          <dt className="text-xs font-medium text-text-muted shrink-0 w-28 pt-0.5 font-mono">
            {key}
          </dt>
          <dd className="text-sm text-text flex-1 min-w-0">
            {isKeyword(key) ? (
              <KeywordValue keyword={key} value={value} context={context} />
            ) : (
              <span className="font-mono text-xs break-all">
                {typeof value === 'object' ? JSON.stringify(value) : String(value ?? '')}
              </span>
            )}
          </dd>
        </div>
      ))}
    </dl>
  )
}
