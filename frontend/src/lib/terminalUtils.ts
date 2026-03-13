/**
 * Terminal utilities — frontend only.
 *
 * isRestSyntax() is the ONLY function here.
 * The CLI translation table lives in terminal.py (backend) — never here.
 * Autocomplete hints come from useDocsIndex (9D/9E) — never a static table here.
 */

const REST_RE = /^(GET|POST|PUT|DELETE|PATCH)\s+\//i

/**
 * Returns true if the input looks like a REST command (e.g. "GET /api/status").
 * Used for the UI hint label only — the backend resolves all translation.
 */
export function isRestSyntax(input: string): boolean {
  return REST_RE.test(input.trim())
}
