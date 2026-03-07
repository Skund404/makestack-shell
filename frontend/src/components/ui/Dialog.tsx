import * as RadixDialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

interface DialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  children: React.ReactNode
  className?: string
}

export function Dialog({ open, onOpenChange, title, description, children, className }: DialogProps) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40" />
        <RadixDialog.Content
          className={cn(
            'fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50',
            'w-full max-w-lg rounded-lg border border-border-bright bg-surface shadow-xl',
            'focus:outline-none',
            className,
          )}
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <RadixDialog.Title className="text-sm font-semibold text-text">
              {title}
            </RadixDialog.Title>
            <RadixDialog.Close className="text-text-faint hover:text-text transition-colors p-1 rounded hover:bg-surface-el">
              <X size={14} />
            </RadixDialog.Close>
          </div>
          {description && (
            <RadixDialog.Description className="px-4 pt-3 text-sm text-text-muted">
              {description}
            </RadixDialog.Description>
          )}
          <div className="px-4 py-4">{children}</div>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  )
}
