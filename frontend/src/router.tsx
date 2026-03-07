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
// Route tree + router
// ---------------------------------------------------------------------------

const routeTree = rootRoute.addChildren([
  indexRoute,
  catalogueRoute,
  catalogueSearchRoute,
  catalogueCreateRoute,
  catalogueDetailRoute,
  catalogueEditRoute,
])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
