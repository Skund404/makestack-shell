/**
 * Dev: Keyword Playground
 *
 * Paste JSON containing keywords and preview how each renders.
 * Shows the resolution chain (which layer the renderer came from).
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Terminal, AlertCircle } from 'lucide-react'
import { apiGet } from '@/lib/api'
import { resolveKeyword } from '@/modules/keyword-resolver'
import { KeywordValue } from '@/components/keywords/KeywordValue'
import { isKeyword } from '@/lib/keyword-detect'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Textarea } from '@/components/ui/Input'

interface DevKeyword {
  keyword: string
  source: 'core' | 'module' | 'pack'
  module: string | null
}

interface KeywordsData {
  keywords: DevKeyword[]
  total: number
  core_count: number
  module_count: number
}

const DEFAULT_JSON = `{
  "TIMER_": "15min",
  "MEASUREMENT_": "4mm",
  "NOTE_": "info:Remember to pre-punch all holes before stitching",
  "CHECKLIST_": "Prepare workspace|Gather materials|Check tools",
  "UNKNOWN_WIDGET_": "some value"
}`

export function DevKeywords() {
  const [json, setJson] = useState(DEFAULT_JSON)
  const [parseError, setParseError] = useState<string | null>(null)
  const [parsed, setParsed] = useState<Record<string, unknown>>(() => {
    try {
      return JSON.parse(DEFAULT_JSON) as Record<string, unknown>
    } catch {
      return {}
    }
  })

  const { data } = useQuery<KeywordsData>({
    queryKey: ['dev', 'keywords'],
    queryFn: () => apiGet<KeywordsData>('/api/dev/keywords'),
  })

  function handleJsonChange(value: string) {
    setJson(value)
    try {
      const obj = JSON.parse(value) as Record<string, unknown>
      setParsed(obj)
      setParseError(null)
    } catch (err) {
      setParseError(String(err))
      setParsed({})
    }
  }

  const keywords = Object.entries(parsed).filter(([k]) => isKeyword(k))
  const nonKeywords = Object.entries(parsed).filter(([k]) => !isKeyword(k))

  function getSource(keyword: string): { label: string; variant: 'default' | 'success' | 'warning' } {
    const renderer = resolveKeyword(keyword)
    if (!renderer) return { label: 'raw text (no renderer)', variant: 'warning' }
    const reg = data?.keywords.find((kw) => kw.keyword === keyword)
    if (!reg) return { label: 'core', variant: 'default' }
    if (reg.source === 'module') return { label: `module: ${reg.module}`, variant: 'success' }
    if (reg.source === 'pack') return { label: 'widget pack', variant: 'default' }
    return { label: 'core', variant: 'default' }
  }

  const ctx = { primitiveType: 'tool', primitivePath: 'tools/preview/manifest.json' }

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div className="flex items-center gap-2 mb-4">
        <Terminal size={18} className="text-accent" />
        <h1 className="text-lg font-semibold text-text">Keyword Playground</h1>
      </div>

      {/* Registry summary */}
      {data && (
        <div className="flex gap-3 text-xs text-text-muted">
          <span>{data.total} keywords registered:</span>
          <span className="text-text">{data.core_count} core</span>
          <span className="text-text">{data.module_count} module</span>
        </div>
      )}

      {/* Registry table */}
      {data && (
        <Card>
          <CardHeader>
            <span className="text-sm font-medium text-text">Registered Renderers</span>
          </CardHeader>
          <CardBody className="p-0">
            <div className="divide-y divide-border">
              {data.keywords.map((kw) => (
                <div key={kw.keyword} className="flex items-center justify-between px-4 py-2">
                  <code className="text-xs font-mono text-accent">{kw.keyword}</code>
                  <Badge variant={kw.source === 'module' ? 'success' : 'default'}>
                    {kw.source === 'module' ? `module: ${kw.module}` : kw.source}
                  </Badge>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      )}

      {/* JSON input */}
      <Card>
        <CardHeader>
          <span className="text-sm font-medium text-text">Paste JSON to Preview</span>
        </CardHeader>
        <CardBody>
          <Textarea
            value={json}
            onChange={(e) => handleJsonChange(e.target.value)}
            rows={8}
            className="font-mono text-xs"
            placeholder='{"TIMER_": "5min", "NOTE_": "info:Check temperature"}'
          />
          {parseError && (
            <p className="mt-2 text-xs text-danger flex items-center gap-1">
              <AlertCircle size={12} />
              {parseError}
            </p>
          )}
        </CardBody>
      </Card>

      {/* Preview */}
      {keywords.length > 0 && (
        <Card>
          <CardHeader>
            <span className="text-sm font-medium text-text">Preview</span>
          </CardHeader>
          <CardBody className="space-y-4">
            {keywords.map(([keyword, value]) => {
              const source = getSource(keyword)
              return (
                <div key={keyword} className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <code className="text-xs font-mono text-accent">{keyword}</code>
                    <Badge variant={source.variant}>{source.label}</Badge>
                  </div>
                  <div className="pl-2 border-l-2 border-border">
                    <KeywordValue keyword={keyword} value={value} context={ctx} />
                  </div>
                </div>
              )
            })}
          </CardBody>
        </Card>
      )}

      {/* Non-keyword entries */}
      {nonKeywords.length > 0 && (
        <Card>
          <CardHeader>
            <span className="text-sm font-medium text-text-muted">Non-keyword entries (rendered as-is)</span>
          </CardHeader>
          <CardBody className="space-y-1">
            {nonKeywords.map(([k, v]) => (
              <div key={k} className="flex gap-3 text-xs font-mono">
                <span className="text-text-muted">{k}:</span>
                <span className="text-text">{JSON.stringify(v)}</span>
              </div>
            ))}
          </CardBody>
        </Card>
      )}

      {keywords.length === 0 && nonKeywords.length === 0 && !parseError && (
        <p className="text-sm text-text-faint">No keys found in JSON. Paste an object above.</p>
      )}
    </div>
  )
}
