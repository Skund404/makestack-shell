import * as RadixSelect from '@radix-ui/react-select'
import { Check, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SelectOption {
  value: string
  label: string
}

interface SelectProps {
  value: string
  onValueChange: (value: string) => void
  options: SelectOption[]
  placeholder?: string
  label?: string
  className?: string
  disabled?: boolean
}

export function Select({ value, onValueChange, options, placeholder = 'Select…', label, className, disabled }: SelectProps) {
  return (
    <div className="flex flex-col gap-1">
      {label && <span className="text-xs font-medium text-text-muted">{label}</span>}
      <RadixSelect.Root value={value} onValueChange={onValueChange} disabled={disabled}>
        <RadixSelect.Trigger
          className={cn(
            'inline-flex items-center justify-between gap-2',
            'h-8 px-3 rounded border bg-surface-el text-text text-sm',
            'border-border-bright hover:border-accent/40',
            'focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/25',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'transition-colors cursor-pointer',
            className,
          )}
        >
          <RadixSelect.Value placeholder={<span className="text-text-faint">{placeholder}</span>} />
          <RadixSelect.Icon>
            <ChevronDown size={12} className="text-text-faint" />
          </RadixSelect.Icon>
        </RadixSelect.Trigger>
        <RadixSelect.Portal>
          <RadixSelect.Content
            className="z-50 min-w-[10rem] rounded border border-border-bright bg-surface shadow-xl"
            position="popper"
            sideOffset={4}
          >
            <RadixSelect.Viewport className="p-1">
              {options.map((opt) => (
                <RadixSelect.Item
                  key={opt.value}
                  value={opt.value}
                  className={cn(
                    'flex items-center justify-between gap-2 px-3 py-1.5 text-sm rounded',
                    'text-text-muted hover:bg-surface-el hover:text-text cursor-pointer',
                    'data-[state=checked]:text-accent data-[highlighted]:outline-none data-[highlighted]:bg-surface-el data-[highlighted]:text-text',
                  )}
                >
                  <RadixSelect.ItemText>{opt.label}</RadixSelect.ItemText>
                  <RadixSelect.ItemIndicator>
                    <Check size={12} className="text-accent" />
                  </RadixSelect.ItemIndicator>
                </RadixSelect.Item>
              ))}
            </RadixSelect.Viewport>
          </RadixSelect.Content>
        </RadixSelect.Portal>
      </RadixSelect.Root>
    </div>
  )
}
