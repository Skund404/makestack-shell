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
    │     Catalogue proxy ─── Core API (with LRU cache + degraded mode)
    │     UserDB (SQLite)     Inventory, workshops, settings, users
    │     Module system       Routes, migrations, SDK
    │     Package manager     Git-native registry
    │     MCP action log      Audit trail for AI operations
    │     Backup system       Automated + manual UserDB backups
    │
    ├── React frontend        Human UI
    └── MCP server            AI agent interface (SSE + stdio)
```

**Two clients, one API.** The React frontend and MCP server both hit the same FastAPI endpoints. There is no UI-only operation — if a human can do it, an AI agent can too.

---

## Features

- **Catalogue proxy** — full pass-through to Core with LRU cache and stale-while-revalidate degraded mode
- **Inventory** — personal relationship to catalogue entries via immutable Git commit hash-pointers with staleness detection
- **Workshops** — organizational containers with module associations, member management, and per-workshop navigation
- **User profiles** — name, avatar, bio, timezone, locale, activity stats
- **Version history and diffs** — every catalogue primitive has a full Git history with structured field-level diffs
- **Module system** — full-stack extensions (Python backend + React frontend) with migrations, SDK, auto-MCP exposure, and standalone app mode
- **Standalone app mode** — modules can declare `app_mode` to run as standalone apps with branded sidebars, launched from workshop home cards
- **Streamlined app install** — browse registries, preview dependencies, install + assign to a workshop in one click
- **Widget system** — stateless frontend-only keyword renderers; core widgets: `TIMER_`, `MEASUREMENT_`, `MATERIAL_REF_`, `TOOL_REF_`, `TECHNIQUE_REF_`, `IMAGE_`, `LINK_`, `NOTE_`, `CHECKLIST_`
- **Git-native package manager** — install modules, widget packs, catalogues, data packs, and skills from any Git host
- **MCP server** — 49+ tools across 11 groups; SSE, stdio, and static HTTP (key-authenticated) transports; transparent action audit logging
- **Fork primitives** — `fork_primitive` MCP tool and REST endpoint create an independent copy of any catalogue primitive with `cloned_from` provenance tracking
- **Binary file references** — git-backed pointer records for photos, videos, models, and documents without LFS; full CRUD via REST and MCP
- **Export/import** — portable JSON snapshots of personal state (workshops, inventory, preferences)
- **Backup system** — automated nightly UserDB backups with retention policy, manual backup/restore
- **Install safety** — transaction tracking with automatic rollback of partial installs
- **Terminal & logs** — live structured log streaming via SSE and WebSocket
- **Theme system** — JSON themes injected as CSS custom properties at runtime; ships with Cyberpunk, Workshop, Daylight, High-Contrast
- **Production-ready** — structured JSON logging, Docker support, Hetzner + Cloudflare Tunnel deployment

---

## Quick Start

### With Docker (recommended)

```bash
docker compose up
```

This starts Core and Shell together. Shell will be available at `http://localhost:3000`.

Set `MAKESTACK_API_KEY` to secure the API (defaults to `dev-key` for local use):

```bash
MAKESTACK_API_KEY=my-secret docker compose up
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
- API Documentation at `/dev/docs`

**With a local module under development:**

```bash
makestack dev --module ../my-module
```

---

## CLI

```bash
# Server
makestack start                        # Start Shell (production)
makestack dev                          # Start in dev mode
makestack dev --module ./path          # Dev mode + mount local module

# MCP
makestack mcp                          # Run MCP server (stdio transport)

# Packages
makestack install inventory-stock      # Install from registry
makestack install https://github.com/you/repo   # Direct Git URL
makestack install ./local-module       # Local path
makestack uninstall inventory-stock
makestack update inventory-stock
makestack search "leather"
makestack list                         # List installed packages

# Registry
makestack registry add official https://github.com/makestack/registry
makestack registry list
makestack registry remove community
makestack registry refresh             # Pull latest from all registries

# Modules
makestack module create my-module      # Scaffold a new module
makestack module validate ./path       # Validate a module manifest

# Data
makestack export --output backup.json
makestack import backup.json

# Maintenance
makestack rebuild-frontend             # Rebuild after widget pack install
makestack repair                       # Recover from interrupted installs
makestack backup                       # Manual UserDB backup
makestack restore /path/to/backup      # Restore from backup
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

**Streamable HTTP transport** (stable remote URL, key-authenticated):
```
https://makestack.yourdomain.com/mcp-http?key=your-secret-key
# or: Authorization: Bearer your-secret-key
```
Enabled by setting `MAKESTACK_MCP_API_KEY`. The endpoint is not mounted if the variable is unset.

### Available Tools (49+)

| Group | Tools |
|-------|-------|
| Catalogue | `search_catalogue`, `list_primitives`, `get_primitive`, `create_primitive`, `update_primitive`, `delete_primitive`, `get_relationships`, `fork_primitive` |
| Version | `get_primitive_history`, `compare_versions`, `get_primitive_at_version` |
| Inventory | `add_to_inventory`, `list_inventory`, `get_inventory_item`, `check_inventory_updates`, `update_inventory_pointer`, `remove_from_inventory` |
| Workshops | `list_workshops`, `get_workshop`, `create_workshop`, `update_workshop`, `delete_workshop`, `add_to_workshop`, `remove_from_workshop`, `set_active_workshop` |
| Settings | `get_settings`, `update_settings`, `get_theme`, `set_theme` |
| Modules | `list_modules`, `enable_module`, `disable_module`, `list_packages`, `install_package`, `uninstall_package`, `update_package`, `search_packages`, `list_registries`, `add_registry`, `remove_registry`, `refresh_registries` |
| Users | `get_user_profile`, `update_user_profile`, `get_user_stats` |
| Data | `export_data`, `import_data` |
| MCP Log | `list_mcp_actions`, `get_daily_summary` |
| System | `get_status`, `get_capabilities` |
| Binary Refs | `list_binary_refs`, `get_binary_ref`, `create_binary_ref`, `update_binary_ref`, `delete_binary_ref` |

Module API endpoints are automatically exposed as MCP tools when modules are installed — no extra code required.

**Static MCP endpoint:** Set `MAKESTACK_MCP_API_KEY` to enable a key-authenticated Streamable HTTP MCP endpoint at `/mcp-http`. Accepts the key via `?key=` query parameter or `Authorization: Bearer` header. Useful for remote MCP access at a stable URL: `https://makestack.yourdomain.com/mcp-http?key=your-secret`.

---

## Module System

Modules are full-stack extensions: Python backend + optional React frontend + UserDB migrations. Modules can run as standalone apps with their own branded sidebar, or as traditional views in the shell sidebar.

```
my-module/
├── makestack-package.json   # type: "module"
├── manifest.json            # Module contract (keywords, endpoints, tables, views, panels, app_mode)
├── backend/
│   ├── routes.py            # FastAPI router (mounted at /modules/my-module/)
│   ├── services.py
│   └── migrations/
├── frontend/
│   ├── index.ts             # registerMyModule() — views, panels, app mode
│   ├── components/
│   │   └── MySidebar.tsx    # Custom sidebar (optional, for app mode)
│   ├── views/
│   └── panels/
└── tests/
```

**Standalone app mode:** Modules can declare `app_mode` in their manifest to render in a full-screen layout with a branded sidebar. Workshop home shows launcher cards for these modules. The shell chrome (Sidebar, Header) is hidden; a back link returns to the workshop.

**Module SDK surfaces:**
- `CatalogueClient` — typed proxy to Core
- `ModuleUserDB` — scoped access to the module's own tables (enforced by regex)
- `ShellContext` — current user, active workshop, version, dev mode
- `ModuleConfig` — module config with manifest defaults + user overrides
- `PeerModules` — check peer availability and call peer module functions
- `get_logger(module_name)` — pre-tagged structlog logger
- Testing mocks: `MockCatalogueClient`, `MockUserDB`, `MockShellContext`, `MockPeerModules`, `create_test_app`

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
| `skill` | AI skill JSON definitions | No |

---

## Tech Stack

**Backend:** Python 3.10+, FastAPI, httpx, aiosqlite, Pydantic 2.x, structlog, MCP SDK, Click

**Frontend:** React 19, TypeScript (strict), Vite 7, TanStack Router v1, TanStack Query v5, Tailwind CSS v4, Radix UI, Lucide

**Fonts:** Lexend (primary, dyslexia-friendly), JetBrains Mono (data/measurements)

**Infra:** Docker, docker-compose, Hetzner CX21, Cloudflare Tunnel

---

## API Reference

All endpoints return typed JSON. List endpoints include pagination metadata (`total`, `limit`, `offset`). Error responses include an actionable `suggestion` field.

| Group | Base path |
|-------|-----------|
| Catalogue (proxy to Core) | `/api/catalogue/` |
| Inventory | `/api/inventory/` |
| Workshops | `/api/workshops/` |
| Users | `/api/users/` |
| Settings | `/api/settings/` |
| Modules | `/api/modules/` |
| Packages & Registries | `/api/packages/`, `/api/registries/` |
| Binary File References | `/api/binary-refs/` |
| Data (export/import) | `/api/data/` |
| Backups | `/api/backups/` |
| Terminal & Logs | `/api/terminal/` |
| MCP Action Log | `/api/mcp-log/` |
| Version | `/api/version/` |
| System | `/api/status`, `/api/capabilities` |
| Dev (dev mode only) | `/api/dev/` |

Full self-description available at `GET /api/capabilities`.

---

## Running Tests

```bash
python3 -m pytest backend/tests/ -x -q
```

489 tests across 24 files covering: Core client + cache, UserDB + migrations, all REST routes, module manifest validation, module SDK, module loader, package management, registry client, package cache, installers, MCP server, MCP logging, terminal/logs, backups, workshop modules, install transaction rollback, and end-to-end integration.

---

## Configuration

| Environment variable | Default | Description |
|---------------------|---------|-------------|
| `MAKESTACK_CORE_URL` | `http://localhost:8420` | Core API base URL |
| `MAKESTACK_CORE_API_KEY` | *(none)* | API key for Core auth |
| `MAKESTACK_USERDB_PATH` | `~/.makestack/userdb.sqlite` | Personal database path |
| `MAKESTACK_DEV_MODE` | `false` | Enable debug API and dev UI |
| `MAKESTACK_PORT` | `3000` | Shell listen port |
| `MAKESTACK_HOME` | `~/.makestack` | Base config directory |
| `MAKESTACK_API_KEY` | *(none)* | Shell API key (for auth) |
| `MAKESTACK_SHELL_URL` | `http://localhost:3000` | MCP server target (stdio mode) |
| `MAKESTACK_SHELL_TOKEN` | *(none)* | MCP server auth token |
| `MAKESTACK_MCP_ALLOWED_HOSTS` | *(none)* | Reverse-proxy domains for MCP |
| `MAKESTACK_MCP_API_KEY` | *(none)* | Enables `/mcp-http` Streamable HTTP endpoint when set; required in `?key=` or `Authorization: Bearer` |

---

## Deployment

### Hetzner + Cloudflare Tunnel

See [HETZNER.md](HETZNER.md) for the full production deployment guide covering server provisioning, Cloudflare Tunnel setup, and Claude MCP configuration with service token auth.

```bash
docker compose -f docker-compose.hetzner.yml up -d --build
```

---

## License

Proprietary. All Rights Reserved.

The catalogue engine ([makestack-core](https://github.com/makestack/makestack-core)) is MIT-licensed. This shell application is not open-source. Do not distribute, publish, or use without explicit permission.
