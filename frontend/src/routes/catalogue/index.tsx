import { useState } from 'react'
import { Plus, Loader2, AlertCircle } from 'lucide-react'
import { Link } from '@tanstack/react-router'
import { usePrimitiveList } from '@/hooks/use-catalogue'
import { PrimitiveCard } from '@/components/catalogue/PrimitiveCard'
import { Tabs, TabContent } from '@/components/ui/Tabs'
import { Button } from '@/components/ui/Button'
import type { Primitive } from '@/lib/types'

const TABS = [
  { value: '',          label: 'All' },
  { value: 'tool',      label: 'Tools' },
  { value: 'material',  label: 'Materials' },
  { value: 'technique', label: 'Techniques' },
  { value: 'workflow',  label: 'Workflows' },
  { value: 'project',   label: 'Projects' },
  { value: 'event',     label: 'Events' },
]

const PAGE_SIZE = 24

function PrimitiveGrid({ type }: { type: string }) {
  const [offset, setOffset] = useState(0)
  const { data, isLoading, isError } = usePrimitiveList(type || undefined, PAGE_SIZE, offset)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-text-muted gap-2">
        <Loader2 size={16} className="animate-spin" />
        Loading…
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex items-center justify-center py-16 text-danger/70 gap-2">
        <AlertCircle size={16} />
        Failed to load primitives. Is the backend running?
      </div>
    )
  }

  if (!data || data.items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-3 text-text-faint">
        <p className="text-sm">No primitives found.</p>
        <Link to="/catalogue/create" search={{ type: type || undefined }}>
          <Button variant="secondary" size="sm" type="button">
            <Plus size={12} /> Create one
          </Button>
        </Link>
      </div>
    )
  }

  const { items, total, limit } = data
  const totalPages = Math.ceil(total / limit)
  const currentPage = Math.floor(offset / limit) + 1

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between text-xs text-text-faint">
        <span>{total} {type || 'primitive'}{total !== 1 ? 's' : ''}</span>
        {totalPages > 1 && (
          <span>Page {currentPage} of {totalPages}</span>
        )}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {items.map((p: Primitive) => (
          <PrimitiveCard key={p.id} primitive={p} />
        ))}
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-2">
          <Button
            variant="ghost"
            size="sm"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - limit))}
          >
            Previous
          </Button>
          <span className="text-xs text-text-faint">{currentPage} / {totalPages}</span>
          <Button
            variant="ghost"
            size="sm"
            disabled={offset + limit >= total}
            onClick={() => setOffset(offset + limit)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  )
}

interface CatalogueIndexProps {
  initialType?: string
}

export function CatalogueIndex({ initialType = '' }: CatalogueIndexProps) {
  const [activeTab, setActiveTab] = useState(initialType)

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <h1 className="text-base font-semibold text-text">Catalogue</h1>
        <Link to="/catalogue/create" search={{ type: undefined }}>
          <Button variant="primary" size="sm" type="button">
            <Plus size={12} /> New Primitive
          </Button>
        </Link>
      </div>

      <Tabs
        tabs={TABS}
        value={activeTab}
        onValueChange={setActiveTab}
        className="flex-1 min-h-0"
      >
        {TABS.map((tab) => (
          <TabContent key={tab.value} value={tab.value} className="flex-1 overflow-y-auto px-4 py-4">
            <PrimitiveGrid type={tab.value} />
          </TabContent>
        ))}
      </Tabs>
    </div>
  )
}
