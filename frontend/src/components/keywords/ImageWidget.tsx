import type { KeywordContext } from '@/modules/keyword-resolver'

interface ImageValue {
  src: string
  alt?: string
  caption?: string
}

interface ImageWidgetProps {
  keyword: string
  value: unknown
  context: KeywordContext
}

export function ImageWidget({ value, context: _context }: ImageWidgetProps) {
  const src = typeof value === 'string' ? value : (value as ImageValue)?.src ?? ''
  const alt = typeof value === 'object' && value !== null ? (value as ImageValue).alt ?? '' : ''
  const caption = typeof value === 'object' && value !== null ? (value as ImageValue).caption : undefined

  if (!src) return null

  return (
    <figure className="my-2 max-w-lg">
      <img
        src={src}
        alt={alt}
        className="rounded border border-border-bright max-w-full h-auto"
        loading="lazy"
      />
      {caption && (
        <figcaption className="mt-1.5 text-xs text-text-muted text-center">{caption}</figcaption>
      )}
    </figure>
  )
}
