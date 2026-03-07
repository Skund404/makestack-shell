import {
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
} from '@tanstack/react-router'
import { Layout } from '@/components/layout/Layout'
import { CatalogueIndex } from '@/routes/catalogue/index'
import { CatalogueSearch } from '@/routes/catalogue/search'
import { CatalogueCreate } from '@/routes/catalogue/create'
import { CatalogueDetail } from '@/routes/catalogue/detail'
import { CatalogueEdit } from '@/routes/catalogue/edit'
import { InventoryIndex } from '@/routes/inventory/index'
import { InventoryDetail } from '@/routes/inventory/detail'
import { WorkshopsIndex } from '@/routes/workshops/index'
import { WorkshopsDetail } from '@/routes/workshops/detail'
import { SettingsIndex } from '@/routes/settings/index'
import { DevKeywords } from '@/routes/dev/keywords'
import { DevSchema } from '@/routes/dev/schema'
import { DevModules } from '@/routes/dev/modules'

// ---------------------------------------------------------------------------
// Root
// ---------------------------------------------------------------------------

const rootRoute = createRootRoute({ component: Layout })

// ---------------------------------------------------------------------------
// Index — redirect to /catalogue
// ---------------------------------------------------------------------------

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: () => { throw redirect({ to: '/catalogue', search: { type: undefined } }) },
})

// ---------------------------------------------------------------------------
// Catalogue routes
// ---------------------------------------------------------------------------

const catalogueRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/catalogue',
  validateSearch: (search: Record<string, unknown>) => ({
    type: typeof search.type === 'string' ? search.type : undefined,
  }),
  component: function CatalogueIndexPage() {
    const { type } = catalogueRoute.useSearch()
    return <CatalogueIndex initialType={type ?? ''} />
  },
})

const catalogueSearchRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/catalogue/search',
  validateSearch: (search: Record<string, unknown>) => ({
    q: typeof search.q === 'string' ? search.q : '',
  }),
  component: function CatalogueSearchPage() {
    const { q } = catalogueSearchRoute.useSearch()
    return <CatalogueSearch initialQuery={q} />
  },
})

const catalogueCreateRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/catalogue/create',
  validateSearch: (search: Record<string, unknown>) => ({
    type: typeof search.type === 'string' ? search.type : undefined,
  }),
  component: CatalogueCreate,
})

const catalogueDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/catalogue/detail',
  validateSearch: (search: Record<string, unknown>) => ({
    path: typeof search.path === 'string' ? search.path : '',
    at: typeof search.at === 'string' ? search.at : undefined,
  }),
  component: function CatalogueDetailPage() {
    const { path, at } = catalogueDetailRoute.useSearch()
    return <CatalogueDetail path={path} at={at} />
  },
})

const catalogueEditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/catalogue/edit',
  validateSearch: (search: Record<string, unknown>) => ({
    path: typeof search.path === 'string' ? search.path : '',
  }),
  component: function CatalogueEditPage() {
    const { path } = catalogueEditRoute.useSearch()
    return <CatalogueEdit path={path} />
  },
})

// ---------------------------------------------------------------------------
// Inventory routes
// ---------------------------------------------------------------------------

const inventoryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/inventory',
  validateSearch: () => ({} as Record<never, never>),
  component: InventoryIndex,
})

const inventoryDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/inventory/detail',
  validateSearch: (search: Record<string, unknown>) => ({
    id: typeof search.id === 'string' ? search.id : '',
  }),
  component: function InventoryDetailPage() {
    const { id } = inventoryDetailRoute.useSearch()
    return <InventoryDetail id={id} />
  },
})

// ---------------------------------------------------------------------------
// Workshop routes
// ---------------------------------------------------------------------------

const workshopsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/workshops',
  validateSearch: () => ({} as Record<never, never>),
  component: WorkshopsIndex,
})

const workshopsDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/workshops/detail',
  validateSearch: (search: Record<string, unknown>) => ({
    id: typeof search.id === 'string' ? search.id : '',
  }),
  component: function WorkshopsDetailPage() {
    const { id } = workshopsDetailRoute.useSearch()
    return <WorkshopsDetail id={id} />
  },
})

// ---------------------------------------------------------------------------
// Settings route
// ---------------------------------------------------------------------------

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings',
  validateSearch: () => ({} as Record<never, never>),
  component: SettingsIndex,
})

// ---------------------------------------------------------------------------
// Dev routes (only visible/functional in dev mode)
// ---------------------------------------------------------------------------

const devKeywordsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/dev/keywords',
  validateSearch: () => ({} as Record<never, never>),
  component: DevKeywords,
})

const devSchemaRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/dev/schema',
  validateSearch: () => ({} as Record<never, never>),
  component: DevSchema,
})

const devModulesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/dev/modules',
  validateSearch: () => ({} as Record<never, never>),
  component: DevModules,
})

// ---------------------------------------------------------------------------
// Route tree + router
// ---------------------------------------------------------------------------

const routeTree = rootRoute.addChildren([
  indexRoute,
  catalogueRoute,
  catalogueSearchRoute,
  catalogueCreateRoute,
  catalogueDetailRoute,
  catalogueEditRoute,
  inventoryRoute,
  inventoryDetailRoute,
  workshopsRoute,
  workshopsDetailRoute,
  settingsRoute,
  devKeywordsRoute,
  devSchemaRoute,
  devModulesRoute,
])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
