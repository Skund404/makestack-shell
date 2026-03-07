/**
 * Shared form for creating and editing primitives.
 */
import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input, Textarea } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import type { Primitive, PrimitiveCreate, PrimitiveUpdate } from '@/lib/types'

const PRIMITIVE_TYPES = [
  { value: 'tool',      label: 'Tool' },
  { value: 'material',  label: 'Material' },
  { value: 'technique', label: 'Technique' },
  { value: 'workflow',  label: 'Workflow' },
  { value: 'project',   label: 'Project' },
  { value: 'event',     label: 'Event' },
]

interface PrimitiveFormProps {
  initial?: Primitive
  onSubmit: (data: PrimitiveCreate | PrimitiveUpdate) => void
  isSubmitting?: boolean
  mode: 'create' | 'edit'
}

interface TagEditorProps {
  tags: string[]
  onChange: (tags: string[]) => void
}

function TagEditor({ tags, onChange }: TagEditorProps) {
  const [input, setInput] = useState('')

  const addTag = () => {
    const t = input.trim()
    if (t && !tags.includes(t)) {
      onChange([...tags, t])
      setInput('')
    }
  }

  return (
    <div className="space-y-1.5">
      <span className="text-xs font-medium text-text-muted">Tags</span>
      <div className="flex flex-wrap gap-1.5 mb-1.5">
        {tags.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-surface-el border border-border-bright text-text-muted"
          >
            {tag}
            <button
              type="button"
              onClick={() => onChange(tags.filter((t) => t !== tag))}
              className="hover:text-danger transition-colors"
            >
              ×
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTag() } }}
          placeholder="Add tag…"
          className="h-7 px-2.5 rounded border bg-surface-el text-text text-xs border-border-bright placeholder:text-text-faint focus:outline-none focus:border-accent/40 flex-1"
        />
        <Button type="button" onClick={addTag} variant="ghost" size="sm">
          <Plus size={12} />
        </Button>
      </div>
    </div>
  )
}

interface RelationshipEditorProps {
  relationships: Array<{ type: string; target: string }>
  onChange: (rels: Array<{ type: string; target: string }>) => void
}

function RelationshipEditor({ relationships, onChange }: RelationshipEditorProps) {
  const add = () => onChange([...relationships, { type: '', target: '' }])
  const remove = (i: number) => onChange(relationships.filter((_, idx) => idx !== i))
  const update = (i: number, field: 'type' | 'target', val: string) =>
    onChange(relationships.map((r, idx) => idx === i ? { ...r, [field]: val } : r))

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-text-muted">Relationships</span>
        <Button type="button" onClick={add} variant="ghost" size="sm">
          <Plus size={12} /> Add
        </Button>
      </div>
      {relationships.map((rel, i) => (
        <div key={i} className="flex gap-2 items-center">
          <input
            value={rel.type}
            onChange={(e) => update(i, 'type', e.target.value)}
            placeholder="type (e.g. uses_tool)"
            className="h-7 px-2 rounded border bg-surface-el text-text text-xs border-border-bright placeholder:text-text-faint focus:outline-none focus:border-accent/40 w-40"
          />
          <input
            value={rel.target}
            onChange={(e) => update(i, 'target', e.target.value)}
            placeholder="target path"
            className="h-7 px-2 rounded border bg-surface-el text-text text-xs border-border-bright placeholder:text-text-faint focus:outline-none focus:border-accent/40 flex-1 font-mono"
          />
          <Button type="button" onClick={() => remove(i)} variant="ghost" size="sm">
            <Trash2 size={12} className="text-danger" />
          </Button>
        </div>
      ))}
    </div>
  )
}

export function PrimitiveForm({ initial, onSubmit, isSubmitting, mode }: PrimitiveFormProps) {
  const [type, setType] = useState(initial?.type ?? 'tool')
  const [name, setName] = useState(initial?.name ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [tags, setTags] = useState<string[]>(initial?.tags ?? [])
  const [relationships, setRelationships] = useState<Array<{ type: string; target: string }>>(
    () => {
      const rels = (initial?.manifest?.relationships as Array<{ type: string; target: string }> | undefined) ?? []
      return rels
    }
  )
  const [propsRaw, setPropsRaw] = useState(
    initial?.properties ? JSON.stringify(initial.properties, null, 2) : '{}'
  )
  const [propsError, setPropsError] = useState('')
  const [stepsRaw, setStepsRaw] = useState(() => {
    const steps = (initial?.manifest?.steps as unknown[] | undefined) ?? []
    return steps.length > 0 ? JSON.stringify(steps, null, 2) : ''
  })

  const hasSteps = type === 'technique' || type === 'workflow'

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    let properties: Record<string, unknown> | undefined
    try {
      const parsed = JSON.parse(propsRaw || '{}') as unknown
      properties = typeof parsed === 'object' && parsed !== null ? (parsed as Record<string, unknown>) : undefined
      setPropsError('')
    } catch {
      setPropsError('Invalid JSON')
      return
    }

    let steps: unknown[] | undefined
    if (hasSteps && stepsRaw.trim()) {
      try {
        const parsed = JSON.parse(stepsRaw) as unknown
        steps = Array.isArray(parsed) ? parsed : undefined
      } catch {
        return
      }
    }

    if (mode === 'edit' && initial) {
      onSubmit({
        id: initial.id,
        type,
        name,
        slug: initial.slug,
        description,
        tags,
        properties,
        steps,
        relationships,
      } satisfies PrimitiveUpdate)
    } else {
      onSubmit({
        type,
        name,
        description,
        tags,
        properties,
        steps,
        relationships,
      } satisfies PrimitiveCreate)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="grid grid-cols-2 gap-4">
        <Select
          label="Type"
          value={type}
          onValueChange={setType}
          options={PRIMITIVE_TYPES}
          disabled={mode === 'edit'}
        />
        <Input
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          placeholder="e.g. Saddle Stitching"
        />
      </div>

      <Textarea
        label="Description"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="What is this? How is it used?"
        className="min-h-[80px]"
      />

      <TagEditor tags={tags} onChange={setTags} />

      {hasSteps && (
        <div className="space-y-1">
          <label className="text-xs font-medium text-text-muted">Steps (JSON array)</label>
          <textarea
            value={stepsRaw}
            onChange={(e) => setStepsRaw(e.target.value)}
            placeholder='[{"text": "First step..."}, "Second step as plain string"]'
            className="w-full px-3 py-2 rounded border bg-surface-el text-text text-xs border-border-bright font-mono placeholder:text-text-faint focus:outline-none focus:border-accent/40 min-h-[100px] resize-y"
          />
        </div>
      )}

      <div className="space-y-1">
        <label className="text-xs font-medium text-text-muted">Properties (JSON object)</label>
        <textarea
          value={propsRaw}
          onChange={(e) => setPropsRaw(e.target.value)}
          className="w-full px-3 py-2 rounded border bg-surface-el text-text text-xs border-border-bright font-mono focus:outline-none focus:border-accent/40 min-h-[80px] resize-y"
        />
        {propsError && <p className="text-xs text-danger">{propsError}</p>}
      </div>

      <RelationshipEditor relationships={relationships} onChange={setRelationships} />

      <div className="flex justify-end pt-2">
        <Button type="submit" variant="primary" disabled={isSubmitting || !name.trim()}>
          {isSubmitting ? 'Saving…' : mode === 'create' ? 'Create Primitive' : 'Save Changes'}
        </Button>
      </div>
    </form>
  )
}
