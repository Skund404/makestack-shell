/**
 * Types for Phase 9 — terminal exec and SSE log stream.
 *
 * Entry types returned by POST /api/terminal/exec:
 *   command  — the raw input the user typed
 *   request  — the translated HTTP call (method, path, body)
 *   response — the HTTP response (status, elapsed_ms, body)
 *   error    — exec failure or unknown command
 *
 * Entry types from GET /api/terminal/stream (SSE):
 *   log       — structlog backend event
 *   heartbeat — SSE keepalive, silently dropped on the client
 */

export type EntryType =
  | 'command'
  | 'request'
  | 'response'
  | 'error'
  | 'log'
  | 'heartbeat'

export interface TerminalEntry {
  type: EntryType
  timestamp: string
  /** command: what the user typed; request: "METHOD /path"; response: "HTTP 200"; error: message; log: structlog event */
  event: string
  component?: string
  // request + response fields
  method?: string
  path?: string
  body?: string
  // response fields
  status_code?: number
  elapsed_ms?: number
  level?: string
  // error fields
  suggestion?: string
}

export type TerminalSyntax = 'auto' | 'cli' | 'rest'

export interface ExecRequest {
  input: string
  syntax: TerminalSyntax
}

export interface ExecResponse {
  entries: TerminalEntry[]
}

/** Shape of a single CLI autocomplete entry from GET /api/terminal/docs. */
export interface CliCommandHint {
  keyword: string
  description: string
  accepts_arg: boolean
}

// ---------------------------------------------------------------------------
// Back-compat alias — LogEntry used in LogPanel / LogStream (SSE entries)
// ---------------------------------------------------------------------------
/** @deprecated Use TerminalEntry. Kept for LogPanel/LogStream imports. */
export type LogEntry = TerminalEntry
