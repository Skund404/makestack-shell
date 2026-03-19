# CLAUDE.md — Makestack App (Shell)

> This file is read by Claude Code at the start of every session.
> It contains project context, current state, and coding instructions.
> Update this file at the end of each session.

---

## Instructions

1. Read this ENTIRE file before doing any work.
2. Check "Current State" and "What's In Progress" before starting.
3. Ask the user what to work on — don't assume.
4. At the END of each session, suggest updates to this file.
5. Never contradict the spec documents without discussing first.
6. If something isn't covered by the specs, ask — don't guess.
7. Write clear, well-commented code. The user relies heavily on AI for development.

---

## Project Overview

Makestack is a modular project management and ERP toolkit for makers (leatherworkers, cosplayers, woodworkers, 3D printers, cooks, etc.).

**This repo (makestack-shell)** is the Shell — the host application that sits between the user and everything else. It:
- Proxies all access to makestack-core (the catalogue engine)
- Owns the UserDB (SQLite — personal state: inventory, workshops, preferences, module data)
- Hosts modules (Python backend + React frontend)
- Provides the themed UI, keyword renderer registry, navigation, and dev tooling
- Manages authentication (the single security boundary)
- Exposes an MCP server so AI agents can fully operate the system

It is intentionally boring infrastructure with no domain opinion. Every domain feature (inventory, costing, suppliers) lives in a module. The Shell just makes sure modules have what they need to run.

**Two clients, one API:** The Shell has exactly two consumers — the React frontend (for humans) and the MCP server (for AI agents). Both hit the same FastAPI backend. There is no separate "AI API" — the REST API is designed to be complete enough that either client can do everything.

**Companion repo:** makestack-core (Go 1.24, single binary) — the headless catalogue engine. Manages JSON files in Git, maintains a SQLite read index, serves data via REST API. Core is already feature-complete for v0. Binary name: `makestack-core`. Default port: 8420.

---

## Architecture

```
makestack-core  (Go, port 8420)
    Impersonal, canonical knowledge
    Git-backed, headless
         │
         │ REST API (Shell is the only client)
         │
makestack-shell  (Python/FastAPI, port 3000)
    ├── FastAPI backend
    │     Catalogue proxy ─── Core API
    │     UserDB (SQLite)     Inventory, workshops, settings, users
    │     Module system       Routes, migrations, SDK
    │     Package manager     Git-native registry
    │     MCP action log      Audit trail for AI operations
    │     Terminal/log SSE    Live log streaming
    │     Backup system       Automated + manual UserDB backups
    │
    ├── React frontend        Human UI
    └── MCP server            AI agent interface (SSE + stdio)
```

**Rules:**
- The Shell is the only client of Core; modules never talk to Core directly
- The catalogue never knows about the user
- The inventory stores hash-pointer references, never copies catalogue data
- Uninstall every module → the Shell still works (catalogue browsing, search, edit, workshops)
- The Shell has no domain opinion
- Every Shell operation must be reachable via REST API — no operation requires the frontend
- The MCP server wraps the REST API — it doesn't bypass it or talk to UserDB directly

---

## Tech Stack

### Backend
- **Language:** Python 3.10+ (system has 3.10; pyproject.toml says >=3.10)
- **Framework:** FastAPI (async)
- **HTTP client:** httpx (async, for Core communication)
- **Database:** SQLite via aiosqlite (UserDB — local personal state)
- **Validation:** Pydantic 2.x
- **Logging:** structlog (tagged, structured, with SSE broadcast)
- **Testing:** pytest + pytest-asyncio (474 tests)
- **Module SDK:** `makestack_sdk` package (provided by this repo, consumed by modules)
- **MCP server:** `mcp` Python SDK (SSE + stdio transports)
- **CLI:** Click

### Frontend
- **Framework:** React 19 + TypeScript (strict mode)
- **Routing:** TanStack Router v1 (code-based routes in `router.tsx`)
- **Data fetching:** TanStack Query v5
- **Styling:** Tailwind CSS v4 (inline `@theme`, CSS vars `--ms-*`)
- **Components:** Radix UI primitives wrapped in `src/components/ui/`
- **Icons:** Lucide React
- **Build:** Vite 7
- **Primary font:** Lexend (dyslexia-friendly)
- **Mono font:** JetBrains Mono (measurements/data)

### Infra
- **Container:** Docker + docker-compose (Core + Shell together)
- **Production deployment:** Hetzner CX21 + Cloudflare Tunnel (see HETZNER.md)
- **CLI entry point:** `makestack = "cli.main:app"`

---

## Directory Layout (Repo)

```
makestack-shell/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, lifespan, startup sequence
│   │   ├── constants.py             # SHELL_VERSION = "0.1.0"
│   │   ├── core_client.py           # CatalogueClient with LRU cache
│   │   ├── userdb.py                # Async SQLite wrapper + migration runner
│   │   ├── models.py                # All Pydantic models (30+ types)
│   │   ├── dependencies.py          # FastAPI DI providers
│   │   ├── module_loader.py         # Module discovery, validation, mounting
│   │   ├── module_manifest.py       # ModuleManifest Pydantic schema
│   │   ├── package_manifest.py      # PackageManifest schema (makestack-package.json)
│   │   ├── registry_client.py       # Git-based registry resolver
│   │   ├── package_cache.py         # Local package cache manager
│   │   ├── log_broadcast.py         # SSE log fan-out broadcaster
│   │   ├── routers/                 # 14 FastAPI routers
│   │   │   ├── catalogue.py         # Core proxy
│   │   │   ├── inventory.py         # Hash-pointer inventory
│   │   │   ├── workshops.py         # Workshop CRUD + members + modules + nav
│   │   │   ├── settings.py          # Preferences + theme
│   │   │   ├── users.py             # User profile + stats
│   │   │   ├── version.py           # History + diff
│   │   │   ├── modules.py           # Module management
│   │   │   ├── packages.py          # Package install/uninstall + registries
│   │   │   ├── system.py            # Status + capabilities
│   │   │   ├── data.py              # Export/import
│   │   │   ├── backups.py           # UserDB backup management
│   │   │   ├── terminal.py          # Terminal + log stream (SSE + WebSocket)
│   │   │   ├── mcp_log.py           # MCP action audit log
│   │   │   └── dev.py               # Dev-only debugging
│   │   ├── migrations/              # 7 numbered SQL migrations
│   │   │   ├── 001_initial_schema.py
│   │   │   ├── 002_add_package_path.py
│   │   │   ├── 003_add_registry_tables.py
│   │   │   ├── 004_user_profile.py
│   │   │   ├── 005_mcp_action_log.py
│   │   │   ├── 006_workshop_modules.py
│   │   │   └── 007_install_transactions.py
│   │   └── installers/              # Package installer handlers
│   │       ├── base.py              # InstallResult dataclass
│   │       ├── module_installer.py
│   │       ├── widget_installer.py
│   │       ├── catalogue_installer.py
│   │       ├── data_installer.py
│   │       └── skill_installer.py
│   ├── sdk/                         # Module SDK implementation
│   │   ├── __init__.py
│   │   ├── catalogue_client.py
│   │   ├── userdb.py
│   │   ├── config.py
│   │   ├── context.py
│   │   ├── peers.py
│   │   ├── logger.py
│   │   └── testing.py
│   ├── tests/                       # 23 test files, 474 tests
│   │   ├── conftest.py
│   │   ├── test_*.py
│   │   └── fixtures/                # Broken/invalid modules for error testing
│   └── requirements.txt
├── mcp_server/
│   ├── server.py                    # MCP server factory (_LoggingFastMCP)
│   ├── transport.py                 # SSE + stdio transport setup
│   ├── tool_generator.py            # Auto-generates tools from module manifests
│   ├── __main__.py                  # stdio entry point
│   └── tools/                       # 10 tool groups, 40+ tools
│       ├── catalogue.py             # 7 tools
│       ├── inventory.py             # 6 tools
│       ├── workshops.py             # 8 tools
│       ├── version.py               # 3 tools
│       ├── settings.py              # 4 tools
│       ├── modules.py               # 12 tools
│       ├── data.py                  # 2 tools
│       ├── system.py                # 2 tools
│       ├── mcp_log.py               # 2 tools
│       └── users.py                 # 3 tools
├── frontend/
│   ├── src/
│   │   ├── main.tsx                 # Entry: QueryClient, theme, module registration
│   │   ├── App.tsx                  # RouterProvider wrapper
│   │   ├── router.tsx               # All routes (TanStack Router, code-based)
│   │   ├── index.css                # Tailwind v4 @theme, CSS vars, base styles
│   │   ├── components/
│   │   │   ├── ui/                  # Radix wrappers (Button, Card, Dialog, etc.)
│   │   │   ├── keywords/            # Core keyword widgets (7 types)
│   │   │   ├── version/             # Timeline, diff, badge, compare
│   │   │   ├── layout/              # Layout, Sidebar, Header, BottomPanel
│   │   │   └── catalogue/           # Card, form, property/step renderers
│   │   ├── hooks/                   # TanStack Query hooks per domain
│   │   ├── context/                 # WorkshopContext (global active workshop)
│   │   ├── theme/                   # Theme loader + token types
│   │   ├── modules/                 # View/panel/keyword registries
│   │   │   ├── registry.ts          # Auto-generated at build time
│   │   │   ├── view-registry.ts     # Pattern-based route matching
│   │   │   ├── panel-registry.ts    # Panel component registry
│   │   │   └── keyword-resolver.ts  # 3-layer keyword resolution
│   │   ├── routes/                  # Route page components
│   │   └── lib/                     # api.ts, types.ts, utils.ts
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
├── cli/
│   ├── main.py                      # Click CLI (40+ commands)
│   └── commands/
│       ├── mcp.py                   # MCP stdio entry
│       └── data.py                  # Export/import CLI
├── makestack_sdk/                   # Thin re-export layer for module authors
├── Dockerfile                       # Multi-stage: Node build → Python runtime
├── docker-compose.yml               # Core + Shell full-stack
├── docker-compose.dev.yml           # Dev override with hot-reload
├── docker-compose.hetzner.yml       # Hetzner + Cloudflare Tunnel production
├── HETZNER.md                       # Production deployment guide
├── pyproject.toml                   # Python packaging + deps
├── CLAUDE.md                        # This file
├── LICENSE                          # Proprietary (All Rights Reserved)
└── README.md
```

---

## Directory Layout (Runtime)

```
~/.makestack/                    # Shell's local state (not in Git)
├── userdb.sqlite                # UserDB — all personal state
├── cache/                       # Catalogue proxy cache
├── packages/                    # Package cache (cloned Git repos)
│   ├── modules/
│   ├── widgets/
│   ├── catalogues/
│   └── data/
├── registries/                  # Cloned registry repos
├── backups/                     # UserDB backups (auto + manual)
└── logs/                        # Log files (production mode)
```

---

## Shell API Reference

### Catalogue (Proxy to Core)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/catalogue/primitives` | List primitives (type-filtered) |
| GET | `/api/catalogue/search` | Full-text search |
| GET | `/api/catalogue/primitives/{path...}` | Read primitive |
| POST | `/api/catalogue/primitives/{path...}` | Create primitive |
| PUT | `/api/catalogue/primitives/{path...}` | Update primitive |
| DELETE | `/api/catalogue/primitives/{path...}` | Delete primitive |
| GET | `/api/catalogue/{path...}/history` | Version history |
| GET | `/api/catalogue/{path...}/diff` | Diff two versions |
| GET | `/api/catalogue/relationships/{path...}` | Cross-references |

### Inventory
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/inventory` | List all inventory items |
| POST | `/api/inventory` | Add item (creates hash-pointer) |
| GET | `/api/inventory/stale` | Items with newer catalogue versions |
| GET | `/api/inventory/{id}` | Read item with resolved catalogue data |
| PUT | `/api/inventory/{id}` | Update item |
| DELETE | `/api/inventory/{id}` | Remove item |
| GET | `/api/inventory/{id}/update-pointer` | Update hash to latest |

### Workshops
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/workshops` | List workshops |
| POST | `/api/workshops` | Create workshop |
| GET | `/api/workshops/{id}` | Read workshop with members |
| PUT | `/api/workshops/{id}` | Update workshop |
| DELETE | `/api/workshops/{id}` | Delete workshop |
| POST | `/api/workshops/active` | Set active workshop |
| POST | `/api/workshops/{id}/members` | Add member |
| DELETE | `/api/workshops/{id}/members/{ref}` | Remove member |
| GET | `/api/workshops/{id}/nav` | Workshop navigation items |
| POST | `/api/workshops/{id}/modules` | Assign module to workshop |

### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users/me` | Read user profile |
| PUT | `/api/users/me` | Update user profile |
| GET | `/api/users/me/stats` | Activity summary |

### Settings
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/settings` | Read preferences |
| PUT | `/api/settings/preferences` | Update preferences |
| GET | `/api/settings/theme` | Current theme name |
| PUT | `/api/settings/theme` | Set active theme |

### Modules
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/modules` | List installed modules |
| PUT | `/api/modules/{name}/enable` | Enable a module |
| PUT | `/api/modules/{name}/disable` | Disable a module |
| GET | `/api/modules/{name}/views` | Module view registrations |
| ANY | `/modules/{name}/{path...}` | Module-owned routes |

### Packages & Registries
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/packages` | List installed packages |
| POST | `/api/packages/install` | Install a package |
| POST | `/api/packages/uninstall` | Uninstall a package |
| POST | `/api/packages/{name}/update` | Update a package |
| GET | `/api/packages/search` | Search across registries |
| GET | `/api/packages/repair` | Recover from interrupted installs |
| GET | `/api/registries` | List configured registries |
| POST | `/api/registries` | Add a registry |
| DELETE | `/api/registries/{name}` | Remove a registry |

### Data (Export / Import)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/data/export` | Export UserDB as portable JSON |
| POST | `/api/data/import` | Import UserDB JSON |

### Backups
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/backups` | List available backups |
| GET | `/api/backups/{id}` | Get backup details |
| POST | `/api/backups/restore/{id}` | Restore from backup |
| DELETE | `/api/backups/{id}` | Delete a backup |

### Terminal & Logs
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/terminal/logs` | SSE log stream |
| WS | `/api/terminal/ws` | WebSocket log stream |

### MCP Action Log
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/mcp-log` | Paginated action audit log |
| POST | `/api/mcp-log` | Record an action |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | Shell health, Core connection, module states |
| GET | `/api/capabilities` | Machine-readable list of all operations |

### Version
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/version/{path}/history` | Primitive version timeline |
| GET | `/api/version/{path}/diff` | Structured field-level diff |

### Dev (dev mode only)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dev/modules` | Module debug info |
| GET | `/api/dev/keywords` | Keyword renderer registry |
| GET | `/api/dev/catalogue-proxy` | Core API calls + cache stats |
| GET | `/api/dev/userdb/tables` | UserDB table info |
| POST | `/api/dev/validate-module` | Validate module manifest |
| POST | `/api/dev/error` | Frontend error reporting |

---

## MCP Server

### Tool Inventory (40+ tools across 10 groups)

| Group | Count | Tools |
|-------|-------|-------|
| Catalogue | 7 | `search_catalogue`, `list_primitives`, `get_primitive`, `create_primitive`, `update_primitive`, `delete_primitive`, `get_relationships` |
| Inventory | 6 | `add_to_inventory`, `list_inventory`, `get_inventory_item`, `check_inventory_updates`, `update_inventory_pointer`, `remove_from_inventory` |
| Workshops | 8 | `list_workshops`, `get_workshop`, `create_workshop`, `update_workshop`, `delete_workshop`, `add_to_workshop`, `remove_from_workshop`, `set_active_workshop` |
| Version | 3 | `get_primitive_history`, `compare_versions`, `get_primitive_at_version` |
| Settings | 4 | `get_settings`, `update_settings`, `get_theme`, `set_theme` |
| Modules | 12 | `list_modules`, `enable_module`, `disable_module`, `list_packages`, `install_package`, `uninstall_package`, `update_package`, `search_packages`, `list_registries`, `add_registry`, `remove_registry`, `refresh_registries` |
| Data | 2 | `export_data`, `import_data` |
| System | 2 | `get_status`, `get_capabilities` |
| Users | 3 | `get_user_profile`, `update_user_profile`, `get_user_stats` |
| MCP Log | 2 | `list_mcp_actions`, `get_daily_summary` |

Module API endpoints are automatically exposed as MCP tools via `tool_generator.py` — no hardcoding per module. Tool naming: `{module_name}__{endpoint_name}`.

### Transport
- **SSE:** Mounted at `/mcp` in FastAPI, available at `/mcp/sse`
- **stdio:** `python -m mcp_server` or `makestack mcp`

### MCP Logging
`_LoggingFastMCP` subclass wraps all tool calls, logs to `/api/mcp-log` (tool_name, args, status, affected_paths, session_id). Non-blocking — never breaks tool execution.

---

## Data Model

### Six Primitives (in Core's catalogue)

| Primitive | What It Captures |
|-----------|-----------------|
| Tool | Instruments used to perform work |
| Material | Consumable inputs |
| Technique | Methods and skills |
| Workflow | Ordered sequences of techniques |
| Project | Concrete instances of making |
| Event | Time-bound occurrences within projects |

### UserDB Schema (7 migrations)

**Migration 001 — Core tables:**
- `users` (id, name, avatar_path, created_at, updated_at)
- `user_preferences` (user_id FK, key, value JSON)
- `workshops` (id, name, slug UNIQUE, description, icon, color, sort_order)
- `workshop_members` (workshop_id FK, primitive_path, primitive_type)
- `inventory` (id, catalogue_path, catalogue_hash, primitive_type, workshop_id FK)
- `installed_modules` (name PK, version, enabled, last_migration)
- `module_migrations` (module_name FK, migration_id)

**Migration 002** — `installed_modules.package_path TEXT` (local dev override)

**Migration 003** — Registry tables:
- `installed_registries` (name PK, git_url, added_at, last_refreshed)
- `installed_packages` (name PK, type, version, git_url, package_path, registry_name)

**Migration 004** — User profile fields: `users.bio`, `users.timezone`, `users.locale`

**Migration 005** — MCP action log:
- `mcp_action_log` (id, timestamp, tool_name, tool_args JSON, result_status, result_summary, affected_paths JSON, session_id, day)

**Migration 006** — Workshop-module associations:
- `workshop_modules` (workshop_id FK, module_name, sort_order, enabled)

**Migration 007** — Install transactions (rollback tracking):
- `install_transactions` (id, package_name, package_version, package_type, status, steps_completed JSON, failed_step, backup_path)

### Hash-Pointer Model

Inventory items reference catalogue entries via Git commit hashes:
```
inventory.catalogue_path = "materials/wickett-craig-5oz"
inventory.catalogue_hash = "a3f8c1d..."   ← immutable pointer to specific version
```

---

## Module System

### Module Loading Sequence
1. Read `installed_modules` table
2. Resolve manifest.json (from `package_path` or Python package)
3. Validate `ModuleManifest`
4. Run pending UserDB migrations
5. Import backend router
6. Mount router at `/modules/{name}/`
7. Register keywords, views, panels, endpoints in ModuleRegistry

### Module Manifest Fields
- `name`, `display_name`, `version`, `shell_compatibility`
- `has_backend`, `has_frontend`
- `keywords[]`, `api_endpoints[]`, `views[]`, `panels[]`
- `userdb_tables[]`, `dependencies`, `peer_modules`
- `core_api_permissions[]`, `config_defaults`
- `replaces_shell_view` — only "inventory", "workshops", or "catalogue"

### SDK Surfaces (for module authors)
```python
from makestack_sdk import (
    CatalogueClient, get_catalogue_client,    # Proxy to Core
    ModuleUserDB, get_module_userdb_factory,   # Scoped table access
    ShellContext, get_shell_context,           # user_id, workshop_id, version, dev_mode
    ModuleConfig, get_module_config_factory,   # Config merging
    PeerModules, get_peer_modules,             # Inter-module calls
    get_logger,                                # Pre-tagged structlog
    # Testing
    MockCatalogueClient, MockUserDB,
    MockShellContext, MockPeerModules,
    create_test_app,
)
```

### Frontend Module System
Three registries, all populated at startup via `registerAllModules()`:
- **View registry** — pattern-based route matching, caught by router's `defaultNotFoundComponent`
- **Panel registry** — panel components rendered on workshop home
- **Keyword resolver** — 3-layer priority: module > pack > core

### Package Types

| Type | What it is | Restart? |
|------|-----------|----------|
| `module` | Full-stack extension (backend + frontend + DB) | Yes |
| `widget-pack` | Frontend-only keyword renderer bundle | No |
| `catalogue` | Primitive data to merge into Core | No |
| `data` | Themes, presets, or other static files | No |
| `skill` | AI skill JSON definitions | No |

### Install Transaction Safety
Migration 007 tracks install steps. On startup, the module loader checks for `status='in_progress'` rows and automatically rolls back partial installs.

---

## Frontend Architecture

### Route Tree (TanStack Router, code-based in `router.tsx`)
- `/` → redirects to `/catalogue`
- `/catalogue` — type-filtered primitive list
- `/catalogue/search` — full-text search results
- `/catalogue/create` — create new primitive
- `/catalogue/detail` — primitive detail view (path + optional at hash)
- `/catalogue/edit` — edit primitive
- `/inventory` — inventory list
- `/inventory/detail` — inventory item detail
- `/workshops` — workshop list
- `/workshops/detail` — workshop detail
- `/workshop/$id` — active workshop home (renders panels)
- `/workshop/$id/settings` — workshop configuration
- `/settings` — user preferences, theme switcher
- `/packages` — package/module management
- `/dev/keywords` — keyword widget docs (dev only)
- `/dev/schema` — UserDB schema viewer (dev only)
- `/dev/modules` — module debug info (dev only)
- `/dev/docs` — API documentation (dev only)
- Catch-all → `ModuleViewRenderer` (resolves against module view registry)

### Layout Structure
```
<Layout>
  <StaleBanner>           (dismissed when Core unreachable)
  <Sidebar>               (w-52, workshop context, module nav, shell nav, dev tools)
  <Header>                (breadcrumbs, search, workshop switcher, Core indicator)
  <main>                  (route outlet)
  <BottomPanel>           (resizable: Terminal tab, Log tab)
</Layout>
```

### Key Patterns
- `WorkshopContext` — global active workshop state, persists via backend
- All navigate calls to `/catalogue/detail` require `at: undefined` explicitly
- `erasableSyntaxOnly: true` — no parameter-shorthand class properties
- `ModuleErrorBoundary` wraps untrusted module/pack keyword renderers
- Bottom panel state saved to sessionStorage
- `apiGet/apiPost/apiPut/apiDelete` in `lib/api.ts` — typed HTTP client
- Dev tools section only shown when `dev_mode: true` from `/api/status`

### Core Keyword Widgets
`TIMER_`, `MEASUREMENT_`, `MATERIAL_REF_`, `TOOL_REF_`, `TECHNIQUE_REF_`, `IMAGE_`, `LINK_`, `NOTE_`, `CHECKLIST_`

---

## Backend Architecture

### Key Infrastructure

**CatalogueClient** (`core_client.py`) — LRU cache with stale-while-revalidate:
- Fresh hit → return cached
- Stale + Core up → return cached, refresh async
- Stale + Core down → return stale with warning
- Cache miss + Core down → raise `CoreUnavailableError`
- List/search TTL: 5 min. Individual items: 30 min. Max 500 entries.

**UserDB** (`userdb.py`) — async SQLite:
- WAL mode, FK enforced, row factory → dicts
- Methods: `fetch_one`, `fetch_all`, `execute`, `execute_returning`, `count`
- Backup/restore: native async backup, retention policy pruning

**LogBroadcaster** (`log_broadcast.py`) — SSE fan-out:
- structlog processor broadcasts every log event to SSE subscribers
- Non-blocking (slow subscribers drop events)

**Dependencies** (`dependencies.py`) — all singletons on `app.state`:
- `app.state.core_client` → CatalogueClient
- `app.state.userdb` → UserDB
- `app.state.module_registry` → ModuleRegistry
- `app.state.registry_client` → RegistryClient
- `app.state.package_cache` → PackageCache
- `app.state.config` → dict
- `app.state.dev_mode` → bool
- `app.state.core_connected` → bool (updated by health poll every 30s)

### Startup Sequence
1. Load config from environment
2. Configure structlog (JSON or console based on dev_mode)
3. Open UserDB + run migrations (001-007)
4. Attempt Core connection (log warning if unavailable)
5. Load and mount all modules (validate, migrate, mount routers)
6. Mount frontend static files
7. Start background tasks (Core health polling, daily backup)

### Degraded Mode
Shell starts even when Core is unreachable:
- Catalogue reads → cached data with staleness warning
- Catalogue writes/search → disabled with clear message
- Inventory, workshops, settings, user profile → fully functional (local)
- MCP server → functional for local operations, degraded for catalogue

---

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `MAKESTACK_CORE_URL` | `http://localhost:8420` | Core API base URL |
| `MAKESTACK_CORE_API_KEY` | *(none)* | API key for Core auth |
| `MAKESTACK_USERDB_PATH` | `~/.makestack/userdb.sqlite` | Personal database path |
| `MAKESTACK_DEV_MODE` | `false` | Enable dev logging + routes |
| `MAKESTACK_PORT` | `3000` | Shell listen port |
| `MAKESTACK_HOME` | `~/.makestack` | Base config directory |
| `MAKESTACK_API_KEY` | *(none)* | Shell API key (for auth) |
| `MAKESTACK_SHELL_URL` | `http://localhost:3000` | MCP server target (stdio mode) |
| `MAKESTACK_SHELL_TOKEN` | *(none)* | MCP server auth token |
| `MAKESTACK_MCP_ALLOWED_HOSTS` | *(none)* | Reverse-proxy domains for MCP |

---

## Code Standards

### Python (Backend)
- Python 3.10+ (use `str | None` union syntax, etc.)
- Type hints on all function signatures
- Async everywhere — FastAPI endpoints, httpx calls, aiosqlite queries
- Pydantic 2.x for all request/response models
- structlog for logging (tagged by component)
- pytest + pytest-asyncio for tests
- Error responses always include `suggestion` field for AI consumption

### TypeScript (Frontend)
- Strict mode enabled, `erasableSyntaxOnly: true`
- No `any` — use `unknown` + type guards
- TanStack Query for all server state
- TanStack Router for all navigation
- Tailwind only — no inline styles, no CSS modules

### General
- API-first: build the endpoint before the UI
- No silent failures: log warnings, return structured errors
- Route ordering: specific routes before `/{id}` catch-alls
- Conventional Commits (`feat:`, `fix:`, `docs:`, etc.)

---

## Testing

```bash
# Run all tests
python3 -m pytest backend/tests/ -x -q

# Install dev dependencies
pip install -e ".[dev]"
```

**474 tests** across 23 test files covering: Core client + cache, UserDB + migrations, all 14 routers, module manifest validation, module SDK, module loader, package management, registry client, package cache, installers, MCP server, MCP logging, terminal/logs, backups, workshop modules, Phase 10 rollback, and end-to-end integration.

**Test patterns:**
- In-memory UserDB: `UserDB(":memory:")` + `await db.run_migrations()`
- Mock Core: `unittest.mock.AsyncMock` on `CatalogueClient` spec
- ASGI test client: `httpx.AsyncClient(transport=ASGITransport(app=test_app))`
- Dependency overrides: `app.dependency_overrides[get_userdb] = lambda: db`

---

## Current State

Shell: **v0 Feature-Complete + Post-v0 Hardening**

All seven original phases are complete. Post-v0 additions include:
- User account management (profile, stats, bio/timezone/locale)
- MCP action audit logging (transparent tool call tracking)
- Terminal and live log streaming (SSE + WebSocket)
- UserDB backup system (automated nightly + manual + retention policy)
- Install transaction safety (automatic rollback of partial installs)
- Workshop-module associations (per-workshop module assignment)
- Module frontend system (Phase 8B — view/panel/keyword registries with error boundaries)
- Production deployment (Hetzner + Cloudflare Tunnel, see HETZNER.md)

**Test suite:** 474 tests, all passing.

---

## Next Steps

_Post-v0 work to be defined._

---

## Decisions Made

- **Licensing:** Shell is proprietary (All Rights Reserved). Core is MIT open-source.
- **Two clients, one API:** React frontend and MCP server both hit the same FastAPI backend.
- **Three extension types:** Widgets (stateless, frontend-only), Modules (full-stack), Registry (Git-native).
- **Five package types:** module, widget-pack, catalogue, data, skill.
- **Widget packs do NOT require Shell restart** (frontend-only). Modules DO require restart.
- Shell is Python/FastAPI + React (not Go, not Next.js, not Electron)
- UserDB is SQLite via aiosqlite, WAL mode
- Module tables typed with real columns, FK to inventory
- Hash-pointer model: inventory references catalogue via Git commit hash
- Theme system: JSON → CSS custom properties → Tailwind
- Default ports: Shell on 3000, Core on 8420
- MCP server is a thin layer over the REST API — never bypasses it
- Module API endpoints auto-generate MCP tools from manifest declarations
- MCP supports SSE (remote) and stdio (local) transports
- Error responses include actionable `suggestion` field for AI consumption
- Module tools use `{module_name}__{endpoint_name}` naming
- MCP tool calls are audit-logged transparently
- Install transactions tracked for automatic rollback on failure

## Decisions Deferred

- Open-sourcing the Shell
- Multi-user authentication (JWT sessions — API key for v0)
- Module marketplace or discovery service
- Mobile-responsive layout (desktop-first for v0)
- Electron/Tauri desktop wrapper
- MCP resource endpoints (tools-only for v0)
- MCP prompts (pre-built prompt templates)
