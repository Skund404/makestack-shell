import * as RadixTabs from '@radix-ui/react-tabs'
import { cn } from '@/lib/utils'

interface Tab {
  value: string
  label: React.ReactNode
}

interface TabsProps {
  tabs: Tab[]
  value: string
  onValueChange: (value: string) => void
  children: React.ReactNode
  className?: string
}

export function Tabs({ tabs, value, onValueChange, children, className }: TabsProps) {
  return (
    <RadixTabs.Root value={value} onValueChange={onValueChange} className={cn('flex flex-col', className)}>
      <RadixTabs.List className="flex items-center gap-0.5 px-1 border-b border-border shrink-0">
        {tabs.map((tab) => (
          <RadixTabs.Trigger
            key={tab.value}
            value={tab.value}
            className={cn(
              'px-3 py-2 text-xs font-medium transition-colors cursor-pointer',
              'border-b-2 border-transparent -mb-px',
              'text-text-muted hover:text-text',
              'data-[state=active]:text-accent data-[state=active]:border-accent',
            )}
          >
            {tab.label}
          </RadixTabs.Trigger>
        ))}
      </RadixTabs.List>
      {children}
    </RadixTabs.Root>
  )
}

export const TabContent = RadixTabs.Content
