import { useState } from 'react'
import type { KeywordContext } from '@/modules/keyword-resolver'

interface ChecklistItem {
  text: string
  checked?: boolean
}

interface ChecklistWidgetProps {
  keyword: string
  value: unknown
  context: KeywordContext
}

export function ChecklistWidget({ value, context: _context }: ChecklistWidgetProps) {
  const rawItems: ChecklistItem[] = Array.isArray(value)
    ? (value as Array<string | ChecklistItem>).map((item) =>
        typeof item === 'string' ? { text: item, checked: false } : item,
      )
    : []

  const [checked, setChecked] = useState<boolean[]>(() => rawItems.map((i) => i.checked ?? false))

  const toggle = (idx: number) =>
    setChecked((prev) => prev.map((v, i) => (i === idx ? !v : v)))

  if (rawItems.length === 0) return null

  return (
    <ul className="space-y-1 my-1">
      {rawItems.map((item, idx) => (
        <li key={idx} className="flex items-start gap-2">
          <button
            onClick={() => toggle(idx)}
            className={`mt-0.5 w-4 h-4 rounded border shrink-0 flex items-center justify-center transition-colors ${
              checked[idx]
                ? 'bg-accent border-accent text-bg'
                : 'border-border-bright hover:border-accent/50'
            }`}
          >
            {checked[idx] && (
              <svg viewBox="0 0 8 8" className="w-2.5 h-2.5 fill-current">
                <polyline points="1,4 3,6 7,2" stroke="currentColor" strokeWidth="1.5" fill="none" />
              </svg>
            )}
          </button>
          <span className={`text-sm leading-5 ${checked[idx] ? 'line-through text-text-faint' : 'text-text'}`}>
            {item.text}
          </span>
        </li>
      ))}
    </ul>
  )
}
