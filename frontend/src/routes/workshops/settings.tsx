import { useState } from 'react'
import { useNavigate, Link } from '@tanstack/react-router'
import {
  AlertCircle,
  ArrowLeft,
  ArrowDown,
  ArrowUp,
  Check,
  Loader2,
  Plus,
  Trash2,
  X,
} from 'lucide-react'
import { useWorkshop, useUpdateWorkshop, useDeleteWorkshop } from '@/hooks/use-workshops'
import {
  useWorkshopModuleList,
  useAddWorkshopModule,
  useRemoveWorkshopModule,
  useUpdateWorkshopModuleSortOrder,
  useInstalledModules,
} from '@/hooks/use-workshop-modules'
import { useWorkshopContext } from '@/context/WorkshopContext'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Separator } from '@/components/ui/Separator'
import type { WorkshopModule } from '@/lib/types'

// ---------------------------------------------------------------------------
// Workshop name / description editor
// ---------------------------------------------------------------------------

function WorkshopInfoSection({ id }: { id: string }) {
  const { data: ws, isLoading } = useWorkshop(id)
  const updateMutation = useUpdateWorkshop()

  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [editing, setEditing] = useState(false)

  if (isLoading || !ws) return null

  const startEdit = () => {
    setName(ws.name)
    setDesc(ws.description)
    setEditing(true)
  }

  const handleSave = () => {
    if (!name.trim()) return
    updateMutation.mutate(
      { id, data: { name: name.trim(), description: desc.trim() } },
      { onSuccess: () => setEditing(false) },
    )
  }

  return (
    <section>
      <h2 className="text-xs font-semibold text-text-faint uppercase tracking-widest mb-3">
        Workshop
      </h2>
      {editing ? (
        <div className="space-y-2">
          <div>
            <label className="block text-xs text-text-muted mb-1">Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSave() }}
              className="h-8 w-full rounded border bg-surface border-border-bright text-sm text-text px-2.5 focus:outline-none focus:border-accent/40 transition-colors"
              autoFocus
            />
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Description</label>
            <input
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              placeholder="Optional description"
              className="h-8 w-full rounded border bg-surface border-border-bright text-sm text-text px-2.5 focus:outline-none focus:border-accent/40 transition-colors placeholder:text-text-faint"
            />
          </div>
          <div className="flex gap-2 pt-1">
            <Button
              variant="primary"
              size="sm"
              onClick={handleSave}
              disabled={!name.trim() || updateMutation.isPending}
            >
              {updateMutation.isPending ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />}
              Save
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
          {updateMutation.isError && (
            <p className="text-xs text-danger">Failed to save.</p>
          )}
        </div>
      ) : (
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-0.5">
              {ws.icon && <span className="text-base">{ws.icon}</span>}
              <p className="text-sm font-medium text-text">{ws.name}</p>
            </div>
            {ws.description && (
              <p className="text-xs text-text-muted">{ws.description}</p>
            )}
          </div>
          <Button variant="secondary" size="sm" onClick={startEdit}>
            Edit
          </Button>
        </div>
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Module row — shows association + reorder arrows + remove button
// ---------------------------------------------------------------------------

function ModuleRow({
  mod,
  isFirst,
  isLast,
  onMoveUp,
  onMoveDown,
  onRemove,
  isPending,
}: {
  mod: WorkshopModule
  isFirst: boolean
  isLast: boolean
  onMoveUp: () => void
  onMoveDown: () => void
  onRemove: () => void
  isPending: boolean
}) {
  return (
    <div className="flex items-center gap-2 py-2 border-b border-border last:border-0">
      {/* Reorder */}
      <div className="flex flex-col gap-0.5 shrink-0">
        <button
          onClick={onMoveUp}
          disabled={isFirst || isPending}
          className="text-text-faint hover:text-text disabled:opacity-25 transition-colors p-0.5 rounded"
          title="Move up"
        >
          <ArrowUp size={11} />
        </button>
        <button
          onClick={onMoveDown}
          disabled={isLast || isPending}
          className="text-text-faint hover:text-text disabled:opacity-25 transition-colors p-0.5 rounded"
          title="Move down"
        >
          <ArrowDown size={11} />
        </button>
      </div>

      {/* Module name */}
      <span className="flex-1 text-sm text-text font-mono">{mod.module_name}</span>

      {/* Remove */}
      <button
        onClick={onRemove}
        disabled={isPending}
        className="text-text-faint hover:text-danger transition-colors p-1 rounded disabled:opacity-50"
        title="Remove from workshop"
      >
        <X size={12} />
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Module list section
// ---------------------------------------------------------------------------

function ModulesSection({ id }: { id: string }) {
  const { data: associations, isLoading } = useWorkshopModuleList(id)
  const addMutation = useAddWorkshopModule(id)
  const removeMutation = useRemoveWorkshopModule(id)
  const reorderMutation = useUpdateWorkshopModuleSortOrder(id)
  const { data: allModules } = useInstalledModules()
  const { switchWorkshop, activeWorkshop } = useWorkshopContext()

  const [addOpen, setAddOpen] = useState(false)

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-4 text-text-muted">
        <Loader2 size={12} className="animate-spin" />
        <span className="text-xs">Loading modules…</span>
      </div>
    )
  }

  const mods = associations ?? []

  // Installed modules not yet associated with this workshop.
  const associated = new Set(mods.map((m) => m.module_name))
  const available = (allModules?.items ?? []).filter((m) => !associated.has(m.name))

  const isPending =
    addMutation.isPending || removeMutation.isPending || reorderMutation.isPending

  const handleMoveUp = (index: number) => {
    const mod = mods[index]
    reorderMutation.mutate({ module_name: mod.module_name, sort_order: index - 1 })
  }

  const handleMoveDown = (index: number) => {
    const mod = mods[index]
    reorderMutation.mutate({ module_name: mod.module_name, sort_order: index + 1 })
  }

  const handleRemove = (moduleName: string) => {
    removeMutation.mutate(moduleName, {
      onSuccess: () => {
        // Refresh workshop context if this is the active workshop.
        if (activeWorkshop?.id === id) {
          switchWorkshop(id)
        }
      },
    })
  }

  const handleAdd = (moduleName: string) => {
    addMutation.mutate(
      { module_name: moduleName, sort_order: mods.length },
      {
        onSuccess: () => {
          setAddOpen(false)
          if (activeWorkshop?.id === id) {
            switchWorkshop(id)
          }
        },
      },
    )
  }

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-semibold text-text-faint uppercase tracking-widest">
          Modules
        </h2>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setAddOpen(true)}
          disabled={available.length === 0}
          title={available.length === 0 ? 'All installed modules are already associated' : undefined}
        >
          <Plus size={11} /> Add module
        </Button>
      </div>

      {mods.length === 0 ? (
        <p className="text-xs text-text-faint py-3">
          No modules associated. Add one to enable module views in this workshop's nav.
        </p>
      ) : (
        <div>
          {mods.map((mod, i) => (
            <ModuleRow
              key={mod.module_name}
              mod={mod}
              isFirst={i === 0}
              isLast={i === mods.length - 1}
              onMoveUp={() => handleMoveUp(i)}
              onMoveDown={() => handleMoveDown(i)}
              onRemove={() => handleRemove(mod.module_name)}
              isPending={isPending}
            />
          ))}
        </div>
      )}

      {/* Add module dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen} title="Add module to workshop">
        <div className="space-y-1">
          {available.length === 0 ? (
            <p className="text-xs text-text-faint py-2">No more installed modules to add.</p>
          ) : (
            available.map((m) => (
              <button
                key={m.name}
                onClick={() => handleAdd(m.name)}
                disabled={addMutation.isPending}
                className="w-full flex items-center gap-2 px-3 py-2 rounded text-sm text-left hover:bg-surface-el transition-colors disabled:opacity-50"
              >
                <span className="flex-1 font-mono text-text">{m.name}</span>
                {!m.loaded && (
                  <span className="text-[10px] text-text-faint">not loaded</span>
                )}
              </button>
            ))
          )}
        </div>
      </Dialog>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Danger zone — delete workshop
// ---------------------------------------------------------------------------

function DangerSection({ id }: { id: string }) {
  const navigate = useNavigate()
  const { switchWorkshop, activeWorkshop } = useWorkshopContext()
  const deleteMutation = useDeleteWorkshop()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const { data: ws } = useWorkshop(id)

  const handleDelete = () => {
    deleteMutation.mutate(id, {
      onSuccess: () => {
        if (activeWorkshop?.id === id) {
          switchWorkshop(null)
        } else {
          void navigate({ to: '/workshops', search: {} })
        }
      },
    })
  }

  return (
    <section>
      <h2 className="text-xs font-semibold text-danger/70 uppercase tracking-widest mb-3">
        Danger zone
      </h2>
      <div className="rounded border border-danger/20 bg-danger/5 px-3 py-2.5 flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-medium text-text">Delete workshop</p>
          <p className="text-xs text-text-faint mt-0.5">
            Removes this workshop and all module associations. Primitives in the catalogue are unaffected.
          </p>
        </div>
        <Button
          variant="danger"
          size="sm"
          onClick={() => setConfirmOpen(true)}
          className="shrink-0"
        >
          <Trash2 size={11} /> Delete
        </Button>
      </div>

      <Dialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Delete workshop"
        description={`Delete "${ws?.name ?? id}"? This cannot be undone. Primitives and module data are not affected.`}
      >
        <div className="flex justify-end gap-2 mt-2">
          <Button variant="ghost" onClick={() => setConfirmOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? 'Deleting…' : 'Delete'}
          </Button>
        </div>
      </Dialog>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Page root
// ---------------------------------------------------------------------------

function WorkshopSettingsView({ id }: { id: string }) {
  const { data: ws, isLoading, isError } = useWorkshop(id)

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-20 justify-center text-text-muted">
        <Loader2 size={14} className="animate-spin" />
      </div>
    )
  }

  if (isError || !ws) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3 text-danger/70">
        <AlertCircle size={20} />
        <p className="text-sm">Workshop not found.</p>
      </div>
    )
  }

  return (
    <div className="max-w-lg space-y-6">
      {/* Back link */}
      <Link
        to="/workshop/$id"
        params={{ id }}
        className="inline-flex items-center gap-1.5 text-xs text-text-faint hover:text-text transition-colors"
      >
        <ArrowLeft size={11} />
        Back to {ws.name}
      </Link>

      <WorkshopInfoSection id={id} />
      <Separator />
      <ModulesSection id={id} />
      <Separator />
      <DangerSection id={id} />
    </div>
  )
}

export function WorkshopSettings({ id }: { id: string }) {
  if (!id) {
    return <div className="p-4 text-sm text-text-faint">No workshop ID specified.</div>
  }

  return (
    <div className="p-4 overflow-y-auto">
      <h1 className="text-sm font-semibold text-text mb-4">Workshop settings</h1>
      <WorkshopSettingsView id={id} />
    </div>
  )
}
