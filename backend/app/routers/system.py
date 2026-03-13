"""System routes — Shell health, status, and machine-readable capabilities.

GET /api/status       → Runtime state (core connection, modules loaded, uptime)
GET /api/capabilities → Full operation list for MCP tool auto-generation
POST /api/system/shutdown       → Gracefully shut down the Shell process
POST /api/system/restart        → Restart the Shell process (exec)
POST /api/system/core/shutdown  → Send SIGTERM to the Core process
"""

import asyncio
import os
import signal
import subprocess
import sys
import time
from urllib.parse import urlparse

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from ..constants import SHELL_VERSION as _SHELL_VERSION
from ..core_client import CatalogueClient
from ..dependencies import get_core_client, get_userdb
from ..models import Capability, CapabilitiesResponse, CapabilityParam, SystemStatus
from ..userdb import UserDB

log = structlog.get_logger().bind(component="system_router")

router = APIRouter(prefix="/api", tags=["system"])


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
        last_core_check=getattr(request.app.state, "last_core_check", None),
        modules_loaded=modules_loaded,
        modules_failed=modules_failed,
        userdb_path=db.path,
        uptime_seconds=round(time.monotonic() - start_time, 1),
        cache_size=core.cache_size,
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
    # User profile
    Capability(
        method="GET", path="/api/users/me",
        description="Get current user profile (name, avatar, bio, timezone, locale)",
        tags=["users"],
    ),
    Capability(
        method="PUT", path="/api/users/me",
        description="Update current user profile",
        tags=["users"],
    ),
    Capability(
        method="GET", path="/api/users/me/stats",
        description="Activity summary: workshop count, inventory count, module count",
        tags=["users"],
    ),
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
    # Packages
    Capability(method="GET", path="/api/packages", description="List all installed packages", tags=["packages"]),
    Capability(
        method="POST", path="/api/packages/install",
        description="Install a package by registry name, Git URL, or local path",
        tags=["packages"],
    ),
    Capability(
        method="DELETE", path="/api/packages/{name}",
        description="Uninstall a package",
        tags=["packages"],
        params=[CapabilityParam(name="name", type="string", required=True)],
    ),
    Capability(
        method="POST", path="/api/packages/{name}/update",
        description="Update an installed package to its latest or a specific version",
        tags=["packages"],
        params=[CapabilityParam(name="name", type="string", required=True)],
    ),
    Capability(
        method="GET", path="/api/packages/search",
        description="Search packages across all configured registries",
        tags=["packages"],
        params=[CapabilityParam(name="q", type="string", required=True, description="Search query")],
    ),
    # Registries
    Capability(method="GET", path="/api/registries", description="List configured registries", tags=["packages"]),
    Capability(method="POST", path="/api/registries", description="Add a registry", tags=["packages"]),
    Capability(
        method="DELETE", path="/api/registries/{name}",
        description="Remove a registry",
        tags=["packages"],
        params=[CapabilityParam(name="name", type="string", required=True)],
    ),
    Capability(
        method="POST", path="/api/registries/refresh",
        description="Pull latest from all configured registries",
        tags=["packages"],
    ),
    # Data export/import
    Capability(
        method="GET", path="/api/data/export",
        description="Export personal data (workshops, inventory, preferences) as portable JSON",
        tags=["data"],
        params=[
            CapabilityParam(name="only", type="string", required=False,
                            description="Section: workshops, inventory, preferences, or module:<name>"),
        ],
    ),
    Capability(
        method="POST", path="/api/data/import",
        description="Import personal data from an export document",
        tags=["data"],
        params=[
            CapabilityParam(name="only", type="string", required=False),
            CapabilityParam(name="strategy", type="string", required=False,
                            description="additive (default), overwrite, skip_conflicts"),
        ],
    ),
    # System
    Capability(method="GET", path="/api/status", description="Shell runtime status", tags=["system"]),
    Capability(
        method="GET", path="/api/capabilities",
        description="Machine-readable list of all available Shell operations",
        tags=["system"],
    ),
    Capability(
        method="POST", path="/api/system/shutdown",
        description="Gracefully shut down the Shell process",
        tags=["system"],
    ),
    Capability(
        method="POST", path="/api/system/restart",
        description="Restart the Shell process",
        tags=["system"],
    ),
    Capability(
        method="POST", path="/api/system/core/shutdown",
        description="Send SIGTERM to the Core process",
        tags=["system"],
    ),
]


# ---------------------------------------------------------------------------
# Process control endpoints
# ---------------------------------------------------------------------------


async def _shutdown_after_response() -> None:
    await asyncio.sleep(0.4)
    log.info("shell_shutdown_requested")
    os.kill(os.getpid(), signal.SIGTERM)


async def _restart_after_response() -> None:
    await asyncio.sleep(0.4)
    log.info("shell_restart_requested")
    os.execv(sys.executable, [sys.executable] + sys.argv)


def _find_pid_on_port(port: int) -> list[int]:
    """Return PIDs listening on the given TCP port using lsof."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return [int(p) for p in result.stdout.split() if p.strip().isdigit()]
    except Exception:
        return []


@router.post("/system/shutdown", summary="Shut down the Shell process")
async def shutdown_shell() -> dict:
    """Gracefully shut down the Shell process (SIGTERM).

    The response is sent before the process exits.
    """
    asyncio.create_task(_shutdown_after_response())
    return {"status": "shutting_down", "message": "Shell is shutting down."}


@router.post("/system/restart", summary="Restart the Shell process")
async def restart_shell() -> dict:
    """Restart the Shell process using os.execv (replaces current process).

    The response is sent before the restart. The UI should poll /api/status
    until it gets a successful response.
    """
    asyncio.create_task(_restart_after_response())
    return {"status": "restarting", "message": "Shell is restarting. Poll /api/status to detect when it is back."}


@router.post("/system/core/shutdown", summary="Shut down the Core process")
async def shutdown_core(request: Request) -> dict:
    """Send SIGTERM to the Core process.

    Finds the Core process by the port it is configured to listen on.
    """
    core_url: str = getattr(request.app.state, "config", {}).get(
        "core_url", "http://localhost:8420"
    )
    parsed = urlparse(core_url)
    port = parsed.port or 8420

    pids = _find_pid_on_port(port)
    if not pids:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"No process found listening on port {port}.",
                "suggestion": "Core may already be stopped.",
            },
        )

    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            log.info("core_shutdown_requested", pid=pid, port=port)
        except ProcessLookupError:
            pass

    return {
        "status": "stopping",
        "message": f"Sent SIGTERM to Core process(es) on port {port}.",
        "pids": pids,
    }


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
