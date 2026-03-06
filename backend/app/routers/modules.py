"""Module management routes.

For Phase 1 these routes read from and write to the ``installed_modules`` table
in UserDB. The actual module loader (which mounts Python routers and runs
migrations) is built in Phase 5.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_userdb
from ..models import InstalledModule, PaginatedList
from ..userdb import UserDB

log = structlog.get_logger().bind(component="modules_router")

router = APIRouter(prefix="/api/modules", tags=["modules"])


def _row_to_module(row: dict) -> InstalledModule:
    return InstalledModule(
        name=row["name"],
        version=row["version"],
        installed_at=row["installed_at"],
        enabled=bool(row["enabled"]),
        last_migration=row.get("last_migration"),
    )


@router.get("", response_model=PaginatedList[InstalledModule], summary="List installed modules")
async def list_modules(
    limit: int = 50,
    offset: int = 0,
    db: UserDB = Depends(get_userdb),
) -> PaginatedList[InstalledModule]:
    """List all registered modules and their enabled state."""
    total = await db.count("installed_modules")
    rows = await db.fetch_all(
        "SELECT * FROM installed_modules ORDER BY name ASC LIMIT ? OFFSET ?",
        [limit, offset],
    )
    return PaginatedList(
        items=[_row_to_module(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.put("/{name}/enable", response_model=InstalledModule, summary="Enable a module")
async def enable_module(
    name: str,
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
    return _row_to_module(updated)


@router.put("/{name}/disable", response_model=InstalledModule, summary="Disable a module")
async def disable_module(
    name: str,
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
    return _row_to_module(updated)
