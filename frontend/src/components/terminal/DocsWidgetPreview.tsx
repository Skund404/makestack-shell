/**
 * DocsWidgetPreview — editable value input that renders the live widget.
 *
 * Uses resolveKeyword() directly — the same function used in real primitive views.
 * No backend call. Falls back gracefully if no renderer is registered.
 */
import { useState } from 'react'
import { resolveKeyword } from '@/modules/keyword-resolver'

interface DocsWidgetPreviewProps {
  keyword: string
  initialValue: string
}

const PREVIEW_CONTEXT = {
  primitiveType: 'technique',
  primitivePath: 'docs/preview',
}

export function DocsWidgetPreview({ keyword, initialValue }: DocsWidgetPreviewProps) {
  const [value, setValue] = useState(initialValue)
  const Renderer = resolveKeyword(keyword)

  return (
    <div className="mt-1 space-y-1">
      <div className="flex items-center gap-1.5">
        <span className="text-[9px] text-text-faint/60 font-mono shrink-0">value:</span>
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="flex-1 text-[10px] font-mono bg-surface border border-border rounded px-1.5 py-px text-text outline-none focus:border-accent/50"
          placeholder="Edit to preview…"
          spellCheck={false}
        />
      </div>
      {Renderer && value ? (
        <div className="border border-border/50 rounded px-2 py-1 bg-surface/50 text-xs">
          <Renderer keyword={keyword} value={value} context={PREVIEW_CONTEXT} />
        </div>
      ) : (
        <div className="text-[10px] text-text-faint/40 font-mono italic">
          {Renderer ? 'Enter a value to preview' : 'No renderer registered'}
        </div>
      )}
    </div>
  )
}
