import { useCallback, useRef, useState } from 'react'
import { Search, Loader2 } from 'lucide-react'
import { useSearch } from '@/hooks/use-catalogue'
import { PrimitiveCard } from '@/components/catalogue/PrimitiveCard'

interface CatalogueSearchProps {
  initialQuery?: string
}

export function CatalogueSearch({ initialQuery = '' }: CatalogueSearchProps) {
  const [query, setQuery] = useState(initialQuery)
  const [debouncedQuery, setDebouncedQuery] = useState(initialQuery)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { data, isLoading, isFetching } = useSearch(debouncedQuery)

  const handleChange = useCallback((val: string) => {
    setQuery(val)
    if (timerRef.current !== null) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setDebouncedQuery(val), 300)
  }, [])

  return (
    <div className="p-4 space-y-4 max-w-4xl">
      <h1 className="text-base font-semibold text-text">Search Catalogue</h1>

      <div className="relative max-w-md">
        <Search
          size={13}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-text-faint pointer-events-none"
        />
        {isFetching && (
          <Loader2
            size={13}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-text-faint animate-spin"
          />
        )}
        <input
          autoFocus
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          placeholder="Search techniques, materials, tools…"
          className="w-full h-9 pl-8 pr-10 rounded border bg-surface-el text-text text-sm border-border-bright placeholder:text-text-faint focus:outline-none focus:border-accent/40 transition-colors"
        />
      </div>

      {debouncedQuery.trim() && isLoading && (
        <div className="flex items-center gap-2 text-sm text-text-muted py-4">
          <Loader2 size={14} className="animate-spin" />
          Searching…
        </div>
      )}

      {data && debouncedQuery.trim() && (
        <>
          <p className="text-xs text-text-faint">
            {data.total} result{data.total !== 1 ? 's' : ''} for "{debouncedQuery}"
          </p>
          {data.items.length === 0 ? (
            <p className="text-sm text-text-faint italic py-4">No results found.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {data.items.map((p) => (
                <PrimitiveCard key={p.id} primitive={p} />
              ))}
            </div>
          )}
        </>
      )}

      {!debouncedQuery.trim() && (
        <p className="text-sm text-text-faint py-4">Type to search across all primitives.</p>
      )}
    </div>
  )
}
