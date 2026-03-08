import { useState } from 'react'
import { Loader2, Search } from 'lucide-react'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import { useAddToInventory } from '@/hooks/use-inventory'
import { useWorkshopList } from '@/hooks/use-workshops'
import { useSearch } from '@/hooks/use-catalogue'
import { primitiveTypeBg } from '@/lib/utils'
import type { Primitive } from '@/lib/types'

interface AddToInventoryDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Pre-fill from a catalogue detail page — skips search step */
  preselectedPath?: string
  preselectedName?: string
  preselectedType?: string
  onAdded?: () => void
}

export function AddToInventoryDialog({
  open,
  onOpenChange,
  preselectedPath,
  preselectedName,
  preselectedType,
  onAdded,
}: AddToInventoryDialogProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedPrimitive, setSelectedPrimitive] = useState<Primitive | null>(null)
  const NONE = '__none__'
  const [workshopId, setWorkshopId] = useState(NONE)

  const addMutation = useAddToInventory()
  const { data: workshops } = useWorkshopList()
  const { data: searchResults, isLoading: searchLoading } = useSearch(
    searchQuery,
    !preselectedPath && searchQuery.trim().length > 1,
  )

  const activePath = preselectedPath ?? selectedPrimitive?.path
  const activeName = preselectedName ?? selectedPrimitive?.name
  const activeType = preselectedType ?? selectedPrimitive?.type

  const workshopOptions = [
    { value: NONE, label: 'No workshop' },
    ...(workshops?.items ?? []).map((w) => ({ value: w.id, label: w.name })),
  ]

  const handleClose = (open: boolean) => {
    if (!open) {
      setSearchQuery('')
      setSelectedPrimitive(null)
      setWorkshopId(NONE)
    }
    onOpenChange(open)
  }

  const handleConfirm = () => {
    if (!activePath) return
    addMutation.mutate(
      { catalogue_path: activePath, workshop_id: workshopId !== NONE ? workshopId : null },
      {
        onSuccess: () => {
          handleClose(false)
          onAdded?.()
        },
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={handleClose} title="Add to inventory">
      <div className="space-y-4">
        {/* Primitive selection */}
        {preselectedPath ? (
          <div className="p-3 rounded border border-border bg-surface-el space-y-1">
            <div className="flex items-center gap-2">
              {activeType && (
                <span className={`text-xs px-1.5 py-0.5 rounded border ${primitiveTypeBg(activeType)}`}>
                  {activeType}
                </span>
              )}
              <span className="text-sm font-medium text-text">{activeName}</span>
            </div>
            <p className="text-xs text-text-faint font-mono">{activePath}</p>
          </div>
        ) : selectedPrimitive ? (
          <div className="p-3 rounded border border-accent/30 bg-accent/5 space-y-1">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className={`text-xs px-1.5 py-0.5 rounded border ${primitiveTypeBg(selectedPrimitive.type)}`}>
                  {selectedPrimitive.type}
                </span>
                <span className="text-sm font-medium text-text">{selectedPrimitive.name}</span>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setSelectedPrimitive(null)}>
                Change
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="relative">
              <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-faint pointer-events-none" />
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search catalogue…"
                className="h-8 w-full pl-7 pr-3 rounded border bg-surface border-border-bright text-sm text-text placeholder:text-text-faint focus:outline-none focus:border-accent/40 transition-colors"
                autoFocus
              />
            </div>
            {searchLoading && (
              <div className="flex items-center gap-2 py-1 text-sm text-text-muted">
                <Loader2 size={12} className="animate-spin" /> Searching…
              </div>
            )}
            {searchResults && searchResults.items.length > 0 && (
              <div className="border border-border rounded overflow-hidden max-h-52 overflow-y-auto">
                {searchResults.items.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => setSelectedPrimitive(p)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-surface-el transition-colors border-b border-border last:border-0"
                  >
                    <span className={`text-xs px-1.5 py-0.5 rounded border shrink-0 ${primitiveTypeBg(p.type)}`}>
                      {p.type}
                    </span>
                    <span className="text-text">{p.name}</span>
                  </button>
                ))}
              </div>
            )}
            {searchResults && searchResults.items.length === 0 && searchQuery.trim().length > 1 && (
              <p className="text-sm text-text-faint py-1">No results for "{searchQuery}"</p>
            )}
          </div>
        )}

        {/* Workshop selector */}
        <Select
          label="Assign to workshop (optional)"
          value={workshopId}
          onValueChange={setWorkshopId}
          options={workshopOptions}
          placeholder="No workshop"
        />

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={() => handleClose(false)}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleConfirm}
            disabled={!activePath || addMutation.isPending}
          >
            {addMutation.isPending ? (
              <>
                <Loader2 size={12} className="animate-spin" /> Adding…
              </>
            ) : (
              'Add to inventory'
            )}
          </Button>
        </div>

        {addMutation.isError && (
          <p className="text-xs text-danger">
            {addMutation.error instanceof Error ? addMutation.error.message : 'Failed to add to inventory'}
          </p>
        )}
      </div>
    </Dialog>
  )
}
