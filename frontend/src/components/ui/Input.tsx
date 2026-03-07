import { cn } from '@/lib/utils'

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export function Input({ label, error, className, id, ...props }: InputProps) {
  const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-')
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label htmlFor={inputId} className="text-xs font-medium text-text-muted">
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={cn(
          'h-8 px-3 rounded border bg-surface-el text-text text-sm',
          'border-border-bright placeholder:text-text-faint',
          'focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/25',
          'transition-colors',
          error && 'border-danger/50 focus:border-danger focus:ring-danger/25',
          className,
        )}
        {...props}
      />
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  )
}

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  error?: string
}

export function Textarea({ label, error, className, id, ...props }: TextareaProps) {
  const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-')
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label htmlFor={inputId} className="text-xs font-medium text-text-muted">
          {label}
        </label>
      )}
      <textarea
        id={inputId}
        className={cn(
          'px-3 py-2 rounded border bg-surface-el text-text text-sm',
          'border-border-bright placeholder:text-text-faint',
          'focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/25',
          'transition-colors resize-y min-h-[80px]',
          error && 'border-danger/50',
          className,
        )}
        {...props}
      />
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  )
}
