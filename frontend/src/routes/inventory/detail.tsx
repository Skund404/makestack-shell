import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import {
  Loader2,
  AlertCircle,
  RefreshCw,
  Trash2,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'
import { useInventoryItem, useUpdateInventoryItem, useRemoveFromInventory } from '@/hooks/use-inventory'
import { useWorkshopList } from '@/hooks/use-workshops'
import { DiffViewer } from '@/components/version/DiffViewer'
import { VersionBadge } from '@/components/version/VersionBadge'
import { PropertyRenderer } from '@/components/catalogue/PropertyRenderer'
import { StepRenderer } from '@/components/catalogue/StepRenderer'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Dialog } from '@/components/ui/Dialog'
import { Select } from '@/components/ui/Select'
import { Separator } from '@/components/ui/Separator'
import { primitiveTypeBg, formatDateTime, abbreviateHash } from '@/lib/utils'

function CollapsibleSection({
  label,
  defaultOpen = false,
  children,
}: {
  label: string
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 w-full py-2 text-sm font-medium text-text-muted hover:text-text transition-colors"
      >
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        {label}
      </button>
      {open && <div className="pl-5 pb-3">{children}</div>}
    </div>
  )
}

function InventoryDetailView({ id }: { id: string }) {
  const navigate = useNavigate()
  const { data, isLoading, isError } = useInventoryItem(id)
  const { data: workshops } = useWorkshopList()
  const updateMutation = useUpdateInventoryItem()
  const removeMutation = useRemoveFromInventory()

  const [deleteOpen, setDeleteOpen] = useState(false)
  const [editingWorkshop, setEditingWorkshop] = useState(false)
  const NONE = '__none__'
  const [workshopId, setWorkshopId] = useState(NONE)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20 text-text-muted gap-2">
        <Loader2 size={16} className="animate-spin" /> Loading…
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3 text-danger/70">
        <AlertCircle size={20} />
        <p className="text-sm">Inventory item not found.</p>
      </div>
    )
  }

  const item = data
  const p = item.catalogue_data
  const context = {
    primitiveType: p?.type ?? item.primitive_type,
    primitivePath: p?.path ?? item.catalogue_path,
  }

  const workshopOptions = [
    { value: NONE, label: 'No workshop' },
    ...(workshops?.items ?? []).map((w) => ({ value: w.id, label: w.name })),
  ]
  const currentWorkshopName = workshops?.items.find((w) => w.id === item.workshop_id)?.name

  const handleUpdateHash = () => {
    if (!item.current_hash) return
    updateMutation.mutate({ id, data: { catalogue_hash: item.current_hash } })
  }

  const handleSaveWorkshop = () => {
    updateMutation.mutate(
      { id, data: { workshop_id: workshopId !== NONE ? workshopId : null } },
      { onSuccess: () => setEditingWorkshop(false) },
    )
  }

  const handleStartEditWorkshop = () => {
    setWorkshopId(item.workshop_id ?? NONE)
    setEditingWorkshop(true)
  }

  const handleRemove = () => {
    removeMutation.mutate(id, {
      onSuccess: () => void navigate({ to: '/inventory', search: {} }),
    })
  }

  return (
    <div className="max-w-3xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex-1 min-w-0">
          {p ? (
            <>
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-xs px-1.5 py-0.5 rounded border ${primitiveTypeBg(p.type)}`}>
                  {p.type}
                </span>
                <VersionBadge
                  currentHash={item.current_hash ?? undefined}
                  inventoryHash={item.catalogue_hash}
                />
              </div>
              <h1 className="text-xl font-semibold text-text leading-tight">{p.name}</h1>
              {p.description && (
                <p className="text-sm text-text-muted mt-1 leading-relaxed">{p.description}</p>
              )}
            </>
          ) : (
            <>
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-xs px-1.5 py-0.5 rounded border ${primitiveTypeBg(item.primitive_type)}`}>
                  {item.primitive_type}
                </span>
              </div>
              <h1 className="text-xl font-semibold text-text-muted font-mono leading-tight">
                {item.catalogue_path}
              </h1>
              <p className="text-sm text-text-faint mt-1">Catalogue data unavailable (Core offline)</p>
            </>
          )}
        </div>
        <Button variant="danger" size="sm" onClick={() => setDeleteOpen(true)}>
          <Trash2 size={12} />
        </Button>
      </div>

      {/* Tags */}
      {p && p.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-4">
          {p.tags.map((tag) => (
            <Badge key={String(tag)} variant="muted">{String(tag)}</Badge>
          ))}
        </div>
      )}

      <Separator className="mb-4" />

      {/* Inventory metadata */}
      <div className="grid grid-cols-2 gap-2 text-xs text-text-faint mb-3">
        <div>
          <span className="text-text-muted">Added</span> {formatDateTime(item.added_at)}
        </div>
        <div>
          <span className="text-text-muted">Updated</span> {formatDateTime(item.updated_at)}
        </div>
        <div className="col-span-2 font-mono">
          <span className="text-text-muted">Pinned version</span> {abbreviateHash(item.catalogue_hash)}
        </div>
      </div>

      {/* Workshop assignment */}
      <div className="mb-4 text-xs">
        {editingWorkshop ? (
          <div className="flex items-center gap-2">
            <Select
              value={workshopId}
              onValueChange={setWorkshopId}
              options={workshopOptions}
              placeholder="No workshop"
            />
            <Button
              variant="primary"
              size="sm"
              onClick={handleSaveWorkshop}
              disabled={updateMutation.isPending}
            >
              Save
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setEditingWorkshop(false)}>
              Cancel
            </Button>
          </div>
        ) : (
          <span className="text-text-faint">
            <span className="text-text-muted">Workshop</span>{' '}
            {currentWorkshopName ?? 'None'}{' '}
            <button
              onClick={handleStartEditWorkshop}
              className="text-accent hover:underline"
            >
              Edit
            </button>
          </span>
        )}
      </div>

      {/* Staleness */}
      {item.is_stale && item.current_hash && (
        <div className="mb-4 p-3 rounded border border-warning/30 bg-warning/5 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-sm text-warning">
              <RefreshCw size={14} />
              <span>The catalogue entry has been updated since you added this item.</span>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleUpdateHash}
              disabled={updateMutation.isPending}
            >
              {updateMutation.isPending ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <RefreshCw size={12} />
              )}
              Update to latest
            </Button>
          </div>
          <CollapsibleSection label="View changes">
            <DiffViewer
              path={item.catalogue_path}
              fromHash={item.catalogue_hash}
              toHash={item.current_hash}
            />
          </CollapsibleSection>
        </div>
      )}

      {/* Catalogue properties and steps */}
      {p && p.properties && Object.keys(p.properties).length > 0 && (
        <CollapsibleSection label="Properties" defaultOpen>
          <PropertyRenderer properties={p.properties} context={context} />
        </CollapsibleSection>
      )}
      {p && (p.manifest?.steps as unknown[] | undefined)?.length ? (
        <CollapsibleSection label="Steps" defaultOpen>
          <StepRenderer steps={p.manifest.steps as unknown[]} context={context} />
        </CollapsibleSection>
      ) : null}

      {/* Navigation to catalogue */}
      {p && (
        <div className="mt-4">
          <button
            onClick={() =>
              void navigate({
                to: '/catalogue/detail',
                search: { path: item.catalogue_path, at: undefined },
              })
            }
            className="text-xs text-accent hover:underline"
          >
            View in catalogue →
          </button>
        </div>
      )}

      {/* Remove dialog */}
      <Dialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Remove from inventory"
        description="Remove this item from your personal inventory? The catalogue entry is not affected."
      >
        <div className="flex justify-end gap-2 mt-2">
          <Button variant="ghost" onClick={() => setDeleteOpen(false)}>Cancel</Button>
          <Button
            variant="danger"
            onClick={handleRemove}
            disabled={removeMutation.isPending}
          >
            {removeMutation.isPending ? 'Removing…' : 'Remove'}
          </Button>
        </div>
      </Dialog>
    </div>
  )
}

export function InventoryDetail({ id }: { id: string }) {
  if (!id) {
    return (
      <div className="p-4 text-sm text-text-faint">No inventory item ID specified.</div>
    )
  }

  return (
    <div className="p-4 overflow-y-auto">
      <InventoryDetailView id={id} />
    </div>
  )
}
