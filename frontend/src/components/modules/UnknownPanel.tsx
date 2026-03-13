import { AlertCircle } from 'lucide-react'

/** Fallback rendered when a panelId cannot be resolved in the PanelRegistry. Never throws. */
export function UnknownPanel({ panelId }: { panelId: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 h-full min-h-[100px] rounded border border-dashed border-border text-text-faint p-4">
      <AlertCircle size={14} className="shrink-0 opacity-50" />
      <p className="text-xs text-center">
        Unknown panel: <span className="font-mono">{panelId}</span>
      </p>
    </div>
  )
}
