"""System routes — Shell health, status, and machine-readable capabilities.

GET /api/status      → Runtime state (core connection, modules loaded, uptime)
GET /api/capabilities → Full operation list for MCP tool auto-generation
"""

import time

import structlog
from fastapi import APIRouter, Depends, Request

from ..core_client import CatalogueClient
from ..dependencies import get_core_client, get_userdb
from ..models import Capability, CapabilitiesResponse, CapabilityParam, SystemStatus
from ..userdb import UserDB

log = structlog.get_logger().bind(component="system_router")

router = APIRouter(prefix="/api", tags=["system"])

_SHELL_VERSION = "0.1.0"


@router.get("/status", response_model=SystemStatus, summary="Shell runtime status")
async def get_status(
    request: Request,
    core: CatalogueClient = Depends(get_core_client),
    db: UserDB = Depends(get_userdb),
) -> SystemStatus:
    """Return current Shell health and runtime state."""
    start_time: float = getattr(request.app.state, "start_time", time.monotonic())
    registry = getattr(request.app.state, "module_registry", None)
    modules_loaded = len(registry.get_loaded()) if registry else 0
    modules_failed = len(registry.get_failed()) if registry else 0

    return SystemStatus(
        shell_version=_SHELL_VERSION,
        core_connected=core.connected,
        core_url=getattr(request.app.state, "config", {}).get("core_url", "http://localhost:8420"),
        modules_loaded=modules_loaded,
        modules_failed=modules_failed,
        userdb_path=db.path,
        uptime_seconds=round(time.monotonic() - start_time, 1),
    )


# ---------------------------------------------------------------------------
# Capabilities — machine-readable operation registry for MCP tool generation
# ---------------------------------------------------------------------------

_CAPABILITIES: list[Capability] = [
    # Catalogue
    Capability(
        method="GET", path="/api/catalogue/primitives",
        description="List catalogue primitives, optionally filtered by type",
        tags=["catalogue"],
        params=[
            CapabilityParam(name="type", type="string", required=False, description="Primitive type filter"),
            CapabilityParam(name="limit", type="integer", required=False, description="Max results per page"),
            CapabilityParam(name="offset", type="integer", required=False, description="Pagination offset"),
        ],
    ),
    Capability(
        method="GET", path="/api/catalogue/search",
        description="Full-text search across the catalogue",
        tags=["catalogue"],
        params=[
            CapabilityParam(name="q", type="string", required=True, description="Search query"),
            CapabilityParam(name="limit", type="integer", required=False),
            CapabilityParam(name="offset", type="integer", required=False),
        ],
    ),
    Capability(
        method="GET", path="/api/catalogue/primitives/{path}",
        description="Get a primitive at its current version or a specific commit",
        tags=["catalogue"],
        params=[
            CapabilityParam(name="path", type="string", required=True, description="Primitive path"),
            CapabilityParam(name="at", type="string", required=False, description="Commit hash for historical read"),
        ],
    ),
    Capability(
        method="GET", path="/api/catalogue/primitives/{path}/hash",
        description="Get the current commit hash for a primitive",
        tags=["catalogue"],
        params=[CapabilityParam(name="path", type="string", required=True)],
    ),
    Capability(
        method="GET", path="/api/catalogue/primitives/{path}/history",
        description="Paginated commit history for a primitive",
        tags=["catalogue", "version"],
        params=[
            CapabilityParam(name="path", type="string", required=True),
            CapabilityParam(name="limit", type="integer", required=False),
            CapabilityParam(name="offset", type="integer", required=False),
        ],
    ),
    Capability(
        method="GET", path="/api/catalogue/primitives/{path}/diff",
        description="Structured field-level diff between two versions",
        tags=["catalogue", "version"],
        params=[
            CapabilityParam(name="path", type="string", required=True),
            CapabilityParam(name="from", type="string", required=False, description="Starting commit hash"),
            CapabilityParam(name="to", type="string", required=False, description="Ending commit hash"),
        ],
    ),
    Capability(
        method="GET", path="/api/catalogue/relationships/{path}",
        description="Bidirectional relationship lookup for a primitive",
        tags=["catalogue"],
        params=[CapabilityParam(name="path", type="string", required=True)],
    ),
    Capability(
        method="POST", path="/api/catalogue/primitives",
        description="Create a new primitive in the catalogue",
        tags=["catalogue"],
    ),
    Capability(
        method="PUT", path="/api/catalogue/primitives/{path}",
        description="Update a primitive (id, type, name, slug required in body)",
        tags=["catalogue"],
        params=[CapabilityParam(name="path", type="string", required=True)],
    ),
    Capability(
        method="DELETE", path="/api/catalogue/primitives/{path}",
        description="Delete a primitive from the catalogue",
        tags=["catalogue"],
        params=[CapabilityParam(name="path", type="string", required=True)],
    ),
    # Inventory
    Capability(
        method="GET", path="/api/inventory",
        description="List personal inventory items",
        tags=["inventory"],
        params=[
            CapabilityParam(name="workshop_id", type="string", required=False),
            CapabilityParam(name="type", type="string", required=False),
            CapabilityParam(name="limit", type="integer", required=False),
            CapabilityParam(name="offset", type="integer", required=False),
        ],
    ),
    Capability(
        method="GET", path="/api/inventory/stale",
        description="List inventory items where the catalogue has been updated",
        tags=["inventory"],
    ),
    Capability(
        method="GET", path="/api/inventory/{id}",
        description="Get an inventory item with resolved catalogue data",
        tags=["inventory"],
        params=[CapabilityParam(name="id", type="string", required=True)],
    ),
    Capability(
        method="POST", path="/api/inventory",
        description="Add a catalogue item to personal inventory",
        tags=["inventory"],
    ),
    Capability(
        method="PUT", path="/api/inventory/{id}",
        description="Update an inventory item (change workshop or pinned hash)",
        tags=["inventory"],
        params=[CapabilityParam(name="id", type="string", required=True)],
    ),
    Capability(
        method="DELETE", path="/api/inventory/{id}",
        description="Remove an item from inventory",
        tags=["inventory"],
        params=[CapabilityParam(name="id", type="string", required=True)],
    ),
    # Workshops
    Capability(method="GET", path="/api/workshops", description="List all workshops", tags=["workshops"]),
    Capability(
        method="GET", path="/api/workshops/{id}",
        description="Get a workshop with its member list",
        tags=["workshops"],
        params=[CapabilityParam(name="id", type="string", required=True)],
    ),
    Capability(method="POST", path="/api/workshops", description="Create a workshop", tags=["workshops"]),
    Capability(
        method="PUT", path="/api/workshops/{id}",
        description="Update a workshop",
        tags=["workshops"],
        params=[CapabilityParam(name="id", type="string", required=True)],
    ),
    Capability(
        method="DELETE", path="/api/workshops/{id}",
        description="Delete a workshop",
        tags=["workshops"],
        params=[CapabilityParam(name="id", type="string", required=True)],
    ),
    Capability(
        method="POST", path="/api/workshops/{id}/members",
        description="Add a primitive to a workshop",
        tags=["workshops"],
        params=[CapabilityParam(name="id", type="string", required=True)],
    ),
    Capability(
        method="DELETE", path="/api/workshops/{id}/members/{path}",
        description="Remove a primitive from a workshop",
        tags=["workshops"],
        params=[
            CapabilityParam(name="id", type="string", required=True),
            CapabilityParam(name="path", type="string", required=True),
        ],
    ),
    Capability(
        method="PUT", path="/api/workshops/active",
        description="Set the active workshop context",
        tags=["workshops"],
    ),
    # Settings
    Capability(method="GET", path="/api/settings", description="Get all user settings", tags=["settings"]),
    Capability(method="PUT", path="/api/settings/preferences", description="Update user preferences", tags=["settings"]),
    Capability(method="GET", path="/api/settings/theme", description="Get active theme", tags=["settings"]),
    Capability(method="PUT", path="/api/settings/theme", description="Switch active theme", tags=["settings"]),
    # Version
    Capability(
        method="GET", path="/api/version/{path}/history",
        description="Commit history for a primitive (alias of catalogue history endpoint)",
        tags=["version"],
        params=[CapabilityParam(name="path", type="string", required=True)],
    ),
    Capability(
        method="GET", path="/api/version/{path}/diff",
        description="Structured diff for a primitive (alias of catalogue diff endpoint)",
        tags=["version"],
        params=[CapabilityParam(name="path", type="string", required=True)],
    ),
    # Modules
    Capability(method="GET", path="/api/modules", description="List installed modules", tags=["modules"]),
    Capability(
        method="PUT", path="/api/modules/{name}/enable",
        description="Enable an installed module",
        tags=["modules"],
        params=[CapabilityParam(name="name", type="string", required=True)],
    ),
    Capability(
        method="PUT", path="/api/modules/{name}/disable",
        description="Disable an installed module",
        tags=["modules"],
        params=[CapabilityParam(name="name", type="string", required=True)],
    ),
    # System
    Capability(method="GET", path="/api/status", description="Shell runtime status", tags=["system"]),
    Capability(
        method="GET", path="/api/capabilities",
        description="Machine-readable list of all available Shell operations",
        tags=["system"],
    ),
]


@router.get(
    "/capabilities",
    response_model=CapabilitiesResponse,
    summary="Machine-readable operation registry",
)
async def get_capabilities() -> CapabilitiesResponse:
    """Return a structured description of every Shell API operation.

    Used by the MCP server to auto-generate tool definitions. Module endpoints
    are appended to this list when modules are loaded (Phase 5).
    """
    return CapabilitiesResponse(version=_SHELL_VERSION, capabilities=_CAPABILITIES)
