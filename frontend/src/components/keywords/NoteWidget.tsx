import { AlertTriangle, Info, Lightbulb } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { KeywordContext } from '@/modules/keyword-resolver'

interface NoteValue {
  text: string
  type?: 'info' | 'warning' | 'tip'
}

type NoteType = 'info' | 'warning' | 'tip'

interface NoteWidgetProps {
  keyword: string
  value: unknown
  context: KeywordContext
}

const noteStyles: Record<NoteType, { icon: React.ReactNode; classes: string }> = {
  info:    { icon: <Info size={13} />,          classes: 'border-accent/25 bg-accent/5 text-text' },
  warning: { icon: <AlertTriangle size={13} />, classes: 'border-warning/25 bg-warning/5 text-text' },
  tip:     { icon: <Lightbulb size={13} />,     classes: 'border-success/25 bg-success/5 text-text' },
}

const iconColors: Record<NoteType, string> = {
  info:    'text-accent',
  warning: 'text-warning',
  tip:     'text-success',
}

export function NoteWidget({ value, context: _context }: NoteWidgetProps) {
  const text = typeof value === 'string' ? value : (value as NoteValue)?.text ?? ''
  const type: NoteType = (typeof value === 'object' && value !== null ? (value as NoteValue).type : undefined) ?? 'info'

  const style = noteStyles[type]

  return (
    <div className={cn('flex gap-2.5 px-3 py-2.5 rounded border text-sm my-1', style.classes)}>
      <span className={cn('shrink-0 mt-0.5', iconColors[type])}>
        {style.icon}
      </span>
      <p className="leading-relaxed">{text}</p>
    </div>
  )
}
