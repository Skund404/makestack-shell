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
- **Exposes an MCP server so AI agents can fully operate the system**

It is intentionally boring infrastructure with no domain opinion. Every domain feature (inventory, costing, suppliers) lives in a module. The Shell just makes sure modules have what they need to run.

**Two clients, one API:** The Shell has exactly two consumers — the React frontend (for humans) and the MCP server (for AI agents). Both hit the same FastAPI backend. There is no separate "AI API" — the REST API is designed to be complete enough that either client can do everything.

**Previous project:** HideSync (leatherwork-specific ERP). Abandoned due to deep technical debt from an encryption layer that permeated the backend. Makestack is the architecturally clean successor.

**Companion repo:** makestack-core (Go 1.24, single binary) — the headless catalogue engine. Manages JSON files in Git, maintains a SQLite read index, serves data via REST API. Core is already feature-complete for v0. Binary name: `makestack-core`. Default port: 8420. Default DB: in-memory (rebuilt from Git on startup). Writes auto-commit to Git; file watcher updates index async (~200ms).

---

## Architecture

Three named layers + two access paths:

- **Catalogue** = makestack-core (separate repo, feature-complete). Impersonal, canonical knowledge. No user state, no ownership.
- **Shell** = This repo (makestack-app). Host application: React frontend + Python/FastAPI backend. Owns UserDB, module registry, auth, routing, keyword renderers, theme system.
- **Inventory** = A concept within the Shell's UserDB, extended by modules. A user's personal relationship to the catalogue (what they own, how much, what they paid). References catalogue entries via immutable Git commit hashes, never copies them.

```
┌─────────────────────────────────┐
│   SEPARATE REPO: CORE (Go)     │
│   = THE CATALOGUE               │
│                                 │
│   Impersonal documented knowledge│
│   Already built. Feature-complete│
│   Default: localhost:8420       │
│                                 │
│   Run: makestack-core           │
│     -data <path-to-git-repo>    │
│     -addr :8420                 │
│     -db :memory: (or file path) │
│     -api-key <key>              │
│     --public-reads              │
└───────────────────┬─────────────┘
                    │ REST API (JSON over HTTP)
                    │ (Shell is the ONLY client)
┌───────────────────▼─────────────────────────────────────┐
│   THIS REPO: SHELL                                      │
│                                                         │
│   ┌──────────────────────────────────────────────┐      │
│   │          FastAPI Backend                      │      │
│   │                                              │      │
│   │   Catalogue proxy (to Core)                  │      │
│   │   UserDB (SQLite — inventory, workshops)     │      │
│   │   Module system (routers, SDK, migrations)   │      │
│   │   Settings, auth, health checks              │      │
│   │                                              │      │
│   │   ALL operations available as REST endpoints │      │
│   │   No UI-only operations exist                │      │
│   └──────┬──────────────────────┬────────────────┘      │
│          │                      │                        │
│    ┌─────▼──────┐       ┌──────▼──────┐                 │
│    │   React    │       │  MCP Server │                  │
│    │  Frontend  │       │  (SSE/stdio)│                  │
│    │            │       │             │                  │
│    │  For humans│       │  For AI     │                  │
│    │  Theme,    │       │  agents     │                  │
│    │  keywords, │       │             │                  │
│    │  visual UI │       │  Same ops,  │                  │
│    └────────────┘       │  structured │                  │
│                         │  tool calls │                  │
│                         └─────────────┘                  │
└─────────────────────────────────────────────────────────┘
```

**Rules:**
- The Shell is the only client of Core; modules never talk to Core directly
- The catalogue never knows about the user
- The inventory never stores what the catalogue already knows — it stores hash-pointer references
- Uninstall every module → the Shell still works (catalogue browsing, search, edit, workshops)
- The Shell has no domain opinion — it doesn't know what leatherworking, costing, or inventory tracking is
- **Every Shell operation must be reachable via REST API** — no operation should require the frontend
- **The MCP server wraps the REST API** — it doesn't bypass it or talk to UserDB directly

---

## MCP Integration (Core Design Principle)

### Why MCP Is Foundational, Not a Feature

Makestack is built for makers who use AI as a collaborator. The MCP server is not an add-on — it is a first-class access path, equivalent to the React frontend. Every feature built for the UI must also be accessible via MCP.

### MCP Tool Inventory

**Catalogue**
- `search_catalogue` — full-text search across the catalogue
- `browse_catalogue` — list primitives by type with filtering
- `get_primitive` — read a single primitive with full keyword resolution
- `create_primitive` — create a new catalogue entry
- `update_primitive` — edit an existing entry
- `delete_primitive` — remove an entry
- `get_primitive_hash` — get the last-modified-commit hash for inventory pinning

**Inventory**
- `list_inventory` — list all inventory items with resolved catalogue data
- `add_to_inventory` — create an inventory record pointing to a catalogue entry
- `get_inventory_item` — read an inventory item with resolved catalogue data
- `check_inventory_updates` — which inventory items have newer catalogue versions available
- `update_inventory_pointer` — update an inventory item's hash to the latest catalogue version

**Workshops**
- `list_workshops` — list all workshops
- `create_workshop` — create a new workshop
- `set_active_workshop` — switch the active organizational context
- `add_to_workshop` — assign a primitive to a workshop
- `remove_from_workshop` — remove a primitive reference from a workshop

**Modules**
- `list_modules` — list installed modules with status
- `call_module` — invoke a module's API endpoint (generic passthrough)
- `get_module_data` — read data from a module's tables (via the module's own API)
- `enable_module` / `disable_module` — toggle modules on/off

**Packages / Registry**
- `install_package` — install a module, widget pack, catalogue, or data pack by name or URL
- `uninstall_package` — uninstall a package
- `search_packages` — search across all registries
- `list_packages` — list all installed packages with types and versions
- `list_registries` — list configured registries

**Settings**
- `get_settings` — read current preferences and config
- `update_settings` — change preferences

**System**
- `get_status` — Shell health, Core connection state, loaded modules
- `get_capabilities` — list all available operations (self-describing)

### Design Rules for MCP Compatibility

These rules apply to ALL Shell development, not just the MCP server itself:

1. **No UI-only operations.** Every action the React frontend can perform must have a corresponding REST endpoint. If you're building a UI feature, build the API endpoint first, then build the UI that calls it.

2. **Structured responses everywhere.** Every API endpoint returns typed JSON (Pydantic models). No HTML fragments, no rendered templates, no bare strings. The AI needs to parse and reason about the response.

3. **Descriptive error messages.** API errors must include enough context for an AI to understand what went wrong and how to fix it. `{"error": "not found"}` is insufficient. `{"error": "Primitive not found", "path": "materials/wickett-craig-5oz/manifest.json", "suggestion": "Use search_catalogue to find the correct path"}` is useful.

4. **Pagination with metadata.** List endpoints return `{"items": [...], "total": N, "limit": 50, "offset": 0}` — the AI needs to know if there are more results.

5. **Idempotent operations where possible.** Creating a technique that already exists should either return the existing one or return a clear conflict error, not silently duplicate.

6. **Self-describing API.** `GET /api/capabilities` returns a machine-readable description of all available operations, their parameters, and their return types. The MCP tool list is generated from this.

7. **Module operations exposed generically.** The Shell doesn't hardcode MCP tools per module. Instead, it provides a generic `call_module` tool that can invoke any module's registered API endpoints. Module manifests already declare their endpoints — the MCP server reads these declarations to describe available module operations to the AI.

### MCP Transport

The MCP server supports two transports:

- **SSE (Server-Sent Events):** For remote/network access. The Shell serves the MCP SSE endpoint alongside the REST API. This is how Claude.ai MCP connectors would connect.
- **stdio:** For local development. `makestack mcp` runs the MCP server on stdin/stdout for direct process-level integration with Claude Code or other local AI tools.

```bash
# Remote: SSE transport (served by Shell alongside REST API)
# Available at http://localhost:3000/mcp/sse

# Local: stdio transport (for Claude Code, etc.)
makestack mcp
```

### Module MCP Exposure

When a module is installed, its API endpoints become available through MCP automatically:

1. Module manifest declares its API endpoints with descriptions and parameter schemas
2. Shell's module loader reads these declarations at startup
3. MCP server generates tool definitions from module endpoint declarations
4. AI agent sees module tools alongside Shell tools — no distinction needed

Example: If the inventory-stock module is installed and declares `GET /stock/{material_path}`, the MCP server exposes a tool `inventory_stock__get_stock` that the AI can call.

Module tool naming convention: `{module_name}__{endpoint_name}` (double underscore separator).

---

## Tech Stack (This Repo)

### Backend
- **Language:** Python 3.12+
- **Framework:** FastAPI (async)
- **HTTP client:** httpx (async, for Core communication)
- **Database:** SQLite via aiosqlite (UserDB — local personal state)
- **Validation:** Pydantic 2.x
- **Logging:** structlog (tagged, structured)
- **Testing:** pytest + pytest-asyncio
- **Module SDK:** `makestack-sdk` package (provided by this repo, consumed by modules)
- **MCP server:** `mcp` Python SDK (SSE + stdio transports)

### Frontend
- **Framework:** React 18+
- **Routing:** TanStack Router (file-based routes)
- **Data fetching:** TanStack Query
- **Styling:** Tailwind CSS (config-driven from theme JSON)
- **Components:** Radix UI primitives wrapped in `@makestack/ui`
- **Icons:** Lucide React
- **Charts:** Recharts
- **Build:** Vite
- **Primary font:** Lexend (dyslexia-friendly, research-backed readability)
- **Mono font:** JetBrains Mono (distinct characters for measurements/data)

### Infra
- **Container:** Docker + docker-compose (runs Core + Shell together)
- **CLI:** Click or Typer (for `makestack` command)

---

## Core API Reference (What This Shell Consumes)

Core is already running and feature-complete. The Shell is Core's ONLY client.

**Core connection:** `http://localhost:8420` (configurable, default port 8420)

**Auth:** `Authorization: Bearer <key>` or `X-API-Key: <key>` header. If Core is started with `--public-reads`, GET endpoints are open; writes still require the key. If no key is configured, Core logs a warning and runs open.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Always public. Returns `{"status":"ok"}` |
| GET | `/primitives/{type}` | List primitives of a type (tools/materials/techniques/workflows/projects/events) |
| GET | `/primitives/{type}/{path...}/manifest.json` | Read a primitive |
| POST | `/primitives/{type}/{path...}/manifest.json` | Create a primitive |
| PUT | `/primitives/{type}/{path...}/manifest.json` | Update a primitive |
| DELETE | `/primitives/{type}/{path...}/manifest.json` | Delete a primitive |
| GET | `/primitives/{type}/{path...}/hash` | Last-modified-commit hash for this path |
| GET | `/search?q=&type=&limit=&offset=` | Full-text search |
| GET | `/primitives/{type}/{path...}/manifest.json?at={hash}` | Version-specific read |
| GET | `/history/{type}/{path...}/manifest.json` | Commit history for a path |
| GET | `/diff/{type}/{path...}/manifest.json?from={hash}&to={hash}` | Structured diff |
| GET | `/config` | Active config from `.makestack/config.json` |
| GET | `/themes` | List available themes |
| GET | `/themes/{name}` | Read a theme JSON |

**Key implementation notes:**
- Core speaks JSON over HTTP — no gRPC, no GraphQL
- All write operations auto-commit to Git
- File watcher updates index async after commits (~200ms lag)
- `?at={hash}` reads directly from Git object store, bypassing SQLite
- `/hash` returns the last-modified-commit hash for that specific path (NOT repo HEAD)
- Version-specific reads return 503 when the writer is nil

---

## Shell API Reference

### Catalogue (Proxy)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/catalogue/{type}` | List primitives (proxied + cached) |
| GET | `/api/catalogue/{type}/{path...}` | Read primitive (proxied + cached) |
| POST | `/api/catalogue/{type}/{path...}` | Create primitive (proxied, clears cache) |
| PUT | `/api/catalogue/{type}/{path...}` | Update primitive (proxied, clears cache) |
| DELETE | `/api/catalogue/{type}/{path...}` | Delete primitive (proxied, clears cache) |
| GET | `/api/catalogue/search` | Search (proxied) |
| GET | `/api/catalogue/{type}/{path...}/history` | Version history (proxied) |
| GET | `/api/catalogue/{type}/{path...}/diff` | Diff two versions (proxied) |

### Inventory
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/inventory` | List all inventory items |
| POST | `/api/inventory` | Add item (creates hash-pointer) |
| GET | `/api/inventory/{id}` | Read item with resolved catalogue data |
| PUT | `/api/inventory/{id}` | Update item |
| DELETE | `/api/inventory/{id}` | Remove item |
| POST | `/api/inventory/{id}/update-pointer` | Update hash to latest catalogue version |
| GET | `/api/inventory/stale` | List items with newer catalogue versions |

### Workshops
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/workshops` | List workshops |
| POST | `/api/workshops` | Create workshop |
| GET | `/api/workshops/{id}` | Read workshop |
| PUT | `/api/workshops/{id}` | Update workshop |
| DELETE | `/api/workshops/{id}` | Delete workshop |
| POST | `/api/workshops/{id}/members` | Add member |
| DELETE | `/api/workshops/{id}/members/{ref}` | Remove member |
| POST | `/api/workshops/active` | Set active workshop |

### Settings
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/settings` | Read user preferences |
| PUT | `/api/settings` | Update preferences |
| GET | `/api/settings/theme` | Current theme name |
| PUT | `/api/settings/theme` | Set active theme |
| GET | `/api/settings/theme/data` | CSS variable map for active theme |

### Modules
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/modules` | List installed modules |
| POST | `/api/modules/{name}/enable` | Enable a module |
| POST | `/api/modules/{name}/disable` | Disable a module |
| ANY | `/modules/{name}/{path...}` | Module-owned routes |

### Packages / Registry
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/packages` | List installed packages |
| POST | `/api/packages/install` | Install a package |
| DELETE | `/api/packages/{name}` | Uninstall a package |
| POST | `/api/packages/{name}/update` | Update a package to latest version |
| GET | `/api/packages/search?q=` | Search across all registries |
| GET | `/api/registries` | List configured registries |
| POST | `/api/registries` | Add a registry |
| DELETE | `/api/registries/{name}` | Remove a registry |

### Data (Export / Import)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/data/export` | Export UserDB as portable JSON |
| POST | `/api/data/import` | Import UserDB JSON (additive / overwrite / skip_conflicts) |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | Shell health, Core connection, module states |
| GET | `/api/capabilities` | Machine-readable list of all operations |

### Dev (dev mode only)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dev/modules` | Module debug info |
| GET | `/api/dev/keywords` | Keyword renderer registry |
| GET | `/api/dev/catalogue-proxy` | Recent Core API calls + cache stats |
| GET | `/api/dev/userdb/tables` | UserDB table info |
| GET | `/api/dev/userdb/query?sql=` | Read-only SQL (dev only) |
| GET | `/api/dev/config` | Resolved config |
| POST | `/api/dev/validate-module` | Validate module manifest |
| GET | `/api/dev/health` | Full system health |
| POST | `/api/dev/error` | Frontend error reporting |

---

## Data Model

### Six Primitives (in Core's catalogue)

| Primitive | What It Captures |
|-----------|-----------------|
| Tool | Instruments used to perform work |
| Material | Consumable inputs |
| Technique | Methods and skills |
| Workflow | Ordered sequences of techniques |
| Project | Concrete instances of making (recursive via `parent_project`) |
| Event | Time-bound occurrences within projects |

### UserDB (This repo's SQLite — personal state)

The Shell owns a local SQLite database at `~/.makestack/userdb.sqlite`. It stores everything personal — things Core doesn't know about.

**Core tables (Shell-owned):**

```sql
inventory_items
  id TEXT PRIMARY KEY
  catalogue_path TEXT NOT NULL        -- e.g. "materials/wickett-craig-5oz"
  catalogue_hash TEXT NOT NULL        -- Git commit hash (immutable pointer)
  quantity REAL
  unit TEXT
  notes TEXT
  meta JSON                           -- namespace-scoped module data
  created_at TEXT
  updated_at TEXT

workshops
  id TEXT PRIMARY KEY
  name TEXT NOT NULL
  description TEXT
  is_active INTEGER DEFAULT 0
  created_at TEXT

workshop_members
  workshop_id TEXT REFERENCES workshops(id)
  ref_type TEXT                       -- "catalogue" | "inventory"
  ref_path TEXT
  added_at TEXT

installed_modules
  name TEXT PRIMARY KEY
  version TEXT
  enabled INTEGER DEFAULT 1
  package_path TEXT                   -- local dev override
  installed_at TEXT

module_migrations
  module_name TEXT
  migration_id TEXT
  applied_at TEXT

user_preferences
  key TEXT PRIMARY KEY
  value JSON

registries
  name TEXT PRIMARY KEY
  url TEXT NOT NULL
  last_refreshed TEXT

installed_packages
  name TEXT PRIMARY KEY
  type TEXT                           -- module | widget-pack | catalogue | data
  version TEXT
  source_url TEXT
  installed_at TEXT
```

**Module tables** are defined by each module's migrations and are prefixed with the module name (e.g., `inventory_stock_entries`).

### Hash-Pointer Model

Inventory items reference catalogue entries via Git commit hashes, not by path alone:

```
inventory_item.catalogue_path = "materials/wickett-craig-5oz"
inventory_item.catalogue_hash = "a3f8c1d..."   ← specific version
```

This means:
- Inventory always knows exactly which version of a catalogue entry it was built against
- The catalogue can evolve without silently breaking inventory records
- The Shell can detect when a catalogue entry has been updated since it was added to inventory
- Version-specific reads (`?at={hash}`) let the Shell show the entry as it was at that hash

---

## Extensibility: Widgets, Modules, and Registry

The Shell has three extension mechanisms, each with a different weight and purpose. Understanding the separation is critical — they are NOT the same thing.

### 1. Widgets (Frontend-Only Keyword Renderers)

Widgets are **stateless, frontend-only components** invoked by JSON keywords. When a manifest contains a keyword like `TIMER_: "10min"`, the Shell's keyword renderer detects it and instantiates the corresponding widget.

**Key properties:**
- Pure React components — no Python backend, no API routes, no UserDB tables
- No installation infrastructure — they are present at frontend build time
- Stateless — they receive a keyword value and render it, nothing more
- Degrade gracefully — if the renderer is absent, the raw JSON value displays as text
- The data is already meaningful without the widget — widgets are UI enhancement, not data

**Widgets come from three sources:**
- **Core widgets** — shipped with the Shell (TIMER_, MEASUREMENT_, MATERIAL_REF_, etc.)
- **Widget packs** — installable bundles of keyword renderers (via the registry)
- **Module widgets** — keyword renderers registered by a full module as part of its frontend

A widget pack is just a Git repo containing React components and a manifest declaring which keywords they render. Installing a widget pack triggers a frontend rebuild but does NOT require a Shell restart — no backend is involved.

```
makestack-widget-pack-timers/
├── makestack-package.json       # type: "widget-pack", declares keywords
├── components/
│   ├── Timer.tsx                # Renders TIMER_
│   ├── Countdown.tsx            # Renders COUNTDOWN_
│   └── Stopwatch.tsx            # Renders STOPWATCH_
└── index.ts                     # Exports keyword → component map
```

### 2. Modules (Full-Stack Extensions)

Modules are **full-stack extensions** (Python backend + React frontend) that add domain features to the Shell. They are fundamentally heavier than widgets.

**What modules can do that widgets cannot:**
- Own backend API routes (mounted at `/modules/{name}/`)
- Declare and migrate UserDB tables (personal data storage)
- Access the catalogue via the SDK's CatalogueClient
- Write to `meta` namespaces on catalogue primitives
- Register panels, sidebar entries, and pages (not just keyword renderers)
- Have configuration files (`.makestack/modules/{name}.config.json`)
- Declare peer dependencies on other modules
- Be invoked via MCP tools

**Examples:** Inventory, Cost Tracker, CRM, Supplier Management, CNC Feeds & Speeds, Export Engine.

A module CAN also register keyword renderers — but that's a module providing widgets as part of its larger feature set, not a standalone widget.

**Module install flow:**
1. Resolve via registry → Git URL → clone to package cache
2. Dependency check (strict for Python, permissive for Node)
3. Install Python dependencies
4. Install Node dependencies (if has_frontend)
5. Register in `installed_modules` table
6. Run UserDB migrations
7. Frontend rebuild (includes module's keyword renderers and panels)
8. Shell restart required

```
makestack-module-inventory/
├── makestack-package.json       # type: "module"
├── manifest.json                # Module contract (keywords, endpoints, tables, permissions)
├── backend/
│   ├── __init__.py
│   ├── routes.py                # FastAPI router
│   ├── services.py
│   └── migrations/
│       └── 001_create_stock_table.py
├── frontend/
│   ├── components/
│   │   └── StockBadge.tsx       # Keyword renderer (this is a widget provided BY a module)
│   ├── keywords.ts
│   └── index.ts
└── tests/
```

### 3. Registry / Package Manager (Git-Native)

The registry is a **Git-native package manager** built into the Shell. It is the mechanism by which Makestack proliferates — not an afterthought, but a core feature.

**Two-level structure:**
1. **Primary index** — a JSON file in the data repo (`.makestack/config.json` points to it) listing trusted registries
2. **Registries** — Git repos containing `index.json` files that list packages with their Git URLs and metadata

**Four installable package types:**

| Type | What it is | Restart? |
|------|-----------|----------|
| `module` | Full-stack extension (backend + frontend + DB) | Yes |
| `widget-pack` | Frontend-only keyword renderer bundle | No |
| `catalogue` | Primitive data to merge into Core | No |
| `data` | Themes, presets, or other static files | No |

**Package cache:** Cloned repos live in `~/.makestack/packages/`. Version switching and updates are done via Git operations on the cached clone.

---

## Keywords and Widgets

JSON manifests contain special keywords (uppercase, trailing underscore) that the Shell's keyword renderer resolves to **widgets** — stateless React components:

```json
{ "TIMER_": "30min" }        → renders countdown timer widget
{ "MEASUREMENT_": "4mm" }    → renders measurement widget with unit conversion
```

**Three sources of keyword renderers (all are widgets):**
- **Core widgets** (shipped with Shell): TIMER_, MEASUREMENT_, MATERIAL_REF_, TOOL_REF_, TECHNIQUE_REF_, IMAGE_, LINK_, NOTE_, CHECKLIST_
- **Widget packs** (installed via registry): standalone frontend-only bundles, no backend
- **Module widgets** (registered by modules): keyword renderers that are part of a full-stack module (e.g., INVENTORY_STOCK_ from the inventory module)

**Resolution order:** Module widgets override widget pack widgets override core widgets (for the same keyword). Unknown keywords display as raw text (graceful degradation).

**Detection:** regex `^[A-Z][A-Z0-9_]*_$` on JSON keys.

See **03-JSON-KEYWORD-CONVENTION.md** for full spec.

---

## Directory Layout (Runtime)

```
~/.makestack/                    # Shell's local state (not in Git)
├── userdb.sqlite                # UserDB — all personal state
├── cache/                       # Catalogue proxy cache
├── packages/                    # Package cache (cloned Git repos)
│   ├── modules/
│   │   └── inventory-stock/     # Cloned module repo
│   ├── widgets/
│   │   └── timer-widgets/       # Cloned widget pack repo
│   └── catalogues/
│       └── leatherwork/         # Cloned catalogue repo
├── registries/                  # Cloned registry repos
│   ├── official/
│   └── community-leather/
└── logs/                        # Log files (production mode)

<data-repo>/                     # Managed by Core (Git)
├── .makestack/
│   ├── config.json
│   ├── themes/
│   └── modules/
├── materials/
├── techniques/
├── tools/
├── workflows/
├── projects/
└── events/
```

---

## Directory Layout (Repo)

```
makestack-app/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core_client.py
│   │   ├── models.py
│   │   ├── module_manifest.py
│   │   ├── module_loader.py
│   │   ├── routers/
│   │   │   ├── catalogue.py
│   │   │   ├── inventory.py
│   │   │   ├── workshops.py
│   │   │   ├── settings.py
│   │   │   ├── modules.py
│   │   │   ├── packages.py
│   │   │   ├── data.py
│   │   │   ├── system.py
│   │   │   └── dev.py
│   │   └── migrations/
│   │       ├── 001_initial_schema.py
│   │       └── ...
│   ├── sdk/                          # makestack-sdk package (consumed by modules)
│   │   ├── __init__.py
│   │   ├── catalogue_client.py
│   │   ├── userdb.py
│   │   ├── config.py
│   │   ├── context.py
│   │   ├── peers.py
│   │   ├── logger.py
│   │   └── testing.py
│   ├── requirements.txt
│   └── tests/
├── mcp_server/
│   ├── __init__.py
│   ├── server.py                     # MCP server (tool definitions + handlers)
│   ├── tools/
│   │   ├── catalogue.py
│   │   ├── inventory.py
│   │   ├── workshops.py
│   │   ├── modules.py
│   │   ├── version.py
│   │   ├── settings.py
│   │   ├── data.py
│   │   └── system.py
│   ├── transport.py                  # SSE + stdio transport setup
│   └── tool_generator.py            # Auto-generates tool defs from module manifests
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── routes/
│   │   ├── components/
│   │   │   ├── primitives/
│   │   │   ├── keywords/
│   │   │   ├── version/
│   │   │   ├── layout/
│   │   │   └── ui/                   # @makestack/ui (Radix wrappers)
│   │   ├── hooks/
│   │   ├── theme/
│   │   ├── modules/
│   │   │   ├── registry.ts           # Auto-generated at build time
│   │   │   └── keyword-resolver.ts
│   │   └── lib/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── vite.config.ts
├── cli/
│   ├── __init__.py
│   ├── main.py                       # `makestack` CLI entry point
│   ├── commands/
│   │   ├── start.py
│   │   ├── dev.py
│   │   ├── module.py
│   │   ├── data.py
│   │   └── mcp.py
│   └── ...
├── docker-compose.yml
├── docker-compose.dev.yml
├── Dockerfile
├── CLAUDE.md                         # This file
├── LICENSE                           # Proprietary (All Rights Reserved)
├── README.md
└── CONTRIBUTING.md
```

---

## Startup Sequence

```
1. Parse CLI flags and environment variables
2. Open UserDB at ~/.makestack/userdb.sqlite (create if first run)
3. Run Shell-owned migrations (core tables)
4. Attempt Core connection (localhost:8420 by default)
   ├─ Success → load config from .makestack/config.json via Core API
   └─ Failure → load cached config if available, enter degraded mode
5. Discover installed modules (read installed_modules table)
   For each enabled module:
     a. Import the Python package
     b. Read its manifest.json
     c. Validate manifest against current Shell version
     d. Run pending UserDB migrations
     e. Mount its FastAPI router at /modules/{name}/
     f. Collect keyword renderer registrations
     g. Collect panel registrations
     h. Inject CatalogueClient and UserDB access via DI
6. Build keyword renderer registry (Shell core + all modules)
7. Build capabilities registry (all endpoints + module endpoints)
8. Start FastAPI server (serves REST API + frontend + MCP SSE endpoint)
9. Begin Core health check polling
10. Log startup summary
```

### Degraded Mode

The Shell MUST start even when Core is unreachable:

| Feature | When Core is down | Source |
|---------|------------------|--------|
| Catalogue browsing | Cached data with staleness warning | Proxy cache |
| Catalogue search | Disabled with clear message | Requires Core |
| Catalogue create/edit | Disabled with clear message | Requires Core |
| Inventory browsing | Fully functional | UserDB (local) |
| Workshop management | Fully functional | UserDB (local) |
| Settings | Fully functional | UserDB (local) |
| Theme | Fully functional | Already loaded |
| MCP server | Functional for local operations, degraded for catalogue | Same as above |

---

## Version History and Diff

Git is a complete history of how a maker's craft evolves. The Shell exposes this as first-class:

- **Version timeline** — every primitive has a scrollable history
- **Side-by-side diff** — structured field-level comparison (not text diff)
- **Inventory version tracking** — shows if catalogue entry was updated since added
- **Project version context** — view referenced entries as they were at project creation time

Frontend components (part of `@makestack/ui`):
- `<VersionTimeline>`, `<DiffViewer>`, `<VersionBadge>`, `<VersionCompare>`

---

## Theme System

Themes are JSON files in `.makestack/themes/` in the data repo (served via Core):

- Theme JSON → CSS custom properties → Tailwind reads variables
- Default theme: "Cyberpunk" (dark, neon accents)
- Ships with 4 themes: Cyberpunk, Workshop, Daylight, High-Contrast

See **05-DESIGN-SYSTEM.md** for full details.

---

## Module System Details

### Meta Namespace Enforcement

Modules write to `meta` on catalogue primitives, scoped to their namespace:
- Module `inventory-stock` can write to `meta.inventory-stock`, read any namespace
- Shell proxy validates namespace before forwarding writes to Core
- Writing to another module's namespace → `403 Forbidden`

### Module Peer Awareness

1. `meta` namespaces (read across freely, write own only)
2. `peers.call()` — invoke peer module functions
3. No direct cross-module table access

### Module Migration Lifecycle

- Numbered sequential migrations per module, run at startup if pending
- Shell tracks applied migrations in `module_migrations` table
- Uninstall does NOT drop tables or data
- Table names prefixed with module name (e.g., `inventory_stock`)

---

## Code Standards

### Python (Backend)
- Python 3.12+ (use modern syntax: `str | None`, match statements, etc.)
- Type hints on all function signatures
- Async everywhere — FastAPI endpoints, httpx calls, aiosqlite queries
- Pydantic 2.x for all request/response models
- structlog for logging (structured, tagged by component/module)
- pytest + pytest-asyncio for tests
- Docstrings on all exported functions and classes
- Commits: Conventional Commits (`feat:`, `fix:`, `docs:`, etc.)

### TypeScript (Frontend)
- Strict mode enabled
- No `any` — use `unknown` + type guards
- TanStack Query for all server state (no useState for async data)
- TanStack Router for all navigation (no direct window.location)
- Tailwind only — no inline styles, no CSS modules
- Components are small and single-purpose

### General
- **API-first:** build the endpoint before the UI
- **Error messages:** always include `suggestion` field with actionable text
- **No silent failures:** log warnings, return structured errors

```python
# Good — async, typed, descriptive error
async def get_item(item_id: str, db: aiosqlite.Connection) -> InventoryItem:
    item = await db.execute_fetchone(
        "SELECT * FROM inventory_items WHERE id = ?", [item_id])
    if not item:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Inventory item not found",
                "item_id": item_id,
                "suggestion": "Use GET /api/inventory to list available items"
            }
        )
    ...

# Bad — sync, untyped, useless error
def get_item(id):
    print(f"getting {id}")
    item = db.get(id)
    if not item:
        raise HTTPException(404, "not found")
    ...
```

---

## Specification Documents

The full specs are in the makestack-docs repo. Key documents for Shell development:

- **01-ARCHITECTURE.md** — Two-system design, three-layer data model
- **02-DATA-MODEL.md** — Six primitives, schemas, relationships, workshops
- **03-JSON-KEYWORD-CONVENTION.md** — Keyword format, core keywords, module extension pattern
- **04-MODULE-INTERFACE.md** — Module config, keyword registration, lifecycle
- **05-DESIGN-SYSTEM.md** — Theme JSON structure, CSS variables, typography, component patterns, accessibility
- **06-TECH-STACK-DECISIONS.md** — Why Python+React, why Tailwind+Radix, why SQLite
- **08-REPOSITORY-STRUCTURE.md** — Multi-repo layout, docker-compose setup
- **10-SHELL-ARCHITECTURE.md** — Shell internals: proxy, UserDB, module loader, degraded mode, CLI, startup sequence
- **11-MODULE-DEVELOPER-GUIDE.md** — Module author contract: manifest spec, SDK surfaces, dependency rules, dev tooling

---

## Current State

Shell: **v0 Feature-Complete**

The Shell is fully implemented across all seven planned phases. All core systems are operational: the FastAPI backend, catalogue proxy with LRU cache and degraded mode, UserDB with migrations, inventory and workshop management, MCP server (SSE + stdio), React frontend with theme system and keyword renderer registry, module system with full SDK, registry and package manager, export/import, Docker orchestration, and production logging. The test suite covers 314 tests, all passing.

---

## Next Steps

_Post-v0 work to be defined._

---

## Decisions Made

- **Licensing: Shell is proprietary (All Rights Reserved).** Core (makestack-core) is MIT open-source. The Shell is private — not to be published, distributed, or used by others without explicit permission. This split is intentional: the catalogue engine is open, the application layer is not. Modules will have their own licensing (TBD per module).
- **Three extension types: Widgets, Modules, Registry.** These are fundamentally different things with different install flows, different capabilities, and different weights.
- **Widgets are stateless, frontend-only, no install infrastructure.** They are pure UI enhancement on data that is already meaningful without them. They degrade to raw text gracefully.
- **Modules are full-stack extensions** with backend routes, UserDB tables, and optional frontend. They are the heavy-weight extension mechanism.
- **Registry is Git-native, two-level.** Primary index → registries → packages. No npm/PyPI dependency. Any Git host works.
- **Four installable package types:** modules, widget-packs, catalogues, data. Each has its own install handler with different targets and restart requirements.
- **Widget packs do NOT require Shell restart** (frontend-only rebuild). Modules DO require restart.
- Shell is Python/FastAPI + React (not Go, not Next.js, not Electron)
- Backend dependency validation is STRICT; frontend is PERMISSIVE
- UserDB is SQLite via aiosqlite
- Module tables are typed with real columns (not key-value), FK to inventory
- Modules share data via `meta` namespaces and `peers.call()`
- Workshops are schema-free organizational containers
- Hash-pointer model: inventory references catalogue via Git commit hash
- User edits go directly to catalogue (Git via Core), not a draft layer
- Theme system: JSON config → CSS custom properties → Tailwind
- Default port: Shell on 3000, Core on 8420
- Single-user auth for v0 (multi-user deferred but schema supports it)
- Lexend primary font; JetBrains Mono for measurements/data
- **MCP server is a thin layer over the REST API — never bypasses it**
- **Every UI operation must have a REST endpoint (API-first, MCP-compatible)**
- **Module API endpoints auto-generate MCP tools from manifest declarations**
- **MCP supports SSE (remote) and stdio (local) transports**
- **`GET /api/capabilities` provides machine-readable self-description**
- **Error responses include actionable context for AI consumption**
- **Module tools use `{module_name}__{endpoint_name}` naming**

## Decisions Deferred

- Open-sourcing the Shell (currently proprietary; may open-source later)
- Multi-user authentication (JWT sessions — API key for v0)
- Module marketplace or discovery service
- Mobile-responsive layout (desktop-first for v0)
- Electron/Tauri desktop wrapper
- GitHub/remote catalogue federation
- MCP resource endpoints (exposing catalogue as MCP resources — tools-only for v0)
- MCP prompts (pre-built prompt templates for common maker workflows)
