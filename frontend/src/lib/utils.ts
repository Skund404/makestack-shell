import { clsx, type ClassValue } from 'clsx'

export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs)
}

export function formatDate(iso: string): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function formatDateTime(iso: string): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function truncate(str: string, maxLen = 120): string {
  if (str.length <= maxLen) return str
  return str.slice(0, maxLen).trimEnd() + '…'
}

export function primitiveTypeColor(type: string): string {
  switch (type) {
    case 'tool':      return 'text-orange-400'
    case 'material':  return 'text-emerald-400'
    case 'technique': return 'text-sky-400'
    case 'workflow':  return 'text-violet-400'
    case 'project':   return 'text-amber-400'
    case 'event':     return 'text-rose-400'
    default:          return 'text-text-muted'
  }
}

export function primitiveTypeBg(type: string): string {
  switch (type) {
    case 'tool':      return 'bg-orange-400/10 text-orange-400 border-orange-400/20'
    case 'material':  return 'bg-emerald-400/10 text-emerald-400 border-emerald-400/20'
    case 'technique': return 'bg-sky-400/10 text-sky-400 border-sky-400/20'
    case 'workflow':  return 'bg-violet-400/10 text-violet-400 border-violet-400/20'
    case 'project':   return 'bg-amber-400/10 text-amber-400 border-amber-400/20'
    case 'event':     return 'bg-rose-400/10 text-rose-400 border-rose-400/20'
    default:          return 'bg-surface text-text-muted border-border'
  }
}

export function abbreviateHash(hash: string, len = 7): string {
  return hash.slice(0, len)
}
