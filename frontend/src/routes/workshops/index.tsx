import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Plus, Loader2, AlertCircle, FlaskConical } from 'lucide-react'
import {
  useWorkshopList,
  useCreateWorkshop,
  useSetActiveWorkshop,
  useActiveWorkshop,
} from '@/hooks/use-workshops'
import { Card, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { cn } from '@/lib/utils'
import type { Workshop } from '@/lib/types'

function WorkshopCard({
  workshop,
  isActive,
  onClick,
  onSetActive,
}: {
  workshop: Workshop
  isActive: boolean
  onClick: () => void
  onSetActive: () => void
}) {
  return (
    <Card
      hoverable
      onClick={onClick}
      className={cn(isActive && 'border-accent/30')}
    >
      <CardBody className="space-y-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            {workshop.icon ? (
              <span className="text-base">{workshop.icon}</span>
            ) : (
              <FlaskConical size={14} className="text-text-faint shrink-0" />
            )}
            <h3 className="text-sm font-semibold text-text leading-tight truncate">{workshop.name}</h3>
          </div>
          {isActive && <Badge variant="accent">Active</Badge>}
        </div>
        {workshop.description && (
          <p className="text-xs text-text-muted leading-relaxed line-clamp-2">{workshop.description}</p>
        )}
        {!isActive && (
          <button
            onClick={(e) => { e.stopPropagation(); onSetActive() }}
            className="text-xs text-text-faint hover:text-accent transition-colors"
          >
            Set as active
          </button>
        )}
      </CardBody>
    </Card>
  )
}

function CreateWorkshopDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const navigate = useNavigate()
  const createMutation = useCreateWorkshop()

  const handleCreate = () => {
    if (!name.trim()) return
    createMutation.mutate(
      { name: name.trim(), description: description.trim() },
      {
        onSuccess: (ws) => {
          onOpenChange(false)
          setName('')
          setDescription('')
          void navigate({ to: '/workshops/detail', search: { id: ws.id } })
        },
      },
    )
  }

  const handleClose = (open: boolean) => {
    if (!open) { setName(''); setDescription('') }
    onOpenChange(open)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose} title="Create workshop">
      <div className="space-y-3">
        <Input
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Leatherwork, 2024 Projects…"
          autoFocus
          onKeyDown={(e) => { if (e.key === 'Enter') handleCreate() }}
        />
        <Input
          label="Description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What this workshop is for"
        />
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={() => handleClose(false)}>Cancel</Button>
          <Button
            variant="primary"
            onClick={handleCreate}
            disabled={!name.trim() || createMutation.isPending}
          >
            {createMutation.isPending ? 'Creating…' : 'Create'}
          </Button>
        </div>
        {createMutation.isError && (
          <p className="text-xs text-danger">
            {createMutation.error instanceof Error
              ? createMutation.error.message
              : 'Failed to create workshop'}
          </p>
        )}
      </div>
    </Dialog>
  )
}

export function WorkshopsIndex() {
  const navigate = useNavigate()
  const [createOpen, setCreateOpen] = useState(false)

  const { data, isLoading, isError } = useWorkshopList()
  const { data: activeWorkshop } = useActiveWorkshop()
  const setActiveMutation = useSetActiveWorkshop()

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
        <AlertCircle size={16} /> Failed to load workshops.
      </div>
    )
  }

  const workshops = data?.items ?? []

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <h1 className="text-base font-semibold text-text">Workshops</h1>
        <Button variant="primary" size="sm" onClick={() => setCreateOpen(true)}>
          <Plus size={12} /> New workshop
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {workshops.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3 text-text-faint">
            <FlaskConical size={24} />
            <p className="text-sm">No workshops yet.</p>
            <Button variant="secondary" size="sm" onClick={() => setCreateOpen(true)}>
              <Plus size={12} /> Create your first workshop
            </Button>
          </div>
        ) : (
          <div className="space-y-3 pt-2">
            <p className="text-xs text-text-faint">
              {workshops.length} workshop{workshops.length !== 1 ? 's' : ''}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {workshops.map((ws: Workshop) => (
                <WorkshopCard
                  key={ws.id}
                  workshop={ws}
                  isActive={activeWorkshop?.id === ws.id}
                  onClick={() => void navigate({ to: '/workshops/detail', search: { id: ws.id } })}
                  onSetActive={() => setActiveMutation.mutate(ws.id)}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      <CreateWorkshopDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  )
}
