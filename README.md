# Makestack Shell

The host application for [Makestack](https://github.com/Skund404/makestack-shell) — a modular project management and ERP toolkit for makers (leatherworkers, cosplayers, woodworkers, 3D printers, cooks, and more).

This repo is the **Shell**: the application layer that sits between the user and everything else. It proxies all access to `makestack-core` (the catalogue engine), owns the local personal database, hosts modules, and exposes both a React UI and an MCP server so AI agents can fully operate the system.

---

## Architecture

Makestack is split across two repos:

- **[makestack-core](https://github.com/makestack/makestack-core)** (Go, separate repo) — the headless catalogue engine. Manages JSON files in Git, maintains a SQLite read index, serves data via REST. Already feature-complete. Default port: `8420`.
- **makestack-shell** (this repo) — the application host. React frontend + Python/FastAPI backend. Owns all personal state (UserDB), module system, auth, and the MCP server.

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
    │     UserDB (SQLite)     Inventory, workshops, settings
    │     Module system       Routes, migrations, SDK
    │     Package manager     Git-native registry
    │
    ├── React frontend        Human UI
    └── MCP server            AI agent interface (SSE + stdio)
```

**Two clients, one API.** The React frontend and MCP server both hit the same FastAPI endpoints. There is no UI-only operation — if a human can do it, an AI agent can too.

---

## Features

- **Catalogue proxy** — full pass-through to Core with degraded-mode LRU cache (stale-while-revalidate when Core is down)
- **Inventory** — personal relationship to catalogue entries via immutable Git commit hash-pointers
- **Workshops** — schema-free organizational containers (by project, client, domain, or time)
- **Version history and diffs** — every catalogue primitive has a full Git history with structured field-level diffs
- **Module system** — full-stack extensions (Python backend + React frontend) with migrations, SDK, and auto-MCP exposure
- **Widget system** — stateless frontend-only keyword renderers; core widgets: `TIMER_`, `MEASUREMENT_`, `MATERIAL_REF_`, `TOOL_REF_`, `TECHNIQUE_REF_`, `IMAGE_`, `LINK_`, `NOTE_`, `CHECKLIST_`
- **Git-native package manager** — install modules, widget packs, catalogues, and data packs from any Git host
- **MCP server** — 32+ tools across catalogue, inventory, workshops, version, settings, modules, packages, and system; SSE and stdio transports
- **Export/import** — portable JSON snapshots of personal state (workshops, inventory, preferences)
- **Theme system** — JSON themes injected as CSS custom properties at runtime; ships with Cyberpunk, Workshop, Daylight, High-Contrast
- **Production-ready** — structured JSON logging, rotating log files, request middleware with slow-request warnings, Docker support

---

## Quick Start

### With Docker (recommended)

```bash
docker-compose up
```

This starts Core and Shell together. Shell will be available at `http://localhost:3000`.

Set `MAKESTACK_API_KEY` to secure the API (defaults to `dev-key` for local use):

```bash
MAKESTACK_API_KEY=my-secret docker-compose up
```

### Development

**Prerequisites:** Python 3.10+, Node.js 20+

```bash
# 1. Install Python dependencies
pip install -e ".[dev]"

# 2. Install frontend dependencies
cd frontend && npm install && cd ..

# 3. Start in dev mode (hot-reload backend + frontend proxy)
makestack dev
```

Dev mode enables:
- Debug API at `/api/dev/*`
- Keyword Playground at `http://localhost:5173/dev/keywords`
- Schema Inspector at `/dev/schema`
- Module Inspector at `/dev/modules`

**With a local module under development:**

```bash
makestack dev --module ../my-module
```

---

## CLI

```bash
makestack start                     # Start Shell (production)
makestack dev                       # Start in dev mode
makestack dev --module ./path       # Dev mode + mount local module

makestack mcp                       # Run MCP server (stdio transport)

makestack install inventory-stock   # Install a package from registry
makestack install @1.2.0            # Pin to version
makestack install https://github.com/you/repo   # Direct Git URL
makestack uninstall inventory-stock
makestack update inventory-stock
makestack search "leather"

makestack registry add https://github.com/someone/their-registry
makestack registry list
makestack registry remove community-leather

makestack module create my-module   # Scaffold a new module
makestack module validate ./path    # Validate a module manifest

makestack export --output backup.json
makestack import backup.json

makestack rebuild-frontend          # Rebuild after installing widget packs
```

---

## MCP Server

Makestack exposes an MCP server so AI agents (Claude, etc.) can fully operate the system.

**SSE transport** (remote/network):
```
http://localhost:3000/mcp/sse
```

**stdio transport** (local, for Claude Code):
```bash
makestack mcp
```

### Available Tools

| Group | Tools |
|-------|-------|
| Catalogue | `search_catalogue`, `list_primitives`, `get_primitive`, `create_primitive`, `update_primitive`, `delete_primitive`, `get_relationships` |
| Version | `get_primitive_history`, `compare_versions`, `get_primitive_at_version` |
| Inventory | `add_to_inventory`, `list_inventory`, `get_inventory_item`, `check_inventory_updates`, `update_inventory_pointer`, `remove_from_inventory` |
| Workshops | `list_workshops`, `get_workshop`, `create_workshop`, `update_workshop`, `delete_workshop`, `add_to_workshop`, `remove_from_workshop`, `set_active_workshop` |
| Settings | `get_settings`, `update_settings`, `get_theme`, `set_theme` |
| Modules | `list_modules`, `enable_module`, `disable_module`, `call_module`, `list_packages`, `install_package`, `uninstall_package`, `search_packages`, `list_registries` |
| Data | `export_data`, `import_data` |
| System | `get_status`, `get_capabilities` |

Module API endpoints are automatically exposed as MCP tools when modules are installed — no extra code required.

---

## Module System

Modules are full-stack extensions: Python backend + optional React frontend + UserDB migrations.

```
my-module/
├── makestack-package.json   # type: "module"
├── manifest.json            # Module contract (keywords, endpoints, tables)
├── backend/
│   ├── routes.py            # FastAPI router (mounted at /modules/my-module/)
│   ├── services.py
│   └── migrations/
├── frontend/
│   ├── components/
│   └── keywords.ts          # Keyword renderer registrations
└── tests/
```

**Module SDK surfaces:**
- `CatalogueClient` — typed proxy to Core
- `UserDB` — scoped access to the module's own tables
- `ShellContext` — current user, active workshop, version, dev mode
- `ModuleConfig` — module config from `.makestack/modules/{name}.config.json`
- `PeerModules` — check peer availability and call peer module functions
- `get_logger(module_name)` — pre-tagged structlog logger

**Install a module:**
```bash
makestack install my-module
# or directly:
makestack install https://github.com/you/makestack-module-my-module
```

**Scaffold a new module:**
```bash
makestack module create my-module
cd my-module
makestack dev --module .
```

---

## Package Types

| Type | What it is | Restart? |
|------|-----------|----------|
| `module` | Full-stack extension (backend + frontend + DB) | Yes |
| `widget-pack` | Frontend-only keyword renderer bundle | No |
| `catalogue` | Primitive data to merge into Core | No |
| `data` | Themes, presets, or other static files | No |

---

## Tech Stack

**Backend:** Python 3.10+, FastAPI, httpx, aiosqlite, Pydantic 2.x, structlog, MCP SDK

**Frontend:** React 18, TypeScript (strict), Vite, TanStack Router, TanStack Query, Tailwind CSS v4, Radix UI, Lucide, Recharts

**Fonts:** Lexend (primary, dyslexia-friendly), JetBrains Mono (data/measurements)

---

## API Reference

All endpoints return typed JSON. List endpoints include pagination metadata (`total`, `limit`, `offset`). Error responses include an actionable `suggestion` field.

| Group | Base path |
|-------|-----------|
| Catalogue (proxy to Core) | `/api/catalogue/` |
| Inventory | `/api/inventory/` |
| Workshops | `/api/workshops/` |
| Modules | `/api/modules/` |
| Packages | `/api/packages/` |
| Registries | `/api/registries/` |
| Settings | `/api/settings/` |
| Data (export/import) | `/api/data/` |
| System | `/api/status`, `/api/capabilities` |
| Dev (dev mode only) | `/api/dev/` |

Full self-description available at `GET /api/capabilities`.

---

## Running Tests

```bash
python3 -m pytest backend/tests/ -x -q
```

314 tests covering: Core client, UserDB migrations, all REST routes, module manifest validation, module SDK, module loader, package management, registry client, package cache, installers, and end-to-end integration (including degraded mode and export/import).

---

## Configuration

| Environment variable | Default | Description |
|---------------------|---------|-------------|
| `MAKESTACK_CORE_URL` | `http://localhost:8420` | Core API base URL |
| `MAKESTACK_CORE_API_KEY` | *(none)* | API key for Core auth |
| `MAKESTACK_USERDB_PATH` | `~/.makestack/userdb.sqlite` | Personal database path |
| `MAKESTACK_DEV_MODE` | `false` | Enable debug API and dev UI |
| `MAKESTACK_API_KEY` | *(none)* | Shell API key (for auth) |

---

## License

Proprietary. All Rights Reserved.

The catalogue engine ([makestack-core](https://github.com/makestack/makestack-core)) is MIT-licensed. This shell application is not open-source. Do not distribute, publish, or use without explicit permission.
