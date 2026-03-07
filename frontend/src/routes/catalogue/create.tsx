import { useNavigate } from '@tanstack/react-router'
import { useCreatePrimitive } from '@/hooks/use-catalogue'
import { PrimitiveForm } from '@/components/catalogue/PrimitiveForm'

export function CatalogueCreate() {
  const navigate = useNavigate()
  const { mutate, isPending, error } = useCreatePrimitive()

  return (
    <div className="p-4 max-w-2xl">
      <h1 className="text-base font-semibold text-text mb-4">New Primitive</h1>

      {error && (
        <div className="mb-4 px-3 py-2 rounded border border-danger/25 bg-danger/5 text-sm text-danger">
          {error.message}
        </div>
      )}

      <PrimitiveForm
        mode="create"
        isSubmitting={isPending}
        onSubmit={(data) => {
          mutate(data as Parameters<typeof mutate>[0], {
            onSuccess: (result) => {
              void navigate({ to: '/catalogue/detail', search: { path: result.path, at: undefined } })
            },
          })
        }}
      />
    </div>
  )
}
