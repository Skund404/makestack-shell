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

Makestack is built for makers who use AI as a collaborator. An AI agent connected via MCP should be able to do everything a human can through the UI:

- Browse and search the catalogue
- Create, update, and delete primitives (techniques, materials, tools, etc.)
- Manage inventory (add items, adjust stock, check version history)
- Organize workshops (create, assign primitives, switch context)
- Use modules (invoke module APIs, read module data)
- View version history and diffs
- Manage settings and preferences
- Install, enable, and disable modules

This isn't a "nice-to-have" — it's an architectural constraint that ensures the REST API is complete. If a human can do it through the UI, there must be an API endpoint for it, and therefore an MCP tool for it.

### Architecture: Thin MCP Layer Over REST

```
AI Agent (Claude, etc.)
    │
    │ MCP protocol (SSE or stdio)
    │
    ▼
MCP Server (Python, in this repo)
    │
    │ Internal HTTP calls to localhost
    │
    ▼
FastAPI Backend (same process or same host)
    │
    │ (same code path as React frontend)
    │
    ▼
Core / UserDB / Modules
```

The MCP server is a **thin translation layer**. It:
- Describes available operations as MCP tools with typed input schemas
- Translates MCP tool calls into Shell REST API requests
- Returns structured JSON responses the AI can reason about
- Handles auth (same token/key mechanism as the REST API)

The MCP server does NOT:
- Access UserDB directly
- Talk to Core directly
- Contain business logic
- Duplicate any endpoint logic

### MCP Server Implementation

The MCP server lives in this repo and uses the Python `mcp` SDK:

```python
# mcp_server/server.py — simplified

from mcp.server import Server
from mcp.types import Tool, TextContent
import httpx

server = Server("makestack")
api = httpx.AsyncClient(base_url="http://localhost:3000")

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="search_catalogue",
            description="Search the catalogue for techniques, materials, tools, workflows, projects, or events",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms"},
                    "type_filter": {
                        "type": "string",
                        "enum": ["tool", "material", "technique", "workflow", "project", "event"],
                        "description": "Optional: filter by primitive type"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="create_technique",
            description="Create a new technique in the catalogue",
            inputSchema={...}
        ),
        # ... tools for every Shell operation
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    match name:
        case "search_catalogue":
            resp = await api.get("/api/catalogue/search", params={"q": arguments["query"]})
            return [TextContent(type="text", text=resp.text)]
        case "create_technique":
            resp = await api.post("/api/catalogue/primitives", json={
                "type": "technique", **arguments
            })
            return [TextContent(type="text", text=resp.text)]
```

### MCP Tool Categories

The MCP server exposes tools in these groups:

**Catalogue (proxied to Core via Shell)**
- `search_catalogue` — full-text search across all primitives
- `list_primitives` — list by type, browse the catalogue
- `get_primitive` — read a single primitive (current or at a specific version)
- `create_primitive` — create a new technique/material/tool/workflow/project/event
- `update_primitive` — modify an existing primitive
- `delete_primitive` — remove a primitive
- `get_relationships` — show what connects to what

**Version History**
- `get_primitive_history` — list all versions of a primitive
- `compare_versions` — structured diff between two versions of a primitive
- `get_primitive_at_version` — read a primitive as it was at a past commit

**Inventory**
- `add_to_inventory` — add a catalogue item to personal inventory (creates hash-pointer)
- `list_inventory` — browse inventory items (optionally filtered by workshop)
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

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (always public, even with auth enabled) |
| GET | `/api/primitives[?type=]` | List all primitives, optionally filtered by type |
| GET | `/api/primitives/{path}` | Get a single primitive from the SQLite index (current version) |
| GET | `/api/primitives/{path}?at={hash}` | Get primitive at a specific Git commit (reads from Git, bypasses index) |
| GET | `/api/primitives/{path}/hash` | Get the last commit hash that touched this specific path |
| GET | `/api/primitives/{path}/history[?limit=50&offset=0]` | Paginated commit history (limit max 200) |
| GET | `/api/primitives/{path}/diff[?from=&to=]` | Structured field-level JSON diff between two versions |
| GET | `/api/search?q=` | Full-text search across name, description, tags, properties (FTS5) |
| GET | `/api/relationships/{path}` | Bidirectional relationship lookup (source and target matches) |
| POST | `/api/primitives` | Create primitive (auto-generates id, slug, created, modified) |
| PUT | `/api/primitives/{path}` | Update primitive (requires id, type, name, slug in body; auto-stamps modified) |
| DELETE | `/api/primitives/{path}` | Delete primitive and its parent directory |

### Critical Implementation Details

**Path format:** Primitive paths always look like `{type}s/{slug}/manifest.json` (e.g., `tools/stitching-chisel/manifest.json`). The trailing `manifest.json` is part of the path.

**`/hash` is path-specific, NOT repo HEAD.** It returns the hash of the most recent commit that touched this specific file via `LastCommitHashForPath`. This is critical — two primitives will have different hashes even if they're in the same repo. The Shell stores this hash when creating inventory records.

**`?at={hash}` reads from Git, not SQLite.** The index only holds current state. Historical reads go directly to the Git object store. Returns 503 if Core's data directory is not a git repo.

**`/history` pagination:** `limit` defaults to 50, max 200. `offset` defaults to 0. Response shape: `{"path": "...", "total": N, "commits": [{"hash": "...", "message": "...", "author": "...", "timestamp": "..."}]}`. Returns empty list (not 404) for unknown paths.

**`/diff` defaults:** If `to` is omitted, defaults to HEAD. If `from` is omitted, defaults to the parent of `to`. Returns 400 if the target commit has no parent (initial commit). Response includes `from_hash`, `to_hash`, `from_timestamp`, `to_timestamp`, and `changes` array with `{field, type, old_value, new_value}` per change. Change types: `added`, `removed`, `modified`. Fields use dot notation for nested objects (`properties.tension`) and bracket notation for arrays (`steps[3]`).

**Write endpoints return 503** if Core's data directory is not a valid git repo. Writes go to disk + git commit; the file watcher picks up the change and updates the SQLite index async (~200ms debounce).

**POST response:** Returns 201 with the full manifest. The `id`, `slug`, `created`, and `modified` fields are auto-generated if not provided.

**PUT requires all identity fields:** `id`, `type`, `name`, `slug` must be in the body. `modified` is auto-stamped.

**Validation:** POST and PUT validate the body structure before writing. Invalid input returns 400 with all validation errors collected (not fail-fast). Checks: `description` must be string, `tags` must be array of strings, `relationships` must be array of `{type, target}` objects, `steps` (technique/workflow) must be array, `parent_project` (project) must be string.

**Search:** FTS5 across `name`, `description`, `tags`, `properties`. Returns matching primitives ordered by name. Missing `q` param returns 400.

### Core Response Shapes

Primitive response (from GET, POST, PUT):
```json
{
  "id": "tool-stitching-chisel-001",
  "type": "tool",
  "name": "Stitching Chisel (4-prong)",
  "slug": "stitching-chisel",
  "path": "tools/stitching-chisel/manifest.json",
  "created": "2026-02-28T00:00:00Z",
  "modified": "2026-02-28T00:00:00Z",
  "description": "A 4-prong stitching chisel...",
  "tags": ["leather", "stitching"],
  "properties": {"prongs": 4, "spacing_mm": 4},
  "parent_project": "",
  "manifest": { ... full original JSON ... },
  "commit_hash": ""
}
```

The `commit_hash` field is only populated when using `?at={hash}`. The `manifest` field contains the complete original JSON — the other fields are extracted copies for indexing/filtering.

Relationship response:
```json
{
  "source_path": "techniques/saddle-stitching/manifest.json",
  "source_type": "technique",
  "relationship_type": "uses_tool",
  "target_path": "tools/stitching-chisel/manifest.json",
  "target_type": "",
  "metadata": null
}
```

Error response:
```json
{"error": "not found: tools/nonexistent/manifest.json"}
```

---

## Shell API Reference (What the Frontend and MCP Server Consume)

The Shell's FastAPI backend is the single source of truth for all operations. Both the React frontend and MCP server call these endpoints.

### Catalogue (proxy to Core)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/catalogue/primitives` | List/filter primitives |
| GET | `/api/catalogue/primitives/{path}` | Get primitive (current or `?at={hash}`) |
| GET | `/api/catalogue/primitives/{path}/hash` | Get commit hash for primitive |
| GET | `/api/catalogue/primitives/{path}/history` | Version history |
| GET | `/api/catalogue/primitives/{path}/diff` | Version diff |
| GET | `/api/catalogue/search?q=` | Full-text search |
| GET | `/api/catalogue/relationships/{path}` | Relationship lookup |
| POST | `/api/catalogue/primitives` | Create primitive |
| PUT | `/api/catalogue/primitives/{path}` | Update primitive |
| DELETE | `/api/catalogue/primitives/{path}` | Delete primitive |

### Inventory
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/inventory` | List inventory items (`?workshop_id=`, `?type=`) |
| GET | `/api/inventory/{id}` | Get inventory item with resolved catalogue data |
| POST | `/api/inventory` | Add catalogue item to inventory (creates hash-pointer) |
| PUT | `/api/inventory/{id}` | Update inventory item (workshop, update hash-pointer) |
| DELETE | `/api/inventory/{id}` | Remove from inventory |
| GET | `/api/inventory/stale` | List items where catalogue has been updated |

### Workshops
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/workshops` | List workshops |
| GET | `/api/workshops/{id}` | Get workshop with member list |
| POST | `/api/workshops` | Create workshop |
| PUT | `/api/workshops/{id}` | Update workshop |
| DELETE | `/api/workshops/{id}` | Delete workshop |
| POST | `/api/workshops/{id}/members` | Add primitive to workshop |
| DELETE | `/api/workshops/{id}/members/{path}` | Remove primitive from workshop |
| PUT | `/api/workshops/active` | Set active workshop context |

### Settings
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/settings` | Get all settings (preferences + config) |
| PUT | `/api/settings/preferences` | Update user preferences |
| GET | `/api/settings/theme` | Get active theme |
| PUT | `/api/settings/theme` | Switch theme |

### Modules
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/modules` | List installed modules with status |
| PUT | `/api/modules/{name}/enable` | Enable a module |
| PUT | `/api/modules/{name}/disable` | Disable a module |
| GET | `/modules/{name}/*` | Module-specific routes (mounted per module) |

### Widgets
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/widgets` | List all registered keyword renderers (core + packs + modules) |
| GET | `/api/widgets/packs` | List installed widget packs |

### Packages (Registry)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/packages` | List all installed packages (modules, widget packs, catalogues) |
| POST | `/api/packages/install` | Install a package by name or Git URL |
| DELETE | `/api/packages/{name}` | Uninstall a package |
| POST | `/api/packages/{name}/update` | Update a package to latest version |
| GET | `/api/packages/search?q=` | Search across all registries |
| GET | `/api/registries` | List configured registries |
| POST | `/api/registries` | Add a registry |
| DELETE | `/api/registries/{name}` | Remove a registry |

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
| GET | `/api/dev/catalogue-proxy` | Recent Core API calls |
| GET | `/api/dev/userdb/tables` | UserDB table info |
| GET | `/api/dev/userdb/query?sql=` | Read-only SQL (dev only) |
| GET | `/api/dev/config` | Resolved config |
| POST | `/api/dev/validate-module` | Validate module manifest |
| GET | `/api/dev/health` | Full system health |

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

The Shell owns a local SQLite database (`~/.makestack/userdb.sqlite`) for all personal state:

```sql
-- User identity and preferences
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    avatar_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE user_preferences (
    user_id TEXT NOT NULL REFERENCES users(id),
    key TEXT NOT NULL,
    value TEXT NOT NULL,  -- JSON-encoded
    PRIMARY KEY (user_id, key)
);

-- Workshops: user-defined organizational containers (no semantic opinion)
CREATE TABLE workshops (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    description TEXT,
    icon TEXT,
    color TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Workshop membership: which catalogue primitives belong to which workshop
CREATE TABLE workshop_members (
    workshop_id TEXT NOT NULL REFERENCES workshops(id) ON DELETE CASCADE,
    primitive_path TEXT NOT NULL,
    primitive_type TEXT NOT NULL,
    added_at TEXT NOT NULL,
    PRIMARY KEY (workshop_id, primitive_path)
);

-- Inventory: personal relationship to catalogue entries via hash-pointers
CREATE TABLE inventory (
    id TEXT PRIMARY KEY,
    catalogue_path TEXT NOT NULL,
    catalogue_hash TEXT NOT NULL,       -- Git commit hash at time of addition
    primitive_type TEXT NOT NULL,
    workshop_id TEXT REFERENCES workshops(id),
    added_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Module-specific inventory data lives in module-owned typed tables.
-- Each module declares its own tables with real columns,
-- foreign-keying back to the inventory table as needed.

-- Module registration and state
CREATE TABLE installed_modules (
    name TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    installed_at TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_migration TEXT
);

-- Migration tracking per module
CREATE TABLE module_migrations (
    module_name TEXT NOT NULL REFERENCES installed_modules(name),
    migration_id TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    PRIMARY KEY (module_name, migration_id)
);
```

### Hash-Pointer Model (Critical Design)

Inventory records reference catalogue entries via **immutable Git commit hashes**:

```
Inventory Record          Catalogue Entry (Core/Git)
┌───────────────────┐     ┌─────────────────────────────┐
│ catalogue_path ────┼────▶│ materials/wickett-craig-5oz  │
│ catalogue_hash ────┼──┐  │                             │
└───────────────────┘  │  └─────────────────────────────┘
                       │
                       └──▶ exact version at this commit
                            (immutable — never changes)
```

- Inventory NEVER duplicates catalogue data. It stores a path and a commit hash.
- A project from 2024 references the exact version of a technique that existed in 2024.
- When the catalogue entry is updated (new commit), existing inventory pointers remain valid.
- Shell detects staleness: `current_hash != inventory_hash` → "update available".
- User can view diff, update pointer, or keep old reference.
- Module-specific personal data (quantity, location, price) lives in module-owned typed tables that foreign-key to `inventory.id`.

### Workshops

Schema-free organizational containers. The Shell provides mechanism; the user decides meaning:
- Domain scope: "Leatherwork"
- Time scope: "2024 Projects"
- Project scope: "Messenger Bag Build"
- Client scope: "Client: Studio ABC"

Primitives are global. Workshops reference them. A primitive can belong to multiple workshops. Removing from workshop ≠ deleting. Search is always global.

---

## Code Structure (This Repo)

```
makestack-app/
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI entry point + startup sequence
│   │   ├── core_client.py            # Catalogue proxy (httpx client to Core)
│   │   ├── userdb.py                 # UserDB connection + migration runner
│   │   ├── module_loader.py          # Module discovery, validation, loading
│   │   ├── module_config.py          # Module config reader (.makestack/modules/)
│   │   ├── dependencies.py           # FastAPI DI providers
│   │   ├── models.py                 # Shared Pydantic models
│   │   ├── routers/
│   │   │   ├── catalogue.py          # Proxy routes to Core
│   │   │   ├── inventory.py          # Inventory CRUD (hash-pointer management)
│   │   │   ├── workshops.py          # Workshop CRUD + membership
│   │   │   ├── settings.py           # User preferences + config
│   │   │   ├── version.py            # History, diff, version browsing
│   │   │   ├── modules.py            # Module management (list, enable, disable)
│   │   │   ├── system.py             # Status, capabilities
│   │   │   └── dev.py                # Debug API (dev mode only)
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
│   │   ├── catalogue.py              # Catalogue tool definitions
│   │   ├── inventory.py              # Inventory tool definitions
│   │   ├── workshops.py              # Workshop tool definitions
│   │   ├── modules.py                # Module tool definitions (+ dynamic module tools)
│   │   ├── version.py                # Version history tool definitions
│   │   ├── settings.py               # Settings tool definitions
│   │   └── system.py                 # System/status tool definitions
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
│   │   └── mcp.py                    # makestack mcp (stdio transport)
│   └── ...
├── docker-compose.yml
├── Dockerfile
├── CLAUDE.md                         # This file
├── LICENSE                           # Proprietary (All Rights Reserved)
├── README.md
└── CONTRIBUTING.md
```

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
- Branch: GitHub Flow (main + feature branches)

### TypeScript (Frontend)
- Strict TypeScript (no `any` unless absolutely necessary)
- Functional components with hooks
- TanStack Query for all data fetching (never raw `fetch` in components)
- Tailwind CSS only — no inline styles, no CSS modules, no styled-components
- Radix UI primitives wrapped in `@makestack/ui` — never import Radix directly in pages
- Lucide for all icons
- Components export named exports (not default) except route components

### API Design (MCP-Critical)
- Every user-facing operation must have a REST endpoint — no UI-only actions
- All endpoints return Pydantic-typed JSON with consistent envelope: `{"data": ..., "meta": {...}}`
- Error responses include actionable context: what failed, why, and what to try
- List endpoints always include pagination metadata: `total`, `limit`, `offset`
- Endpoints are idempotent where possible
- `GET /api/capabilities` provides machine-readable self-description for MCP tool generation

### Shared
- No `console.log` in committed code (use structured logger or TanStack Query devtools)
- Error handling: all async operations must have error handling
- Every user-facing feature should work without any modules installed

```python
# Good — async, typed, descriptive error for AI consumption
async def get_inventory_item(
    item_id: str,
    db: UserDB = Depends(get_userdb),
    catalogue: CatalogueClient = Depends(get_catalogue_client),
) -> InventoryItemResponse:
    """Retrieve an inventory item with its resolved catalogue data."""
    item = await db.fetch_one("SELECT * FROM inventory WHERE id = ?", [item_id])
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

**Two-level architecture:**

```
┌──────────────────────────────────────┐
│  PRIMARY INDEX                       │
│  (Single Git repo, maintained by     │
│   project maintainer)                │
│                                      │
│  Lists every known registry:         │
│  - Official registry                 │
│  - Community registries              │
│  - Domain-specific registries        │
│  - Third-party registries            │
│                                      │
│  This is the discovery layer.        │
│  A developer publishes a package,    │
│  submits a PR to the primary index,  │
│  and every Makestack user can find it│
└──────────────────┬───────────────────┘
                   │
        ┌──────────▼──────────┐
        │  REGISTRIES         │
        │  (Git repos, each   │
        │   maintained by     │
        │   their owner)      │
        │                     │
        │  Maps package names │
        │  to Git URLs and    │
        │  version tags       │
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────┐
        │  PACKAGES           │
        │  (Git repos)        │
        │                     │
        │  Four types:        │
        │  - Modules          │
        │  - Widget packs     │
        │  - Catalogues       │
        │  - Data             │
        └─────────────────────┘
```

**Primary index** (index of registries):
```json
{
  "registries": {
    "official": {
      "git": "https://github.com/makestack/registry",
      "description": "Official Makestack packages"
    },
    "community-leather": {
      "git": "https://github.com/leather-community/makestack-registry",
      "description": "Community leatherwork packages"
    }
  }
}
```

**Registry** (index of packages):
```json
{
  "packages": {
    "inventory-stock": {
      "git": "https://github.com/makestack/makestack-module-inventory",
      "type": "module"
    },
    "timer-widgets": {
      "git": "https://github.com/makestack/makestack-widgets-timer",
      "type": "widget-pack"
    },
    "leatherwork-catalogue": {
      "git": "https://github.com/makestack/makestack-catalogue-leatherwork",
      "type": "catalogue"
    }
  }
}
```

**Package manifest** (`makestack-package.json`, in the package repo):
```json
{
  "name": "inventory-stock",
  "type": "module",
  "version": "1.0.0",
  "description": "Track material quantities, locations, and stock status",
  "shell_compatibility": ">=0.1.0"
}
```

The `type` in the registry is a hint for discovery. The `makestack-package.json` in the repo is authoritative.

**Four installable types, four install handlers:**

| Type | Install target | What happens | Restart? |
|------|---------------|-------------|----------|
| `module` | Shell Python env + UserDB + frontend | Dependency check → pip install → migrations → mount routes → rebuild frontend | Yes |
| `widget-pack` | Frontend build only | Copy components → rebuild frontend | No (hot-reload in dev) |
| `catalogue` | Core's data repo via Core API | POST each primitive to Core (or git merge). User chooses: merge all, cherry-pick, or preview | No |
| `data` | Configurable target | Themes → `.makestack/themes/`. Presets → `.makestack/`. Generic → user-specified | No |

**Versioning:** Git tags (`v1.0.0`, `v1.1.0`). Shell resolves `latest` to highest semver tag. Pinning: `makestack install inventory-stock@1.2.0`. Package cache stores the cloned repo; switching versions is `git checkout`.

**CLI:**
```bash
makestack install inventory-stock              # Resolve via registry, install
makestack install inventory-stock@1.2.0        # Pin to version
makestack install https://github.com/you/repo  # Direct Git URL (bypass registry)
makestack install ./local-path                 # Local path (dev)
makestack uninstall inventory-stock
makestack update inventory-stock
makestack search "leather"                     # Search across all registries
makestack registry add https://github.com/someone/their-registry
makestack registry list
makestack registry remove community-leather
```

**Key principle:** Any Git host works — GitHub, GitLab, Codeberg, self-hosted Gitea. No vendor lock-in. The registry is just a JSON file in a Git repo.

### Module SDK (5 Surfaces)

Available only to modules (not widgets):

1. **CatalogueClient** — typed proxy to Core (read, search, write, history, diff)
2. **UserDB** — scoped access to module's own tables only
3. **Frontend registration** — keyword renderers, panels, sidebar entries (build time)
4. **API mounting** — FastAPI router at `/modules/{name}/` with auth wrapping
5. **Context injection** — current user, active workshop, module config as FastAPI dependencies

### Module API → MCP Tool Mapping

Module manifests declare `api_endpoints` with method, path, description, and parameter schemas. At startup, the MCP tool generator reads these and creates MCP tool definitions automatically. Module authors don't write MCP code — they write FastAPI endpoints and declare them in their manifest.

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

## Current State

Shell: **Phase 5 Module System Complete**

- [x] Python project initialized (pyproject.toml, requirements.txt)
- [x] FastAPI entry point with startup sequence
- [x] CatalogueClient (httpx proxy to Core)
- [x] UserDB schema and migration runner
- [x] Catalogue proxy routes
- [x] Inventory routes (CRUD with hash-pointer management)
- [x] Workshop routes (CRUD + membership)
- [x] Version/history routes
- [x] Settings routes (+ GET /api/settings/theme/data returning CSS variable map)
- [x] System routes (status, capabilities)
- [x] Degraded mode (Core health-check polling; routes return 503 when Core is down)
- [x] Dev mode debug API
- [x] MCP server (tool definitions, SSE + stdio transports)
- [x] MCP module tool auto-generation (placeholder — wired in Phase 5)
- [x] React frontend initialized (Vite + React 18 + TanStack Router + TanStack Query + Tailwind v4)
- [x] Theme loader (fetches /api/settings/theme/data, injects CSS custom properties; 4 built-in themes)
- [x] Layout (sidebar, header, navigation)
- [x] `@makestack/ui` component library (Badge, Button, Card, Dialog, DropdownMenu, Input, ScrollArea, Select, Separator, Tabs, Tooltip, Textarea)
- [x] Catalogue browsing views (list with type tabs, pagination)
- [x] Primitive detail view (properties, steps, relationships, version history inline)
- [x] Primitive create/edit views
- [x] Keyword renderer registry (resolution chain: module → pack → core → raw text)
- [x] Core widget implementations (TIMER_, MEASUREMENT_, MATERIAL_REF_, TOOL_REF_, TECHNIQUE_REF_, IMAGE_, LINK_, NOTE_, CHECKLIST_)
- [x] Version timeline and diff viewer (VersionTimeline, DiffViewer, VersionBadge, VersionCompare)
- [x] Inventory views (list with type/workshop filters, detail with diff viewer + version update, add-to-inventory dialog)
- [x] Workshop management views (list with active highlight, detail with member management + inline edit)
- [x] Settings views (theme switcher with live preview, system info)
- [x] Sidebar navigation fully functional (stale count badge, active workshop label)
- [x] Header workshop switcher (dropdown to set active workshop context)
- [x] "Add to inventory" button on catalogue detail view
- [x] Module manifest schema (ModuleManifest Pydantic model with full validation)
- [x] UserDB migration 002 (package_path column for local module loading)
- [x] Module SDK package (catalogue_client, userdb, config, context, peers, logger, testing)
- [x] `makestack_sdk` importable package (thin re-export wrapper at repo root)
- [x] Module loader (discovery, manifest validation, migration runner, router mounting)
- [x] ModuleRegistry (runtime registry — loaded/failed, keywords, panels, endpoints)
- [x] Modules router updated (manifest and load state in list response)
- [x] Dev API updated (GET /api/dev/modules, GET /api/dev/keywords)
- [x] MCP tool generator implemented (generate_module_tools() from ModuleRegistry)
- [x] Frontend dev tools (keywords playground, schema inspector, module inspector)
- [x] Sidebar dev section (visible only when MAKESTACK_DEV_MODE=true)
- [x] CLI (makestack start, dev, dev --module, module create, module validate, mcp, rebuild-frontend)
- [x] Tests (74 new — module_manifest, module_sdk, module_loader — 197 total)
- [ ] Widget pack loader (frontend-only, no restart) — Phase 6
- [ ] Registry client (resolve packages from registries, clone to cache) — Phase 6
- [ ] Package installer (type-specific handlers: module, widget-pack, catalogue, data) — Phase 6
- [ ] docker-compose.yml — Phase 7
- [ ] Export/import — Phase 7

---

## What's In Progress

Nothing currently in progress. Ready to begin Phase 6 (Registry / Package Manager).

---

## What's Blocked / Known Issues

Nothing currently blocked.

---

## Next Steps (Priority Order)

### Phase 1: Backend Foundation
1. Initialize Python project (pyproject.toml, directory structure)
2. CatalogueClient — httpx async client wrapping all Core endpoints
3. UserDB — aiosqlite connection, migration runner, core tables
4. FastAPI main.py — startup sequence, dependency injection providers
5. Catalogue proxy routes — pass-through to Core with instrumentation
6. Inventory routes — CRUD with hash-pointer creation and resolution
7. Workshop routes — CRUD + membership management
8. Version routes — history, diff proxied from Core
9. Settings routes — user preferences from UserDB
10. System routes — status endpoint, capabilities registry
11. Tests for all of the above

### Phase 2: MCP Server
12. MCP server skeleton — `mcp` SDK, tool list, SSE transport
13. Catalogue tools — search, browse, CRUD via Shell REST API
14. Inventory tools — add, list, check updates
15. Workshop tools — create, manage, switch context
16. Version tools — history, diff, compare
17. Settings + system tools
18. Module tool auto-generation from manifests
19. stdio transport + `makestack mcp` CLI command
20. MCP integration tests

### Phase 3: Frontend Foundation + Core Widgets
21. Vite + React + TanStack Router + TanStack Query setup
22. Theme loader — read theme JSON, inject CSS custom properties
23. Tailwind config — map CSS variables to Tailwind tokens
24. `@makestack/ui` — Radix UI wrappers
25. Layout — sidebar, header, workspace switcher, navigation
26. Keyword renderer registry — resolution chain (module → widget pack → core)
27. Core widget implementations (TIMER_, MEASUREMENT_, MATERIAL_REF_, TOOL_REF_, TECHNIQUE_REF_, IMAGE_, LINK_, NOTE_, CHECKLIST_)
28. Catalogue list view — browse by type, search
29. Catalogue detail view — show primitive with keyword/widget rendering
30. Version timeline + diff viewer components
31. Primitive create/edit views

### Phase 4: Personal State
32. Inventory views — add to inventory, browse, version tracking
33. Workshop management views
34. Settings views — preferences, theme switching

### Phase 5: Module System
35. Module SDK package (catalogue client, userdb, config, context, peers, logger, testing mocks)
36. Module loader — discovery, manifest validation, migration running, router mounting
37. Frontend module integration — build-time keyword renderer + panel registration
38. Widget pack loader — frontend-only install, no restart
39. MCP tool auto-generation wired to module loader
40. Dev mode — debug API, keyword playground, schema inspector
41. CLI — `makestack start`, `makestack dev`, `makestack module create`

### Phase 6: Registry / Package Manager (Architecture Designed, Implementation Here)
42. Registry client — fetch registries, resolve package names to Git URLs
43. Package cache manager — clone, version-switch, update via Git
44. Type-specific install handlers (module, widget-pack, catalogue, data)
45. CLI — `makestack install/uninstall/update/search`, `makestack registry add/list/remove`
46. Primary index integration — discover registries from the primary index

### Phase 7: Polish
47. Degraded mode — Core health check, cache, graceful degradation
48. Export/import — UserDB portable JSON format
49. docker-compose.yml — Core + Shell orchestration
50. Error boundaries per module
51. Production logging

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

---

## Session Log

### 2026-03-06 — Project Setup
- Created CLAUDE.md with MCP integration as core architectural principle
- MCP designed as thin translation layer over Shell REST API

### 2026-03-06 — Extensibility Architecture
- Established three-tier extension model: Widgets (frontend-only keyword renderers), Modules (full-stack extensions), Registry (Git-native package manager)
- Widgets are stateless, no backend, no install infrastructure, degrade gracefully
- Modules are full-stack with routes, UserDB tables, and optional frontend
- Registry is two-level Git-native: primary index → registries → packages
- Four installable package types: module, widget-pack, catalogue, data — each with type-specific install handler
- Registry architecture fully designed, implementation deferred to Phase 6
- Core API Reference expanded with implementation details from makestack-core codebase
- Shell is proprietary (All Rights Reserved); Core remains MIT
- Ready to begin Phase 1: Backend Foundation

### 2026-03-07 — Phase 2: MCP Server
Built the complete MCP server. 25 new tests; 123 total, all passing.

**Files created:**
- `mcp_server/__init__.py`
- `mcp_server/server.py` — `create_server(api_client?)` factory using FastMCP; accepts optional httpx client for testability
- `mcp_server/__main__.py` — stdio entry point (`python -m mcp_server`)
- `mcp_server/transport.py` — `create_sse_app()` returns Starlette app for mounting in FastAPI
- `mcp_server/tool_generator.py` — placeholder for Phase 5 module tool auto-generation
- `mcp_server/tools/__init__.py`
- `mcp_server/tools/catalogue.py` — 7 tools: search_catalogue, list_primitives, get_primitive, create_primitive, update_primitive, delete_primitive, get_relationships
- `mcp_server/tools/inventory.py` — 6 tools: add_to_inventory, list_inventory, get_inventory_item, check_inventory_updates, update_inventory_pointer, remove_from_inventory
- `mcp_server/tools/workshops.py` — 8 tools: list/get/create/update/delete_workshop, add/remove_from_workshop, set_active_workshop
- `mcp_server/tools/version.py` — 3 tools: get_primitive_history, compare_versions, get_primitive_at_version
- `mcp_server/tools/settings.py` — 4 tools: get_settings, update_settings, get_theme, set_theme
- `mcp_server/tools/modules.py` — 4 tools: list_modules, enable_module, disable_module, call_module
- `mcp_server/tools/system.py` — 2 tools: get_status, get_capabilities
- `cli/__init__.py`, `cli/commands/__init__.py`, `cli/commands/mcp.py` — `makestack mcp` entry point
- `backend/tests/test_mcp_server.py` — 25 integration tests

**Files modified:**
- `backend/app/main.py` — mounts MCP SSE app at `/mcp` via `app.mount("/mcp", create_sse_app())`
- `backend/requirements.txt` + `pyproject.toml` — added `mcp>=1.0.0`

**Key implementation notes:**
- Uses `FastMCP` from `mcp.server.fastmcp` (not low-level `mcp.server.Server`)
- Tools registered via `@mcp.tool()` decorator inside `register_tools(mcp, api)` functions — clean separation per domain
- All tools return JSON strings via `json.dumps(resp.json(), indent=2)` — AI gets full structured data
- Exception handling wraps every API call; errors returned as JSON with suggestion field
- `create_server(api_client=None)` accepts injected client for test isolation (ASGI transport)
- mcp 1.26.0 `call_tool()` returns `(list[ContentBlock],)` tuple — tests unwrap accordingly
- stdio transport responds correctly to MCP `initialize` handshake
- SSE endpoint at `/mcp/sse`

### 2026-03-07 — Phase 3: Frontend Foundation + Core Widgets

Built the complete React frontend. Build passes cleanly (`tsc -b && vite build`), 123 backend tests still pass.

**Files created (frontend/):**
- `vite.config.ts` — Tailwind v4 plugin, `@` path alias, API proxy to `:3000`
- `tsconfig.app.json` — added `paths: { "@/*": ["./src/*"] }`
- `index.html` — Google Fonts (Lexend + JetBrains Mono), title
- `src/index.css` — Cyberpunk CSS custom properties (`--ms-*`), `@theme inline` mapping to Tailwind token names, base resets
- `src/theme/tokens.ts` — `ThemeData` type, `ThemeName` union
- `src/theme/loader.ts` — fetches `/api/settings/theme/data`, injects CSS vars on `:root`
- `src/lib/api.ts` — `apiGet/Post/Put/Delete`, `ApiError` class
- `src/lib/keyword-detect.ts` — `isKeyword()`, `extractKeywords()`, `parseDuration()`, `formatDuration()`
- `src/lib/utils.ts` — `cn()`, `formatDate()`, `formatDateTime()`, `primitiveTypeBg()`, `abbreviateHash()`
- `src/lib/types.ts` — TypeScript types matching Shell Pydantic models (Primitive, PaginatedList, etc.)
- `src/modules/keyword-resolver.ts` — 3-layer registry (core/pack/module), `registerKeyword()`, `resolveKeyword()`
- `src/hooks/use-catalogue.ts` — `usePrimitiveList`, `usePrimitive`, `useSearch`, `useRelationships`, `useCreatePrimitive`, `useUpdatePrimitive`, `useDeletePrimitive`
- `src/hooks/use-version.ts` — `usePrimitiveHistory`, `usePrimitiveDiff`
- `src/components/ui/` — Badge, Button, Card (+Header/Body/Footer), Dialog, DropdownMenu, Input (+Textarea), ScrollArea, Select, Separator, Tabs, Tooltip + barrel index.ts
- `src/components/layout/Sidebar.tsx` — nav sections (Catalogue, Personal, System), disabled items with Phase 4 tooltip
- `src/components/layout/Header.tsx` — breadcrumb, search bar with navigate-on-submit
- `src/components/layout/Layout.tsx` — sidebar + header + `<Outlet />`
- `src/components/keywords/TimerWidget.tsx` — countdown timer with play/pause/reset, progress bar
- `src/components/keywords/MeasurementWidget.tsx` — unit display with toggle conversion (mm↔in, g↔oz, etc.)
- `src/components/keywords/RefWidget.tsx` — fetches primitive, renders compact card with navigate (shared for MATERIAL_REF_, TOOL_REF_, TECHNIQUE_REF_)
- `src/components/keywords/ImageWidget.tsx` — img with optional caption
- `src/components/keywords/LinkWidget.tsx` — external link with icon
- `src/components/keywords/NoteWidget.tsx` — info/warning/tip callout with icon
- `src/components/keywords/ChecklistWidget.tsx` — interactive checkbox list (local state)
- `src/components/keywords/KeywordValue.tsx` — resolves keyword → renderer, falls back to raw text
- `src/components/keywords/index.ts` — `registerCoreWidgets()` function
- `src/components/version/VersionBadge.tsx` — current/up-to-date/update-available badge
- `src/components/version/VersionTimeline.tsx` — scrollable commit list, click to navigate `?at=hash`
- `src/components/version/DiffViewer.tsx` — two-column before/after field diff
- `src/components/version/VersionCompare.tsx` — two selects + DiffViewer
- `src/components/catalogue/PrimitiveCard.tsx` — card for list view
- `src/components/catalogue/PropertyRenderer.tsx` — renders properties with keyword detection
- `src/components/catalogue/StepRenderer.tsx` — numbered steps with inline keyword rendering
- `src/components/catalogue/RelationshipsPanel.tsx` — relationship list with navigation
- `src/components/catalogue/PrimitiveForm.tsx` — shared create/edit form (type, name, desc, tags, steps, properties, relationships)
- `src/routes/catalogue/index.tsx` — `CatalogueIndex` — type tabs + paginated grid
- `src/routes/catalogue/search.tsx` — `CatalogueSearch` — debounced search input + results
- `src/routes/catalogue/create.tsx` — `CatalogueCreate` — PrimitiveForm → POST → navigate to detail
- `src/routes/catalogue/detail.tsx` — `CatalogueDetail` — full detail view with collapsible sections, delete dialog, version history
- `src/routes/catalogue/edit.tsx` — `CatalogueEdit` — loads primitive, PrimitiveForm → PUT → navigate to detail
- `src/router.tsx` — TanStack Router code-based routing; all routes use `validateSearch` for typed params
- `src/App.tsx` — `RouterProvider`
- `src/main.tsx` — `QueryClientProvider`, `loadTheme()`, `registerCoreWidgets()`, mount

**Files modified (backend/):**
- `backend/app/models.py` — added `ThemeData` model
- `backend/app/routers/settings.py` — added `GET /api/settings/theme/data` returning CSS variable maps for 4 built-in themes (cyberpunk, workshop, daylight, high-contrast)

**Key implementation notes:**
- Tailwind v4 with `@theme inline {}` — all color utilities reference `var(--ms-*)` CSS custom properties set at runtime by theme loader
- TanStack Router v1 code-based routing — `validateSearch` return type is strict; `at: undefined` must be passed explicitly when navigating to `/catalogue/detail`
- `erasableSyntaxOnly: true` in tsconfig requires class properties declared explicitly, not via constructor parameter shorthand
- Route components defined inline in `router.tsx` (not in separate files) to access `useSearch()` with the correct typed route reference

### 2026-03-07 — Phase 4: Personal State (Inventory, Workshop, Settings Views)

**Files created:**
- `frontend/src/lib/types.ts` — added InventoryItem, InventoryItemWithCatalogue, Workshop, WorkshopWithMembers, WorkshopMember, WorkshopCreate, WorkshopUpdate
- `frontend/src/hooks/use-inventory.ts` — 6 hooks: useInventoryList, useInventoryItem, useStaleItems, useAddToInventory, useUpdateInventoryItem, useRemoveFromInventory
- `frontend/src/hooks/use-workshops.ts` — 9 hooks: useWorkshopList, useWorkshop, useActiveWorkshop, useCreateWorkshop, useUpdateWorkshop, useDeleteWorkshop, useAddToWorkshop, useRemoveFromWorkshop, useSetActiveWorkshop
- `frontend/src/components/inventory/AddToInventoryDialog.tsx` — shared dialog (pre-fill from catalogue detail OR search to select primitive)
- `frontend/src/routes/inventory/index.tsx` — list with type/workshop filters, stale badges, pagination
- `frontend/src/routes/inventory/detail.tsx` — full detail with staleness diff, version update, workshop assignment
- `frontend/src/routes/workshops/index.tsx` — grid with active highlight, create dialog
- `frontend/src/routes/workshops/detail.tsx` — detail with inline edit, member list by type, add primitive search dialog
- `frontend/src/routes/settings/index.tsx` — theme switcher with live CSS var apply, system info panel

**Files modified:**
- `frontend/src/router.tsx` — added 5 new routes: inventory, inventory/detail, workshops, workshops/detail, settings
- `frontend/src/components/layout/Sidebar.tsx` — enabled all nav links, stale count badge on Inventory, active workshop label in PERSONAL section
- `frontend/src/components/layout/Header.tsx` — replaced "All" placeholder with functional WorkshopSwitcher dropdown
- `frontend/src/routes/catalogue/detail.tsx` — added "Add to inventory" button that opens AddToInventoryDialog

**Key patterns:**
- useActiveWorkshop uses a single async queryFn that chains settings → workshop fetch
- useSetActiveWorkshop invalidates `[WS_ACTIVE_KEY]` which triggers refetch of the chained query
- Routes without search params use `validateSearch: () => ({} as Record<never, never>)`
- Workshop member grouping: plain for loop with bracket notation (avoids ??= for compatibility)
- Theme switching: mutationFn does PUT then fetches /theme/data and calls applyTheme() synchronously

### 2026-03-07 — Phase 5: Module System

Built the complete module system. 74 new tests; 197 total, all passing. Frontend build clean.

**Files created (backend):**
- `backend/app/module_manifest.py` — ModuleManifest Pydantic model with field validation (name regex, keyword regex, table prefix check)
- `backend/app/module_loader.py` — ModuleLoader: discovery from installed_modules table, manifest parsing, migration runner, router mounting; ModuleRegistry class for runtime queries
- `backend/app/migrations/002_add_package_path.py` — adds `package_path` column to installed_modules for local dev loading
- `backend/sdk/catalogue_client.py` — SDK surface: re-exports CatalogueClient + FastAPI `get_catalogue_client` dependency
- `backend/sdk/userdb.py` — SDK surface: ModuleUserDB with table-name scope enforcement; `get_module_userdb_factory()`
- `backend/sdk/config.py` — SDK surface: ModuleConfig with defaults/overrides; `get_module_config_factory()`
- `backend/sdk/context.py` — SDK surface: ShellContext (user, workshop, version, dev_mode); `get_shell_context()`
- `backend/sdk/peers.py` — SDK surface: PeerModules with `is_installed()` and `call()` via Shell routing; `get_peer_modules()`
- `backend/sdk/logger.py` — SDK surface: `get_logger(module_name)` → pre-tagged structlog BoundLogger
- `backend/sdk/testing.py` — SDK surface: MockCatalogueClient, MockUserDB, MockShellContext, MockPeerModules, `create_test_app()`
- `makestack_sdk/__init__.py` — importable `makestack_sdk` package (thin re-exports from backend.sdk)
- `makestack_sdk/testing.py`, `userdb.py`, `config.py`, `context.py`, `logger.py`, `peers.py`, `catalogue_client.py` — sub-module re-exports
- `backend/tests/test_module_manifest.py` — 30 tests for manifest validation
- `backend/tests/test_module_sdk.py` — 26 tests for SDK classes (scoping, config, mocks, peers)
- `backend/tests/test_module_loader.py` — 18 tests for full module lifecycle

**Files created (cli):**
- `cli/main.py` — Click CLI with: `start`, `dev` (+ `--module PATH`), `module create`, `module validate`, `mcp`, `rebuild-frontend`
- Uses `<<KEY>>` placeholder templates (not .format()) to avoid JSON/TS curly brace conflicts in scaffolding

**Files created (frontend):**
- `frontend/src/routes/dev/keywords.tsx` — Keyword Playground: paste JSON, preview renderers, show registry
- `frontend/src/routes/dev/schema.tsx` — Schema Inspector: table browser grouped by owner, read-only SQL runner
- `frontend/src/routes/dev/modules.tsx` — Module Inspector: collapsible cards per module with keywords/endpoints/tables

**Files modified:**
- `backend/sdk/__init__.py` — full public API exports
- `backend/app/main.py` — runs module loader in lifespan, wires MCP module tools
- `backend/app/routers/modules.py` — enriches list response with loaded/failed state from ModuleRegistry
- `backend/app/routers/dev.py` — added `GET /api/dev/modules` and `GET /api/dev/keywords`
- `backend/app/routers/system.py` — uses ModuleRegistry for real module counts
- `backend/app/models.py` — added `loaded`, `load_error`, `manifest`, `package_path` fields to InstalledModule
- `mcp_server/transport.py` — exposed `get_mcp_server()` singleton for post-startup tool registration
- `mcp_server/tool_generator.py` — implemented `generate_module_tools(mcp, registry)`
- `frontend/src/router.tsx` — added `/dev/keywords`, `/dev/schema`, `/dev/modules` routes
- `frontend/src/components/layout/Sidebar.tsx` — DevSection queries `/api/status` dev_mode flag, shows dev nav only in dev mode
- `pyproject.toml` — added `click>=8.1.0` dependency, `[project.scripts]` entry point, expanded packages list
- `backend/requirements.txt` — added `click>=8.1.0`

**Key implementation notes:**
- Module loader stores LoadedModule/FailedModule objects in ModuleRegistry on app.state.module_registry
- Local module loading: `package_path` in installed_modules; `_import_routes()` uses `importlib.util.spec_from_file_location`
- Module migrations tracked in `module_migrations` table; idempotent (skips already-applied)
- `makestack dev --module ./path` calls `_register_dev_module()` synchronously before uvicorn starts
- MCP tool generator: one tool per `api_endpoints` entry in manifest; tool names use `{module_name}__{method}_{path_slug}` convention; delegates to Shell's `/modules/{name}/` routing
- `makestack_sdk` is importable as a package because a root-level `makestack_sdk/` directory re-exports from `backend/sdk/`
- `ModuleUserDB._check_tables()` uses regex to extract table names from SQL — catches FROM/JOIN/INTO/UPDATE
- DevSection in Sidebar queries `/api/status` for `dev_mode` flag — degrades gracefully if not in dev mode
- CLI scaffold templates use `<<KEY>>` placeholders (not f-strings) to avoid conflicts with JSON/TypeScript `{}`/`{}` syntax

### 2026-03-06 — Phase 1: Backend Foundation
Built the complete backend foundation. 98 tests, all passing.

**Files created:**
- `pyproject.toml` — Python 3.10+ project (system only has 3.10; CLAUDE.md says 3.12+ but syntax is compatible)
- `LICENSE` — Proprietary, All Rights Reserved
- `backend/requirements.txt`
- `backend/app/models.py` — All Pydantic models (Primitive, Inventory, Workshop, Diff, etc.)
- `backend/app/core_client.py` — Async httpx CatalogueClient wrapping all Core endpoints
- `backend/app/userdb.py` — aiosqlite manager with migration runner and query helpers
- `backend/app/dependencies.py` — FastAPI DI providers (get_core_client, get_userdb, get_dev_mode)
- `backend/app/main.py` — FastAPI app with lifespan startup sequence, background health poll, CORS
- `backend/app/migrations/001_initial_schema.py` — All core tables + default user seed
- `backend/app/routers/catalogue.py` — Full Core proxy (all 10 endpoints)
- `backend/app/routers/inventory.py` — Hash-pointer CRUD with staleness detection
- `backend/app/routers/workshops.py` — Workshop CRUD + membership + active context
- `backend/app/routers/settings.py` — User preferences and theme management
- `backend/app/routers/version.py` — Standalone history/diff proxy routes
- `backend/app/routers/modules.py` — Module list/enable/disable (Phase 5 loader TBD)
- `backend/app/routers/system.py` — Status endpoint + full capabilities registry for MCP
- `backend/app/routers/dev.py` — Debug API (guarded by dev mode check)
- `backend/sdk/__init__.py` — Placeholder for Phase 5 module SDK
- `backend/tests/conftest.py` — Fixtures: in-memory UserDB, mock CatalogueClient, ASGI test client
- `backend/tests/test_core_client.py` — CatalogueClient unit tests with MockTransport
- `backend/tests/test_userdb.py` — Migration runner + query helper tests
- `backend/tests/test_catalogue_routes.py` — Route tests with mocked Core
- `backend/tests/test_inventory_routes.py` — Full inventory lifecycle tests
- `backend/tests/test_workshops_routes.py` — Workshop CRUD + membership tests
- `backend/tests/test_version_routes.py` — Version proxy route tests

**Key implementation notes:**
- Python version: `>=3.10` (system has 3.10, spec says 3.12+; `str | None` and match work in 3.10)
- Route ordering matters: `/stale` and `/active` are declared before `/{id}` to prevent routing collisions
- `{path:path}` FastAPI converter handles slash-containing primitive paths correctly
- Degraded mode: Core unavailability returns 503 with suggestion messages; background poll reconnects
- `GET /api/capabilities` returns machine-readable operation list for MCP Phase 2
- dev.py routes are always mounted but self-guard with a 403 check (avoids conditional mounting complexity)
- `execute_returning` uses SQLite's `RETURNING *` clause (available since SQLite 3.35 / Python 3.10)
