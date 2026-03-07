/**
 * ModuleErrorBoundary — wraps untrusted module components.
 *
 * A crash in a module's keyword renderer or panel must not take down the
 * entire page. This class component catches errors from its children and
 * renders a diagnostic card instead.
 *
 * Core widgets (TIMER_, MEASUREMENT_, etc.) are trusted and do NOT need
 * to be wrapped — only module-sourced renderers use this boundary.
 */
import React from 'react'
import { AlertTriangle, ChevronDown, ChevronRight, RefreshCw } from 'lucide-react'

interface Props {
  /** The module that owns this component (shown in the error card). */
  moduleName: string
  /** The component name being rendered (e.g. "ExampleWidget"). */
  componentName?: string
  /** The keyword being rendered, if applicable (e.g. "STOCK_LEVEL_"). */
  keyword?: string
  children: React.ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
  showStack: boolean
}

export class ModuleErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null, showStack: false }
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Log full details to the console for debugging
    console.error(
      `[Makestack] Module component crashed\n` +
      `  Module:    ${this.props.moduleName}\n` +
      `  Component: ${this.props.componentName ?? '(unknown)'}\n` +
      `  Keyword:   ${this.props.keyword ?? '(none)'}\n` +
      `  Error:     ${error.message}\n`,
      error,
      info,
    )
  }

  retry = () => {
    this.setState({ hasError: false, error: null, showStack: false })
  }

  toggleStack = () => {
    this.setState((s) => ({ showStack: !s.showStack }))
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children
    }

    const { moduleName, componentName, keyword } = this.props
    const { error, showStack } = this.state

    return (
      <div
        role="alert"
        className="my-1 rounded border border-error/40 bg-error/5 p-3 text-xs font-mono"
      >
        <div className="flex items-start gap-2">
          <AlertTriangle size={14} className="text-error shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <div className="font-semibold text-error">
              Module component crashed: <span className="text-text">{moduleName}</span>
            </div>
            {(componentName || keyword) && (
              <div className="text-text-faint mt-0.5">
                {componentName && <span>Component: {componentName}</span>}
                {componentName && keyword && <span className="mx-1">·</span>}
                {keyword && <span>Keyword: {keyword}</span>}
              </div>
            )}
            <div className="mt-1 text-error/80">
              {error?.message ?? 'Unknown error'}
            </div>

            {/* Collapsible stack trace */}
            {error?.stack && (
              <div className="mt-2">
                <button
                  onClick={this.toggleStack}
                  className="flex items-center gap-1 text-text-faint hover:text-text transition-colors"
                >
                  {showStack ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                  Stack trace
                </button>
                {showStack && (
                  <pre className="mt-1 overflow-x-auto rounded bg-bg p-2 text-text-faint whitespace-pre-wrap break-all">
                    {error.stack}
                  </pre>
                )}
              </div>
            )}

            {/* Actions */}
            <div className="mt-2 flex items-center gap-3">
              <button
                onClick={this.retry}
                className="flex items-center gap-1 text-text-faint hover:text-text transition-colors"
              >
                <RefreshCw size={11} />
                Retry
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }
}
