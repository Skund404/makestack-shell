import { useState } from 'react'
import { ArrowLeftRight } from 'lucide-react'
import type { KeywordContext } from '@/modules/keyword-resolver'

interface MeasurementValue {
  value: number
  unit: string
}

const CONVERSIONS: Record<string, { to: string; factor: number }> = {
  mm:  { to: 'in',  factor: 1 / 25.4 },
  in:  { to: 'mm',  factor: 25.4 },
  cm:  { to: 'in',  factor: 1 / 2.54 },
  g:   { to: 'oz',  factor: 1 / 28.3495 },
  oz:  { to: 'g',   factor: 28.3495 },
  kg:  { to: 'lb',  factor: 2.20462 },
  lb:  { to: 'kg',  factor: 1 / 2.20462 },
}

function parseMeasurement(raw: string): MeasurementValue | null {
  const match = raw.trim().match(/^([\d.]+)\s*([a-zA-Z]+)$/)
  if (!match) return null
  return { value: parseFloat(match[1]), unit: match[2].toLowerCase() }
}

interface MeasurementWidgetProps {
  keyword: string
  value: unknown
  context: KeywordContext
}

export function MeasurementWidget({ value, context: _context }: MeasurementWidgetProps) {
  const [converted, setConverted] = useState(false)

  const parsed: MeasurementValue | null =
    typeof value === 'string'
      ? parseMeasurement(value)
      : typeof value === 'object' && value !== null
        ? (value as MeasurementValue)
        : null

  if (!parsed) {
    return <span className="font-mono text-sm text-text">{String(value)}</span>
  }

  const conv = CONVERSIONS[parsed.unit]
  const canConvert = Boolean(conv)

  const display = converted && conv
    ? { value: +(parsed.value * conv.factor).toFixed(3), unit: conv.to }
    : parsed

  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="font-mono text-sm text-text">
        {display.value}
        <span className="text-xs text-text-muted ml-0.5">{display.unit}</span>
      </span>
      {canConvert && (
        <button
          onClick={() => setConverted((c) => !c)}
          className="p-0.5 rounded text-text-faint hover:text-accent transition-colors"
          title={converted ? `Show original (${parsed.value}${parsed.unit})` : `Convert to ${conv?.to}`}
        >
          <ArrowLeftRight size={10} />
        </button>
      )}
    </span>
  )
}
