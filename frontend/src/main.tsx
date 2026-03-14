import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.tsx'
import { loadTheme } from './theme/loader.ts'
import { registerCoreWidgets } from './components/keywords/index.ts'
import { registerAllModulePanels } from './modules/registry.ts'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
})

// Init — load theme and register widgets/panels before first render
void loadTheme()
registerCoreWidgets()
registerAllModulePanels()

// Global error handler — catches unhandled JS errors.
// In dev mode: reports to POST /api/dev/error for server-side logging.
// In production: logs to console only.
window.addEventListener('error', (event) => {
  const isDev = import.meta.env.DEV
  if (isDev) {
    void fetch('/api/dev/error', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: event.message,
        stack: event.error?.stack ?? null,
        component: null,
        url: window.location.href,
      }),
    }).catch(() => {
      // Silently ignore fetch errors in the error handler itself
    })
  }
  console.error('[Makestack] Unhandled error:', event.error)
})

window.addEventListener('unhandledrejection', (event) => {
  console.error('[Makestack] Unhandled promise rejection:', event.reason)
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
