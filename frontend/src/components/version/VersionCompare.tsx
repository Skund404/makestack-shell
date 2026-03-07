import { useState } from 'react'
import { usePrimitiveHistory } from '@/hooks/use-version'
import { abbreviateHash } from '@/lib/utils'
import { Select } from '@/components/ui/Select'
import { DiffViewer } from './DiffViewer'

interface VersionCompareProps {
  path: string
}

export function VersionCompare({ path }: VersionCompareProps) {
  const { data } = usePrimitiveHistory(path, 50)

  const [fromHash, setFromHash] = useState<string>('')
  const [toHash, setToHash] = useState<string>('')

  const commits = data?.commits ?? []

  const options = commits.map((c) => ({
    value: c.hash,
    label: `${abbreviateHash(c.hash)} — ${c.message || '(no message)'}`.slice(0, 60),
  }))

  const effectiveFrom = fromHash || commits[1]?.hash || ''
  const effectiveTo   = toHash   || commits[0]?.hash || ''

  if (commits.length < 2) {
    return <p className="text-sm text-text-faint italic py-2">Need at least 2 commits to compare.</p>
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <Select
          label="From"
          value={effectiveFrom}
          onValueChange={setFromHash}
          options={options}
          className="w-64"
        />
        <span className="text-text-faint mt-5">→</span>
        <Select
          label="To"
          value={effectiveTo}
          onValueChange={setToHash}
          options={options}
          className="w-64"
        />
      </div>
      {effectiveFrom && effectiveTo && effectiveFrom !== effectiveTo && (
        <DiffViewer path={path} fromHash={effectiveFrom} toHash={effectiveTo} />
      )}
    </div>
  )
}
