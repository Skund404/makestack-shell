"""makestack-sdk — Module SDK for Makestack Shell.

This package provides five SDK surfaces for module authors:

1. CatalogueClient  — typed proxy to Core via Shell (read, search, write)
2. ModuleUserDB     — scoped access to module-owned UserDB tables
3. ModuleConfig     — module configuration (defaults + user overrides)
4. ShellContext     — current user, active workshop, Shell version, dev mode
5. PeerModules      — check peer modules and call their endpoints
6. get_logger       — pre-tagged structlog logger
7. Testing          — mock objects for module tests

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
