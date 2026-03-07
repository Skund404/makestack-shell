/**
 * Dev: Schema Inspector
 *
 * Shows all UserDB tables (Shell + module), row counts, and a read-only SQL query runner.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Database, Play, AlertCircle } from 'lucide-react'
import { apiGet } from '@/lib/api'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Textarea } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'

interface TablesData {
  tables: Record<string, number>
}

interface QueryResult {
  rows: Record<string, unknown>[]
  count: number
}

function classifyTable(name: string): 'shell' | 'module' | 'internal' {
  if (name.startsWith('_')) return 'internal'
  const shellTables = [
    'users', 'user_preferences', 'workshops', 'workshop_members',
    'inventory', 'installed_modules', 'module_migrations',
  ]
  if (shellTables.includes(name)) return 'shell'
  return 'module'
}

export function DevSchema() {
  const [sql, setSql] = useState('SELECT * FROM installed_modules LIMIT 20')
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null)
  const [queryError, setQueryError] = useState<string | null>(null)
  const [isQuerying, setIsQuerying] = useState(false)

  const { data, isLoading } = useQuery<TablesData>({
    queryKey: ['dev', 'schema'],
    queryFn: () => apiGet<TablesData>('/api/dev/userdb/tables'),
  })

  async function runQuery() {
    setIsQuerying(true)
    setQueryError(null)
    setQueryResult(null)
    try {
      const result = await apiGet<QueryResult>('/api/dev/userdb/query', { sql })
      setQueryResult(result)
    } catch (err) {
      setQueryError(String(err))
    } finally {
      setIsQuerying(false)
    }
  }

  const tables = data?.tables ?? {}
  const shellTables = Object.entries(tables).filter(([n]) => classifyTable(n) === 'shell')
  const moduleTables = Object.entries(tables).filter(([n]) => classifyTable(n) === 'module')
  const internalTables = Object.entries(tables).filter(([n]) => classifyTable(n) === 'internal')

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div className="flex items-center gap-2 mb-4">
        <Database size={18} className="text-accent" />
        <h1 className="text-lg font-semibold text-text">Schema Inspector</h1>
      </div>

      {isLoading ? (
        <p className="text-sm text-text-muted">Loading…</p>
      ) : (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-text">Shell Tables</span>
                <Badge>{shellTables.length}</Badge>
              </div>
            </CardHeader>
            <CardBody className="p-0">
              <TableList entries={shellTables} />
            </CardBody>
          </Card>

          {moduleTables.length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-text">Module Tables</span>
                  <Badge variant="success">{moduleTables.length}</Badge>
                </div>
              </CardHeader>
              <CardBody className="p-0">
                <TableList entries={moduleTables} />
              </CardBody>
            </Card>
          )}

          {internalTables.length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-text-muted">Internal Tables</span>
                  <Badge variant="muted">{internalTables.length}</Badge>
                </div>
              </CardHeader>
              <CardBody className="p-0">
                <TableList entries={internalTables} />
              </CardBody>
            </Card>
          )}
        </div>
      )}

      <Card>
        <CardHeader>
          <span className="text-sm font-medium text-text">Read-only Query Runner</span>
        </CardHeader>
        <CardBody className="space-y-3">
          <Textarea
            value={sql}
            onChange={(e) => setSql(e.target.value)}
            rows={3}
            className="font-mono text-xs"
            placeholder="SELECT * FROM inventory LIMIT 10"
          />
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={runQuery}
              disabled={isQuerying || !sql.trim()}
              className="flex items-center gap-1.5"
            >
              <Play size={12} />
              {isQuerying ? 'Running…' : 'Run'}
            </Button>
            {queryResult && (
              <span className="text-xs text-text-muted">{queryResult.count} rows</span>
            )}
          </div>

          {queryError && (
            <p className="text-xs text-danger flex items-center gap-1">
              <AlertCircle size={12} />
              {queryError}
            </p>
          )}

          {queryResult && queryResult.rows.length > 0 && (
            <QueryResultTable rows={queryResult.rows} />
          )}

          {queryResult && queryResult.rows.length === 0 && (
            <p className="text-xs text-text-faint">Query returned 0 rows.</p>
          )}
        </CardBody>
      </Card>
    </div>
  )
}

function TableList({ entries }: { entries: [string, number][] }) {
  if (entries.length === 0) {
    return <p className="px-4 py-2 text-xs text-text-faint">None</p>
  }
  return (
    <div className="divide-y divide-border">
      {entries.map(([name, count]) => (
        <div key={name} className="flex items-center justify-between px-4 py-2">
          <code className="text-xs font-mono text-text">{name}</code>
          <span className="text-xs text-text-muted">{count} rows</span>
        </div>
      ))}
    </div>
  )
}

function QueryResultTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (rows.length === 0) return null
  const cols = Object.keys(rows[0])

  return (
    <div className="overflow-x-auto border border-border rounded text-xs">
      <table className="w-full font-mono">
        <thead className="bg-surface-el">
          <tr>
            {cols.map((c) => (
              <th key={c} className="px-3 py-1.5 text-left text-text-muted font-medium">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-surface-el/50">
              {cols.map((c) => (
                <td key={c} className="px-3 py-1.5 text-text max-w-48 truncate">
                  {row[c] === null ? <span className="text-text-faint">null</span> : String(row[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
