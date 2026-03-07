import { GitCommit, Loader2 } from 'lucide-react'
import { usePrimitiveHistory } from '@/hooks/use-version'
import { abbreviateHash, formatDateTime } from '@/lib/utils'

interface VersionTimelineProps {
  path: string
  selectedHash?: string
  onSelectHash?: (hash: string) => void
}

export function VersionTimeline({ path, selectedHash, onSelectHash }: VersionTimelineProps) {
  const { data, isLoading, isError } = usePrimitiveHistory(path, 50)

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-4 text-sm text-text-muted">
        <Loader2 size={13} className="animate-spin" />
        Loading history…
      </div>
    )
  }

  if (isError || !data) {
    return <p className="text-sm text-danger/70 py-4">Failed to load version history.</p>
  }

  if (data.commits.length === 0) {
    return <p className="text-sm text-text-faint py-4 italic">No version history available.</p>
  }

  return (
    <div className="space-y-1">
      <div className="text-xs text-text-faint mb-2">
        {data.total} commit{data.total !== 1 ? 's' : ''}
      </div>
      {data.commits.map((commit, idx) => {
        const isSelected = commit.hash === selectedHash
        const isLatest = idx === 0
        return (
          <button
            key={commit.hash}
            onClick={() => onSelectHash?.(commit.hash)}
            className={`w-full text-left px-3 py-2 rounded border transition-colors ${
              isSelected
                ? 'border-accent/40 bg-accent/5 text-text'
                : 'border-transparent hover:border-border-bright hover:bg-surface-el text-text-muted hover:text-text'
            }`}
          >
            <div className="flex items-start gap-2">
              <GitCommit size={13} className={`mt-0.5 shrink-0 ${isSelected ? 'text-accent' : 'text-text-faint'}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <code className="text-xs font-mono text-text-muted">
                    {abbreviateHash(commit.hash)}
                  </code>
                  {isLatest && (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-accent/10 text-accent border border-accent/20">
                      latest
                    </span>
                  )}
                </div>
                <p className="text-xs mt-0.5 truncate">{commit.message || '(no message)'}</p>
                <p className="text-xs text-text-faint mt-0.5">
                  {commit.author} · {formatDateTime(commit.timestamp)}
                </p>
              </div>
            </div>
          </button>
        )
      })}
    </div>
  )
}
