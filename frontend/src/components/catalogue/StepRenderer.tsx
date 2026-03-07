/**
 * Renders a steps array (technique / workflow).
 * Detects keywords in step objects and renders widgets inline.
 */
import { isKeyword } from '@/lib/keyword-detect'
import { KeywordValue } from '@/components/keywords/KeywordValue'
import type { KeywordContext } from '@/modules/keyword-resolver'

interface StepRendererProps {
  steps: unknown[]
  context: KeywordContext
}

export function StepRenderer({ steps, context }: StepRendererProps) {
  if (steps.length === 0) return null

  return (
    <ol className="space-y-3">
      {steps.map((step, idx) => (
        <li key={idx} className="flex gap-3">
          <span className="shrink-0 w-6 h-6 rounded-full bg-accent/10 border border-accent/20 flex items-center justify-center text-xs font-mono text-accent">
            {idx + 1}
          </span>
          <div className="flex-1 pt-0.5 space-y-1.5">
            {typeof step === 'string' ? (
              <p className="text-sm text-text leading-relaxed">{step}</p>
            ) : typeof step === 'object' && step !== null ? (
              <StepObject
                step={step as Record<string, unknown>}
                context={{ ...context, stepIndex: idx }}
              />
            ) : (
              <p className="text-sm text-text">{String(step)}</p>
            )}
          </div>
        </li>
      ))}
    </ol>
  )
}

interface StepObjectProps {
  step: Record<string, unknown>
  context: KeywordContext
}

function StepObject({ step, context }: StepObjectProps) {
  return (
    <div className="space-y-1.5">
      {Object.entries(step).map(([key, value]) =>
        isKeyword(key) ? (
          <KeywordValue key={key} keyword={key} value={value} context={context} />
        ) : key === 'text' || key === 'instruction' || key === 'description' ? (
          <p key={key} className="text-sm text-text leading-relaxed">
            {String(value)}
          </p>
        ) : (
          <div key={key} className="flex gap-2 text-xs">
            <span className="text-text-faint font-mono">{key}:</span>
            <span className="text-text-muted font-mono">
              {typeof value === 'object' ? JSON.stringify(value) : String(value ?? '')}
            </span>
          </div>
        ),
      )}
    </div>
  )
}
