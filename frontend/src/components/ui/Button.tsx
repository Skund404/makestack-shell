import { cn } from '@/lib/utils'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  children: React.ReactNode
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:   'bg-accent text-bg font-semibold hover:bg-accent/80 border-transparent',
  secondary: 'bg-surface-el text-text hover:bg-border-bright border-border-bright',
  ghost:     'bg-transparent text-text-muted hover:bg-surface-el hover:text-text border-transparent',
  danger:    'bg-danger/10 text-danger hover:bg-danger/20 border-danger/25',
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'h-7 px-2.5 text-xs',
  md: 'h-8 px-3.5 text-sm',
  lg: 'h-10 px-5 text-sm',
}

export function Button({
  variant = 'secondary',
  size = 'md',
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      disabled={disabled}
      className={cn(
        'inline-flex items-center justify-center gap-1.5 rounded border',
        'transition-colors duration-150 cursor-pointer',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  )
}
