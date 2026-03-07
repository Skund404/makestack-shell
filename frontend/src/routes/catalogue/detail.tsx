import { useState } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import {
  Edit2, Trash2, ChevronDown, ChevronRight,
  GitBranch, Loader2, AlertCircle,
} from 'lucide-react'
import { usePrimitive, useRelationships, useDeletePrimitive } from '@/hooks/use-catalogue'
import { PropertyRenderer } from '@/components/catalogue/PropertyRenderer'
import { StepRenderer } from '@/components/catalogue/StepRenderer'
import { RelationshipsPanel } from '@/components/catalogue/RelationshipsPanel'
import { VersionTimeline } from '@/components/version/VersionTimeline'
import { VersionCompare } from '@/components/version/VersionCompare'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Separator } from '@/components/ui/Separator'
import { formatDateTime, primitiveTypeBg, abbreviateHash } from '@/lib/utils'
import type { Primitive } from '@/lib/types'

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

interface DetailViewProps {
  path: string
  at?: string
}

function PrimitiveDetailView({ path, at }: DetailViewProps) {
  const navigate = useNavigate()
  const { data, isLoading, isError } = usePrimitive(path, at)
  const { data: relData } = useRelationships(path)
  const deleteMutation = useDeletePrimitive()
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [historyHash, setHistoryHash] = useState<string | undefined>()

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
        <p className="text-sm">Primitive not found.</p>
      </div>
    )
  }

  const p: Primitive = data
  const context = { primitiveType: p.type, primitivePath: p.path }
  const hasSteps = Boolean((p.manifest?.steps as unknown[] | undefined)?.length)
  const hasRelationships = (relData?.length ?? 0) > 0
  const hasProperties = p.properties && Object.keys(p.properties).length > 0

  const handleDelete = () => {
    deleteMutation.mutate(path, {
      onSuccess: () => void navigate({ to: '/catalogue', search: { type: undefined } }),
    })
  }

  return (
    <div className="max-w-3xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs px-1.5 py-0.5 rounded border ${primitiveTypeBg(p.type)}`}>
              {p.type}
            </span>
            {at && (
              <Badge variant="warning">
                <GitBranch size={10} /> version {abbreviateHash(at)}
              </Badge>
            )}
          </div>
          <h1 className="text-xl font-semibold text-text leading-tight">{p.name}</h1>
          {p.description && (
            <p className="text-sm text-text-muted mt-1 leading-relaxed">{p.description}</p>
          )}
        </div>
        {!at && (
          <div className="flex items-center gap-2 shrink-0">
            <Link to="/catalogue/edit" search={{ path }}>
              <Button variant="secondary" size="sm">
                <Edit2 size={12} /> Edit
              </Button>
            </Link>
            <Button variant="danger" size="sm" onClick={() => setDeleteOpen(true)}>
              <Trash2 size={12} />
            </Button>
          </div>
        )}
      </div>

      {/* Tags */}
      {p.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-4">
          {p.tags.map((tag) => (
            <Badge key={String(tag)} variant="muted">{String(tag)}</Badge>
          ))}
        </div>
      )}

      <Separator className="mb-4" />

      {/* Meta */}
      <div className="grid grid-cols-2 gap-2 text-xs text-text-faint mb-4">
        <div><span className="text-text-muted">Created</span> {formatDateTime(p.created)}</div>
        <div><span className="text-text-muted">Modified</span> {formatDateTime(p.modified)}</div>
        <div className="font-mono col-span-2 text-text-faint/60">{p.path}</div>
      </div>

      {/* Properties */}
      {hasProperties && (
        <CollapsibleSection label="Properties" defaultOpen>
          <PropertyRenderer properties={p.properties!} context={context} />
        </CollapsibleSection>
      )}

      {/* Steps */}
      {hasSteps && (
        <CollapsibleSection label="Steps" defaultOpen>
          <StepRenderer steps={p.manifest.steps as unknown[]} context={context} />
        </CollapsibleSection>
      )}

      {/* Relationships */}
      {hasRelationships && (
        <CollapsibleSection label="Relationships" defaultOpen>
          <RelationshipsPanel path={path} />
        </CollapsibleSection>
      )}

      {/* Version history */}
      <Separator className="my-4" />
      <CollapsibleSection label="Version History">
        <div className="space-y-4">
          <VersionTimeline
            path={path}
            selectedHash={historyHash}
            onSelectHash={(hash) => {
              setHistoryHash(hash)
              void navigate({ to: '/catalogue/detail', search: { path, at: hash as string } })
            }}
          />
        </div>
      </CollapsibleSection>

      <CollapsibleSection label="Compare Versions">
        <VersionCompare path={path} />
      </CollapsibleSection>

      {/* Delete dialog */}
      <Dialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete primitive"
        description={`Are you sure you want to delete "${p.name}"? This action cannot be undone.`}
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
    </div>
  )
}

interface CatalogueDetailPageProps {
  path: string
  at?: string
}

export function CatalogueDetail({ path, at }: CatalogueDetailPageProps) {
  if (!path) {
    return (
      <div className="p-4 text-sm text-text-faint">
        No primitive path specified.
      </div>
    )
  }

  return (
    <div className="p-4 overflow-y-auto">
      <PrimitiveDetailView path={path} at={at} />
    </div>
  )
}
