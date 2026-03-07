import * as RadixScroll from '@radix-ui/react-scroll-area'
import { cn } from '@/lib/utils'

interface ScrollAreaProps {
  children: React.ReactNode
  className?: string
}

export function ScrollArea({ children, className }: ScrollAreaProps) {
  return (
    <RadixScroll.Root className={cn('overflow-hidden', className)}>
      <RadixScroll.Viewport className="h-full w-full">
        {children}
      </RadixScroll.Viewport>
      <RadixScroll.Scrollbar
        orientation="vertical"
        className="flex w-1.5 touch-none select-none p-0.5"
      >
        <RadixScroll.Thumb className="relative flex-1 rounded bg-border-bright" />
      </RadixScroll.Scrollbar>
    </RadixScroll.Root>
  )
}
