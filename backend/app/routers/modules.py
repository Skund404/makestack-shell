"""Module management routes.

GET  /api/modules          — list installed modules with load state + manifest
PUT  /api/modules/{name}/enable  — enable a module (requires restart)
PUT  /api/modules/{name}/disable — disable a module (requires restart)
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from ..dependencies import get_userdb
from ..models import InstalledModule, PaginatedList
from ..userdb import UserDB

log = structlog.get_logger().bind(component="modules_router")

router = APIRouter(prefix="/api/modules", tags=["modules"])


def _row_to_module(row: dict, registry=None) -> InstalledModule:
    """Convert a DB row to an InstalledModule, enriched with runtime state from registry."""
    name = row["name"]
    loaded = False
    load_error: str | None = None
    manifest_data: dict | None = None

    if registry is not None:
        loaded_mod = registry.get_module(name)
        if loaded_mod is not None:
            loaded = True
            manifest_data = loaded_mod.manifest.model_dump()
        else:
            # Check if it failed to load
            failed = next((f for f in registry.get_failed() if f.name == name), None)
            if failed:
                load_error = failed.error

    return InstalledModule(
        name=name,
        version=row["version"],
        installed_at=row["installed_at"],
        enabled=bool(row["enabled"]),
        last_migration=row.get("last_migration"),
        package_path=row.get("package_path"),
        loaded=loaded,
        load_error=load_error,
        manifest=manifest_data,
    )


@router.get("", response_model=PaginatedList[InstalledModule], summary="List installed modules")
async def list_modules(
    limit: int = 50,
    offset: int = 0,
    request: Request = None,
    db: UserDB = Depends(get_userdb),
) -> PaginatedList[InstalledModule]:
    """List all registered modules with their enabled state, load status, and manifest."""
    registry = getattr(request.app.state, "module_registry", None) if request else None
    total = await db.count("installed_modules")
    rows = await db.fetch_all(
        "SELECT * FROM installed_modules ORDER BY name ASC LIMIT ? OFFSET ?",
        [limit, offset],
    )
    return PaginatedList(
        items=[_row_to_module(r, registry) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.put("/{name}/enable", response_model=InstalledModule, summary="Enable a module")
async def enable_module(
    name: str,
    request: Request = None,
    db: UserDB = Depends(get_userdb),
) -> InstalledModule:
    """Enable an installed module. The Shell must be restarted for the change to take effect."""
    row = await db.fetch_one("SELECT * FROM installed_modules WHERE name = ?", [name])
    if not row:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Module not found",
                "name": name,
                "suggestion": "Use GET /api/modules to list installed modules",
            },
        )
    updated = await db.execute_returning(
        "UPDATE installed_modules SET enabled = 1 WHERE name = ? RETURNING *",
        [name],
    )
    log.info("module_enabled", name=name)
    registry = getattr(request.app.state, "module_registry", None) if request else None
    return _row_to_module(updated, registry)


@router.get("/{name}/views", summary="Get views and panels declared by a module")
async def get_module_views(
    name: str,
    request: Request = None,
) -> dict:
    """Return the views and panels declared in a loaded module's manifest.

    views: nav entries the module can register for workshop sidebars.
    panels: home panels the module can register for workshop home screens.

    Returns 404 if the module is not currently loaded (even if installed).
    """
    registry = getattr(request.app.state, "module_registry", None) if request else None
    if registry is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Module registry unavailable",
                "suggestion": "The Shell has not finished starting up",
            },
        )
    loaded = registry.get_module(name)
    if loaded is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Module not loaded",
                "name": name,
                "suggestion": "Use GET /api/modules to list loaded modules",
            },
        )
    result: dict = {
        "views": [v.model_dump() for v in loaded.manifest.views],
        "panels": [p.model_dump() for p in loaded.manifest.panels],
    }
    if loaded.manifest.app_mode is not None:
        result["app_mode"] = loaded.manifest.app_mode.model_dump()
    return result


@router.put("/{name}/disable", response_model=InstalledModule, summary="Disable a module")
async def disable_module(
    name: str,
    request: Request = None,
    db: UserDB = Depends(get_userdb),
) -> InstalledModule:
    """Disable an installed module. The Shell must be restarted for the change to take effect."""
    row = await db.fetch_one("SELECT * FROM installed_modules WHERE name = ?", [name])
    if not row:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Module not found",
                "name": name,
                "suggestion": "Use GET /api/modules to list installed modules",
            },
        )
    updated = await db.execute_returning(
        "UPDATE installed_modules SET enabled = 0 WHERE name = ? RETURNING *",
        [name],
    )
    log.info("module_disabled", name=name)
    registry = getattr(request.app.state, "module_registry", None) if request else None
    return _row_to_module(updated, registry)
