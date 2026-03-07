import { Loader2, AlertCircle } from 'lucide-react'
import { useNavigate } from '@tanstack/react-router'
import { usePrimitive, useUpdatePrimitive } from '@/hooks/use-catalogue'
import { PrimitiveForm } from '@/components/catalogue/PrimitiveForm'
import type { PrimitiveUpdate } from '@/lib/types'

interface CatalogueEditProps {
  path: string
}

export function CatalogueEdit({ path }: CatalogueEditProps) {
  const navigate = useNavigate()
  const { data, isLoading, isError } = usePrimitive(path)
  const { mutate, isPending, error } = useUpdatePrimitive()

  if (!path) {
    return <div className="p-4 text-sm text-text-faint">No path specified.</div>
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20 text-text-muted gap-2">
        <Loader2 size={16} className="animate-spin" /> Loading…
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="flex items-center justify-center py-20 gap-2 text-danger/70">
        <AlertCircle size={16} />
        <p className="text-sm">Primitive not found.</p>
      </div>
    )
  }

  return (
    <div className="p-4 max-w-2xl">
      <div className="mb-4">
        <h1 className="text-base font-semibold text-text">Edit Primitive</h1>
        <p className="text-xs text-text-faint font-mono mt-0.5">{path}</p>
      </div>

      {error && (
        <div className="mb-4 px-3 py-2 rounded border border-danger/25 bg-danger/5 text-sm text-danger">
          {error.message}
        </div>
      )}

      <PrimitiveForm
        mode="edit"
        initial={data}
        isSubmitting={isPending}
        onSubmit={(formData) => {
          mutate(
            { path, data: formData as PrimitiveUpdate },
            { onSuccess: () => void navigate({ to: '/catalogue/detail', search: { path, at: undefined } }) },
          )
        }}
      />
    </div>
  )
}
