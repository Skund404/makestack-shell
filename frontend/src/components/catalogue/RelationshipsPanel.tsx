import { useNavigate } from '@tanstack/react-router'
import { useRelationships } from '@/hooks/use-catalogue'
import { primitiveTypeBg } from '@/lib/utils'
import type { Relationship } from '@/lib/types'

interface RelationshipsPanelProps {
  path: string
}

function RelationshipRow({ rel, onNavigate }: { rel: Relationship; onNavigate: (path: string) => void }) {
  const targetPath = rel.target_path
  const targetType = rel.target_type || 'unknown'
  const label = targetPath.split('/').slice(-2, -1)[0] ?? targetPath

  return (
    <button
      onClick={() => onNavigate(targetPath)}
      className="w-full text-left flex items-center gap-2.5 px-3 py-2 rounded border border-transparent hover:border-border-bright hover:bg-surface-el transition-colors"
    >
      <span className={`text-xs px-1.5 py-0.5 rounded border shrink-0 ${primitiveTypeBg(targetType)}`}>
        {targetType || '?'}
      </span>
      <span className="text-sm text-text-muted hover:text-text">{label}</span>
      <span className="text-xs text-text-faint ml-auto">{rel.relationship_type}</span>
    </button>
  )
}

export function RelationshipsPanel({ path }: RelationshipsPanelProps) {
  const { data, isLoading } = useRelationships(path)
  const navigate = useNavigate()

  if (isLoading || !data || data.length === 0) return null

  return (
    <div className="space-y-1">
      {data.map((rel, i) => (
        <RelationshipRow
          key={i}
          rel={rel}
          onNavigate={(p) => void navigate({ to: '/catalogue/detail', search: { path: p, at: undefined } })}
        />
      ))}
    </div>
  )
}
