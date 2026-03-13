"""makestack-sdk — Module SDK for Makestack Shell.

This package provides five SDK surfaces for module authors:

1. CatalogueClient  — typed proxy to Core via Shell (read, search, write)
2. ModuleUserDB     — scoped access to module-owned UserDB tables
3. ModuleConfig     — module configuration (defaults + user overrides)
4. ShellContext     — current user, active workshop, Shell version, dev mode
5. PeerModules      — check peer modules and call their endpoints
6. get_logger       — pre-tagged structlog logger
7. Testing          — mock objects for module tests

Manifest schema (manifest.json)
--------------------------------
Modules declare their capabilities in manifest.json. Key optional fields:

``views`` — list of ModuleView objects, each registering a sidebar nav entry
for workshops that have this module associated. Fields:
  - id (str): unique within the module, used as the NavItem id
  - label (str): human-readable nav label
  - route (str): frontend route, e.g. "/modules/my-module/dashboard"
  - icon (str): Lucide icon name (optional, empty = default)
  - replaces_shell_view (str | None): one of "inventory", "workshops",
    "catalogue". Signals the frontend to demote that shell view to secondary
    position. Shell views are never removed — only visually demoted. At most
    one loaded module may claim each shell view; last-to-load wins.
  - sort_order (int, default 0): controls ordering within the workshop nav

``panels`` — list of ModulePanel objects, registering panels for the workshop
home screen. Fields:
  - id (str): registered in the frontend PanelRegistry (panelId → component).
    Unresolved ids render as <UnknownPanel>, never throw.
  - label (str): human-readable panel title
  - size ("full" | "half" | "third"): layout slot size on the home screen

Both fields are optional. Manifests without them remain valid. Existing modules
that do not declare views still appear in workshop nav as a default entry (using
the module name as label and /modules/{name} as route).

All SDK surfaces are injected via FastAPI Depends(). Module authors should
not construct these classes directly.

Quick-start example (module's backend/routes.py):

    from fastapi import APIRouter, Depends
    from makestack_sdk import (
        CatalogueClient, get_catalogue_client,
        ModuleUserDB, get_module_userdb_factory,
        ShellContext, get_shell_context,
        get_logger,
    )

    log = get_logger("my-module")
    router = APIRouter()

    get_db = get_module_userdb_factory("my-module", ["my_module_items"])

    @router.get("/items")
    async def list_items(
        db: ModuleUserDB = Depends(get_db),
        ctx: ShellContext = Depends(get_shell_context),
    ):
        log.info("list_items", user=ctx.user_id)
        rows = await db.fetch_all("SELECT * FROM my_module_items")
        return {"items": rows, "total": len(rows)}
"""

# Re-export the public SDK API from a single entry point.

from .catalogue_client import (
    CatalogueClient,
    CoreNotFoundError,
    CoreUnavailableError,
    CoreValidationError,
    get_catalogue_client,
)
from .config import ModuleConfig, get_module_config_factory
from .context import ShellContext, get_shell_context
from .logger import get_logger
from .peers import PeerModules, get_peer_modules
from .userdb import ModuleUserDB, get_module_userdb_factory

__all__ = [
    # Catalogue
    "CatalogueClient",
    "CoreNotFoundError",
    "CoreUnavailableError",
    "CoreValidationError",
    "get_catalogue_client",
    # UserDB
    "ModuleUserDB",
    "get_module_userdb_factory",
    # Config
    "ModuleConfig",
    "get_module_config_factory",
    # Context
    "ShellContext",
    "get_shell_context",
    # Peers
    "PeerModules",
    "get_peer_modules",
    # Logger
    "get_logger",
]
