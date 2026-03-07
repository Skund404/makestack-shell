import { CheckCircle, GitCommit, RefreshCw } from 'lucide-react'
import { abbreviateHash } from '@/lib/utils'
import { Tooltip } from '@/components/ui/Tooltip'

interface VersionBadgeProps {
  currentHash?: string
  inventoryHash?: string
  className?: string
}

export function VersionBadge({ currentHash, inventoryHash, className }: VersionBadgeProps) {
  if (!currentHash && !inventoryHash) return null

  if (!inventoryHash) {
    return (
      <Tooltip content="Current version">
        <span className={`inline-flex items-center gap-1 text-xs text-text-faint font-mono ${className ?? ''}`}>
          <GitCommit size={10} />
          {abbreviateHash(currentHash ?? '')}
        </span>
      </Tooltip>
    )
  }

  const isStale = currentHash && inventoryHash !== currentHash

  if (isStale) {
    return (
      <Tooltip content={`Update available — pinned to ${abbreviateHash(inventoryHash)}, latest is ${abbreviateHash(currentHash ?? '')}`}>
        <span className={`inline-flex items-center gap-1 text-xs text-warning font-mono ${className ?? ''}`}>
          <RefreshCw size={10} />
          update available
        </span>
      </Tooltip>
    )
  }

  return (
    <Tooltip content={`Up to date — ${abbreviateHash(inventoryHash)}`}>
      <span className={`inline-flex items-center gap-1 text-xs text-success font-mono ${className ?? ''}`}>
        <CheckCircle size={10} />
        up to date
      </span>
    </Tooltip>
  )
}
