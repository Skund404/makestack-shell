import { useNavigate } from '@tanstack/react-router'
import { primitiveTypeBg, truncate } from '@/lib/utils'
import { Badge } from '@/components/ui/Badge'
import { Card, CardBody } from '@/components/ui/Card'
import type { Primitive } from '@/lib/types'

interface PrimitiveCardProps {
  primitive: Primitive
}

export function PrimitiveCard({ primitive }: PrimitiveCardProps) {
  const navigate = useNavigate()

  return (
    <Card
      hoverable
      onClick={() => void navigate({ to: '/catalogue/detail', search: { path: primitive.path, at: undefined } })}
    >
      <CardBody className="space-y-2">
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-sm font-semibold text-text leading-tight">{primitive.name}</h3>
          <span className={`text-xs px-1.5 py-0.5 rounded border shrink-0 ${primitiveTypeBg(primitive.type)}`}>
            {primitive.type}
          </span>
        </div>
        {primitive.description && (
          <p className="text-xs text-text-muted leading-relaxed">
            {truncate(primitive.description, 100)}
          </p>
        )}
        {primitive.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {primitive.tags.slice(0, 5).map((tag) => (
              <Badge key={String(tag)} variant="muted">{String(tag)}</Badge>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  )
}
