import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Plus, Loader2, AlertCircle, RefreshCw } from 'lucide-react'
import { useInventoryList, useStaleItems } from '@/hooks/use-inventory'
import { useWorkshopList } from '@/hooks/use-workshops'
import { AddToInventoryDialog } from '@/components/inventory/AddToInventoryDialog'
import { Card, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Select } from '@/components/ui/Select'
import { primitiveTypeBg, abbreviateHash, formatDate } from '@/lib/utils'
import type { InventoryItem } from '@/lib/types'

const ALL = '__all__'

const TYPE_OPTIONS = [
  { value: ALL, label: 'All types' },
  { value: 'tool', label: 'Tools' },
  { value: 'material', label: 'Materials' },
  { value: 'technique', label: 'Techniques' },
  { value: 'workflow', label: 'Workflows' },
  { value: 'project', label: 'Projects' },
  { value: 'event', label: 'Events' },
]

/** Derive a readable display name from a catalogue path like "tools/stitching-chisel/manifest.json" */
function slugFromPath(path: string): string {
  const parts = path.split('/')
  const slug = parts.length >= 2 ? parts[1] : parts[0]
  return slug
    .split('-')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function InventoryCard({
  item,
  isStale,
  workshopName,
  onClick,
}: {
  item: InventoryItem
  isStale: boolean
  workshopName?: string
  onClick: () => void
}) {
  return (
    <Card hoverable onClick={onClick} className={isStale ? 'border-warning/30' : undefined}>
      <CardBody className="space-y-2">
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-sm font-semibold text-text leading-tight">{slugFromPath(item.catalogue_path)}</h3>
          <span className={`text-xs px-1.5 py-0.5 rounded border shrink-0 ${primitiveTypeBg(item.primitive_type)}`}>
            {item.primitive_type}
          </span>
        </div>
        <div className="flex items-center flex-wrap gap-2">
          {workshopName && <Badge variant="muted">{workshopName}</Badge>}
          {isStale && (
            <span className="inline-flex items-center gap-1 text-xs text-warning">
              <RefreshCw size={10} /> update available
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs text-text-faint">
          <span className="font-mono">{abbreviateHash(item.catalogue_hash)}</span>
          <span>·</span>
          <span>Added {formatDate(item.added_at)}</span>
        </div>
      </CardBody>
    </Card>
  )
}

const PAGE_SIZE = 24

export function InventoryIndex() {
  const navigate = useNavigate()
  const [typeFilter, setTypeFilter] = useState(ALL)
  const [workshopFilter, setWorkshopFilter] = useState(ALL)
  const [offset, setOffset] = useState(0)
  const [addOpen, setAddOpen] = useState(false)

  const { data, isLoading, isError } = useInventoryList(
    workshopFilter !== ALL ? workshopFilter : undefined,
    typeFilter !== ALL ? typeFilter : undefined,
    PAGE_SIZE,
    offset,
  )
  const { data: staleData } = useStaleItems()
  const { data: workshops } = useWorkshopList()

  const staleIds = new Set((staleData?.items ?? []).map((i) => i.id))
  const workshopMap = Object.fromEntries((workshops?.items ?? []).map((w) => [w.id, w.name]))

  const workshopOptions = [
    { value: ALL, label: 'All workshops' },
    ...(workshops?.items ?? []).map((w) => ({ value: w.id, label: w.name })),
  ]

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-text-muted gap-2">
        <Loader2 size={16} className="animate-spin" /> Loading…
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex items-center justify-center py-16 text-danger/70 gap-2">
        <AlertCircle size={16} /> Failed to load inventory.
      </div>
    )
  }

  const items = data?.items ?? []
  const total = data?.total ?? 0
  const limit = data?.limit ?? PAGE_SIZE
  const totalPages = Math.ceil(total / limit)
  const currentPage = Math.floor(offset / limit) + 1

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <div className="flex items-center gap-2">
          <h1 className="text-base font-semibold text-text">Inventory</h1>
          {staleData && staleData.total > 0 && (
            <Badge variant="warning">{staleData.total} stale</Badge>
          )}
        </div>
        <Button variant="primary" size="sm" onClick={() => setAddOpen(true)}>
          <Plus size={12} /> Add item
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 px-4 pb-3">
        <Select
          value={typeFilter}
          onValueChange={(v) => { setTypeFilter(v); setOffset(0) }}
          options={TYPE_OPTIONS}
          className="w-36"
        />
        <Select
          value={workshopFilter}
          onValueChange={(v) => { setWorkshopFilter(v); setOffset(0) }}
          options={workshopOptions}
          className="w-44"
        />
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3 text-text-faint">
            <p className="text-sm">No inventory items{typeFilter !== ALL || workshopFilter !== ALL ? ' matching filters' : ''}.</p>
            {typeFilter === ALL && workshopFilter === ALL && (
              <Button variant="secondary" size="sm" onClick={() => setAddOpen(true)}>
                <Plus size={12} /> Add your first item
              </Button>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between text-xs text-text-faint">
              <span>{total} item{total !== 1 ? 's' : ''}</span>
              {totalPages > 1 && <span>Page {currentPage} of {totalPages}</span>}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {items.map((item: InventoryItem) => (
                <InventoryCard
                  key={item.id}
                  item={item}
                  isStale={staleIds.has(item.id)}
                  workshopName={item.workshop_id ? workshopMap[item.workshop_id] : undefined}
                  onClick={() => void navigate({ to: '/inventory/detail', search: { id: item.id } })}
                />
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
        )}
      </div>

      <AddToInventoryDialog open={addOpen} onOpenChange={setAddOpen} />
    </div>
  )
}
