import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import {
  Loader2,
  AlertCircle,
  Plus,
  Trash2,
  X,
  Search,
  Edit2,
  Check,
} from 'lucide-react'
import {
  useWorkshop,
  useUpdateWorkshop,
  useDeleteWorkshop,
  useAddToWorkshop,
  useRemoveFromWorkshop,
  useSetActiveWorkshop,
  useActiveWorkshop,
} from '@/hooks/use-workshops'
import { useSearch } from '@/hooks/use-catalogue'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Separator } from '@/components/ui/Separator'
import { primitiveTypeBg } from '@/lib/utils'
import type { Primitive, WorkshopMember } from '@/lib/types'

function AddPrimitiveDialog({
  workshopId,
  open,
  onOpenChange,
}: {
  workshopId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [query, setQuery] = useState('')
  const { data: results, isLoading } = useSearch(query, query.trim().length > 1)
  const addMutation = useAddToWorkshop()

  const handleSelect = (p: Primitive) => {
    addMutation.mutate(
      { workshopId, primitive_path: p.path, primitive_type: p.type },
      { onSuccess: () => { onOpenChange(false); setQuery('') } },
    )
  }

  const handleClose = (open: boolean) => {
    if (!open) setQuery('')
    onOpenChange(open)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose} title="Add primitive to workshop">
      <div className="space-y-3">
        <div className="relative">
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-faint pointer-events-none" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search catalogue…"
            className="h-8 w-full pl-7 pr-3 rounded border bg-surface border-border-bright text-sm text-text placeholder:text-text-faint focus:outline-none focus:border-accent/40 transition-colors"
            autoFocus
          />
        </div>
        {isLoading && (
          <div className="flex items-center gap-2 text-sm text-text-muted">
            <Loader2 size={12} className="animate-spin" /> Searching…
          </div>
        )}
        {results && results.items.length > 0 && (
          <div className="border border-border rounded overflow-hidden max-h-64 overflow-y-auto">
            {results.items.map((p) => (
              <button
                key={p.id}
                onClick={() => handleSelect(p)}
                disabled={addMutation.isPending}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-surface-el transition-colors border-b border-border last:border-0 disabled:opacity-50"
              >
                <span className={`text-xs px-1.5 py-0.5 rounded border shrink-0 ${primitiveTypeBg(p.type)}`}>
                  {p.type}
                </span>
                <span className="text-text">{p.name}</span>
              </button>
            ))}
          </div>
        )}
        {results && results.items.length === 0 && query.trim().length > 1 && (
          <p className="text-sm text-text-faint">No results for "{query}"</p>
        )}
        {addMutation.isError && (
          <p className="text-xs text-danger">Failed to add primitive.</p>
        )}
      </div>
    </Dialog>
  )
}

function slugToTitle(path: string): string {
  const parts = path.split('/')
  const slug = parts.length >= 2 ? parts[1] : parts[0]
  return slug
    .split('-')
    .map((w: string) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function MemberRow({
  member,
  onRemove,
}: {
  member: WorkshopMember
  onRemove: () => void
}) {
  const navigate = useNavigate()

  return (
    <div className="flex items-center gap-2 py-2 border-b border-border last:border-0 group">
      <span className={`text-xs px-1.5 py-0.5 rounded border shrink-0 ${primitiveTypeBg(member.primitive_type)}`}>
        {member.primitive_type}
      </span>
      <button
        onClick={() =>
          void navigate({
            to: '/catalogue/detail',
            search: { path: member.primitive_path, at: undefined },
          })
        }
        className="flex-1 text-sm text-text-muted hover:text-accent transition-colors text-left truncate"
      >
        {slugToTitle(member.primitive_path)}
      </button>
      <button
        onClick={onRemove}
        className="text-text-faint hover:text-danger opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded"
        title="Remove from workshop"
      >
        <X size={12} />
      </button>
    </div>
  )
}

function WorkshopDetailView({ id }: { id: string }) {
  const navigate = useNavigate()
  const { data, isLoading, isError } = useWorkshop(id)
  const { data: activeWorkshop } = useActiveWorkshop()
  const updateMutation = useUpdateWorkshop()
  const deleteMutation = useDeleteWorkshop()
  const removeMemberMutation = useRemoveFromWorkshop()
  const setActiveMutation = useSetActiveWorkshop()

  const [editing, setEditing] = useState(false)
  const [editName, setEditName] = useState('')
  const [editDesc, setEditDesc] = useState('')
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [addOpen, setAddOpen] = useState(false)

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
        <p className="text-sm">Workshop not found.</p>
      </div>
    )
  }

  const ws = data
  const isActive = activeWorkshop?.id === ws.id

  const startEdit = () => {
    setEditName(ws.name)
    setEditDesc(ws.description)
    setEditing(true)
  }

  const handleSaveEdit = () => {
    if (!editName.trim()) return
    updateMutation.mutate(
      { id, data: { name: editName.trim(), description: editDesc.trim() } },
      { onSuccess: () => setEditing(false) },
    )
  }

  const handleDelete = () => {
    deleteMutation.mutate(id, {
      onSuccess: () => void navigate({ to: '/workshops', search: {} }),
    })
  }

  // Group members by primitive type
  const membersByType: Record<string, typeof ws.members> = {}
  for (const m of ws.members) {
    if (!membersByType[m.primitive_type]) membersByType[m.primitive_type] = []
    membersByType[m.primitive_type].push(m)
  }

  return (
    <div className="max-w-3xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex-1 min-w-0">
          {editing ? (
            <div className="space-y-2">
              <input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="text-xl font-semibold bg-transparent border-b border-accent/40 text-text w-full focus:outline-none pb-0.5"
                autoFocus
                onKeyDown={(e) => { if (e.key === 'Enter') handleSaveEdit() }}
              />
              <input
                value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)}
                className="text-sm bg-transparent border-b border-border text-text-muted w-full focus:outline-none pb-0.5 placeholder:text-text-faint"
                placeholder="Description"
              />
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2 mb-1">
                {ws.icon && <span className="text-xl">{ws.icon}</span>}
                <h1 className="text-xl font-semibold text-text leading-tight">{ws.name}</h1>
                {isActive && <Badge variant="accent">Active</Badge>}
              </div>
              {ws.description && (
                <p className="text-sm text-text-muted mt-1">{ws.description}</p>
              )}
            </>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {editing ? (
            <>
              <Button
                variant="primary"
                size="sm"
                onClick={handleSaveEdit}
                disabled={!editName.trim() || updateMutation.isPending}
              >
                <Check size={12} /> Save
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </>
          ) : (
            <>
              {!isActive && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setActiveMutation.mutate(ws.id)}
                  disabled={setActiveMutation.isPending}
                >
                  Set active
                </Button>
              )}
              <Button variant="secondary" size="sm" onClick={startEdit}>
                <Edit2 size={12} /> Edit
              </Button>
              <Button variant="danger" size="sm" onClick={() => setDeleteOpen(true)}>
                <Trash2 size={12} />
              </Button>
            </>
          )}
        </div>
      </div>

      <Separator className="mb-4" />

      {/* Members */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-text">
            Primitives
            {ws.members.length > 0 && (
              <span className="text-text-faint ml-2 font-normal">({ws.members.length})</span>
            )}
          </h2>
          <Button variant="secondary" size="sm" onClick={() => setAddOpen(true)}>
            <Plus size={12} /> Add primitive
          </Button>
        </div>

        {ws.members.length === 0 ? (
          <div className="py-8 text-center text-text-faint text-sm">
            No primitives in this workshop.
            <br />
            <button
              onClick={() => setAddOpen(true)}
              className="text-accent hover:underline mt-1"
            >
              Add one from the catalogue →
            </button>
          </div>
        ) : (
          Object.entries(membersByType).map(([type, members]) => (
            <div key={type}>
              <p className="text-xs font-semibold text-text-faint uppercase tracking-wide mb-1">
                {type}s ({members.length})
              </p>
              {members.map((m) => (
                <MemberRow
                  key={m.primitive_path}
                  member={m}
                  onRemove={() =>
                    removeMemberMutation.mutate({
                      workshopId: id,
                      primitivePath: m.primitive_path,
                    })
                  }
                />
              ))}
            </div>
          ))
        )}
      </div>

      {/* Delete dialog */}
      <Dialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete workshop"
        description={`Delete "${ws.name}"? This removes the workshop container — primitives in the catalogue are not affected. This cannot be undone.`}
      >
        <div className="flex justify-end gap-2 mt-2">
          <Button variant="ghost" onClick={() => setDeleteOpen(false)}>Cancel</Button>
          <Button
            variant="danger"
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? 'Deleting…' : 'Delete'}
          </Button>
        </div>
      </Dialog>

      <AddPrimitiveDialog workshopId={id} open={addOpen} onOpenChange={setAddOpen} />
    </div>
  )
}

export function WorkshopsDetail({ id }: { id: string }) {
  if (!id) {
    return <div className="p-4 text-sm text-text-faint">No workshop ID specified.</div>
  }

  return (
    <div className="p-4 overflow-y-auto">
      <WorkshopDetailView id={id} />
    </div>
  )
}
