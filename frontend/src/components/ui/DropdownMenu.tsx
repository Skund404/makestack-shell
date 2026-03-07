import * as RadixDropdown from '@radix-ui/react-dropdown-menu'
import { cn } from '@/lib/utils'

export const DropdownMenu = RadixDropdown.Root
export const DropdownMenuTrigger = RadixDropdown.Trigger

interface DropdownMenuContentProps {
  children: React.ReactNode
  className?: string
  align?: 'start' | 'center' | 'end'
  sideOffset?: number
}

export function DropdownMenuContent({ children, className, align = 'end', sideOffset = 6 }: DropdownMenuContentProps) {
  return (
    <RadixDropdown.Portal>
      <RadixDropdown.Content
        align={align}
        sideOffset={sideOffset}
        className={cn(
          'z-50 min-w-[10rem] rounded border border-border-bright bg-surface shadow-xl p-1',
          'animate-in fade-in-0 zoom-in-95',
          className,
        )}
      >
        {children}
      </RadixDropdown.Content>
    </RadixDropdown.Portal>
  )
}

interface DropdownMenuItemProps {
  children: React.ReactNode
  onSelect?: () => void
  disabled?: boolean
  className?: string
  variant?: 'default' | 'danger'
}

export function DropdownMenuItem({ children, onSelect, disabled, className, variant = 'default' }: DropdownMenuItemProps) {
  return (
    <RadixDropdown.Item
      onSelect={onSelect}
      disabled={disabled}
      className={cn(
        'flex items-center gap-2 px-3 py-1.5 text-sm rounded cursor-pointer',
        'focus:outline-none data-[highlighted]:outline-none',
        variant === 'default'
          ? 'text-text-muted data-[highlighted]:bg-surface-el data-[highlighted]:text-text'
          : 'text-danger data-[highlighted]:bg-danger/10',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        className,
      )}
    >
      {children}
    </RadixDropdown.Item>
  )
}

export function DropdownMenuSeparator() {
  return <RadixDropdown.Separator className="my-1 h-px bg-border" />
}

export function DropdownMenuLabel({ children }: { children: React.ReactNode }) {
  return (
    <RadixDropdown.Label className="px-3 py-1 text-xs font-medium text-text-faint">
      {children}
    </RadixDropdown.Label>
  )
}
