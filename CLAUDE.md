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

**This repo (makestack-app)** is the Shell — the host application that sits between the user and everything else. It:
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

## Module System

### Build-Time Integration (Not Hot-Loading)

Module install → triggers frontend rebuild → restart Shell. No runtime module federation.

### Module SDK (5 Surfaces)

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

## Key Keyword Concepts

```json
{ "TIMER_": "30min" }        → renders countdown timer
{ "MEASUREMENT_": "4mm" }    → renders measurement with unit conversion
```

- Core keywords: TIMER_, MEASUREMENT_, MATERIAL_REF_, TOOL_REF_, TECHNIQUE_REF_, IMAGE_, LINK_, NOTE_, CHECKLIST_
- Module keywords: prefixed with module name (e.g., INVENTORY_STOCK_)
- Unknown keywords display as raw text (graceful degradation)
- Detection: regex `^[A-Z][A-Z0-9_]*_$` on JSON keys

See **03-JSON-KEYWORD-CONVENTION.md** for full spec.

---

## Directory Layout (Runtime)

```
~/.makestack/                    # Shell's local state (not in Git)
├── userdb.sqlite
├── cache/
└── logs/

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

Shell: **NOT YET STARTED**

- [ ] Python project initialized (pyproject.toml, requirements.txt)
- [ ] FastAPI entry point with startup sequence
- [ ] CatalogueClient (httpx proxy to Core)
- [ ] UserDB schema and migration runner
- [ ] Catalogue proxy routes
- [ ] Inventory routes (CRUD with hash-pointer management)
- [ ] Workshop routes (CRUD + membership)
- [ ] Version/history routes
- [ ] Settings routes
- [ ] System routes (status, capabilities)
- [ ] Degraded mode
- [ ] Dev mode debug API
- [ ] MCP server (tool definitions, SSE + stdio transports)
- [ ] MCP module tool auto-generation
- [ ] React frontend initialized
- [ ] Theme loader
- [ ] Layout (sidebar, header, navigation, workshop switcher)
- [ ] Catalogue browsing views
- [ ] Primitive editing views
- [ ] Keyword renderer registry + core renderers
- [ ] Version timeline and diff viewer
- [ ] Inventory views
- [ ] Workshop management views
- [ ] Settings views
- [ ] Module SDK package
- [ ] Module loader
- [ ] Frontend module integration
- [ ] CLI (start, dev, mcp, module management, export/import)
- [ ] docker-compose.yml
- [ ] Tests

---

## What's In Progress

Nothing currently in progress.

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

### Phase 3: Frontend Foundation
21. Vite + React + TanStack Router + TanStack Query setup
22. Theme loader — read theme JSON, inject CSS custom properties
23. Tailwind config — map CSS variables to Tailwind tokens
24. `@makestack/ui` — Radix UI wrappers
25. Layout — sidebar, header, workspace switcher, navigation
26. Catalogue list view — browse by type, search
27. Catalogue detail view — show primitive with keyword rendering
28. Core keyword renderers
29. Version timeline + diff viewer components
30. Primitive create/edit views

### Phase 4: Personal State
31. Inventory views — add to inventory, browse, version tracking
32. Workshop management views
33. Settings views — preferences, theme switching

### Phase 5: Module System
34. Module SDK package
35. Module loader — discovery, validation, migration running, router mounting
36. Frontend module integration — build-time component registry
37. MCP tool auto-generation wired to module loader
38. Dev mode — debug API, keyword playground, schema inspector
39. CLI — `makestack start`, `makestack dev`, `makestack module create/install/uninstall`

### Phase 6: Polish
40. Degraded mode — Core health check, cache, graceful degradation
41. Export/import — UserDB portable JSON format
42. docker-compose.yml — Core + Shell orchestration
43. Error boundaries per module
44. Production logging

---

## Decisions Made

- **Licensing: Shell is proprietary (All Rights Reserved).** Core (makestack-core) is MIT open-source. The Shell is private — not to be published, distributed, or used by others without explicit permission. This split is intentional: the catalogue engine is open, the application layer is not. Modules will have their own licensing (TBD per module).
- Shell is Python/FastAPI + React (not Go, not Next.js, not Electron)
- Build-time module loading (not hot-loading)
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
- Shell development not yet started — Core is feature-complete, specs are complete
- MCP designed as thin translation layer over Shell REST API
- Ready to begin Phase 1: Backend Foundation
