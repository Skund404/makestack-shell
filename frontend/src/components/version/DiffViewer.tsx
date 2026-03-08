import { Loader2, Minus, Plus } from 'lucide-react'
import { usePrimitiveDiff } from '@/hooks/use-version'
import { abbreviateHash, formatDateTime } from '@/lib/utils'
import type { FieldChange } from '@/lib/types'

interface DiffViewerProps {
  path: string
  fromHash: string
  toHash: string
}

function renderValue(val: unknown): string {
  if (val === null || val === undefined) return '—'
  if (typeof val === 'object') return JSON.stringify(val, null, 2)
  return String(val)
}

function ChangeRow({ change }: { change: FieldChange }) {
  const isAdded = change.type === 'added'
  const isRemoved = change.type === 'removed'

  return (
    <div className="grid grid-cols-[1fr_1fr] gap-2 py-2 border-b border-border text-xs">
      <div>
        <div className="text-text-faint mb-1 font-mono">{change.field}</div>
        {!isAdded ? (
          <div className="flex gap-1.5">
            <Minus size={11} className="text-danger shrink-0 mt-0.5" />
            <pre className={`text-xs font-mono whitespace-pre-wrap break-all ${isRemoved ? 'text-danger/80' : 'text-text-muted line-through'}`}>
              {renderValue(change.old_value)}
            </pre>
          </div>
        ) : (
          <span className="text-text-faint italic">—</span>
        )}
      </div>
      <div>
        <div className="text-text-faint mb-1 font-mono opacity-0">{change.field}</div>
        {!isRemoved ? (
          <div className="flex gap-1.5">
            <Plus size={11} className="text-success shrink-0 mt-0.5" />
            <pre className={`text-xs font-mono whitespace-pre-wrap break-all ${isAdded ? 'text-success/80' : 'text-success/70'}`}>
              {renderValue(change.new_value)}
            </pre>
          </div>
        ) : (
          <span className="text-text-faint italic">—</span>
        )}
      </div>
    </div>
  )
}

export function DiffViewer({ path, fromHash, toHash }: DiffViewerProps) {
  const { data, isLoading, isError } = usePrimitiveDiff(path, fromHash, toHash)

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-4 text-sm text-text-muted">
        <Loader2 size={13} className="animate-spin" />
        Loading diff…
      </div>
    )
  }

  if (isError || !data) {
    return <p className="text-sm text-danger/70 py-4">Failed to load diff.</p>
  }

  return (
    <div>
      <div className="flex items-center gap-4 mb-3 text-xs text-text-faint">
        <span>
          <code className="font-mono">{abbreviateHash(data.from_hash)}</code>
          {data.from_timestamp && ` · ${formatDateTime(data.from_timestamp)}`}
        </span>
        <span className="text-text-faint">→</span>
        <span>
          <code className="font-mono">{abbreviateHash(data.to_hash)}</code>
          {data.to_timestamp && ` · ${formatDateTime(data.to_timestamp)}`}
        </span>
      </div>
      {data.changes.length === 0 ? (
        <p className="text-sm text-text-faint italic py-2">No changes between these versions.</p>
      ) : (
        <div>
          <div className="grid grid-cols-[1fr_1fr] gap-2 pb-1 text-xs font-medium text-text-faint border-b border-border mb-1">
            <span>Before</span>
            <span>After</span>
          </div>
          {data.changes.map((change, i) => (
            <ChangeRow key={`${change.field}-${i}`} change={change} />
          ))}
        </div>
      )}
    </div>
  )
}
