"""Dev-mode debug routes — only mounted when MAKESTACK_DEV_MODE=true.

These endpoints expose internals (SQL queries, config values, health details)
that are intentionally unavailable in production.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..core_client import CatalogueClient
from ..dependencies import get_core_client, get_dev_mode, get_userdb
from ..userdb import UserDB

log = structlog.get_logger().bind(component="dev_router")

router = APIRouter(prefix="/api/dev", tags=["dev"])

# Guard: all endpoints check dev mode at request time so the router can always
# be mounted — it simply returns 403 in production.


def _require_dev(dev_mode: bool = Depends(get_dev_mode)) -> None:
    """Dependency that raises 403 when not in dev mode."""
    if not dev_mode:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Dev endpoint unavailable",
                "detail": "These endpoints are only available when MAKESTACK_DEV_MODE=true",
            },
        )


@router.get("/health", summary="Full system health check", dependencies=[Depends(_require_dev)])
async def dev_health(
    core: CatalogueClient = Depends(get_core_client),
    db: UserDB = Depends(get_userdb),
) -> dict:
    """Full health check — core connectivity, UserDB integrity."""
    core_ok = await core.health_check()
    tables = await db.table_names()

    return {
        "status": "ok" if core_ok else "degraded",
        "core": {"connected": core_ok, "url": core._base_url},
        "userdb": {"path": db.path, "tables": tables},
    }


@router.get(
    "/userdb/tables",
    summary="List UserDB tables with row counts",
    dependencies=[Depends(_require_dev)],
)
async def dev_userdb_tables(
    db: UserDB = Depends(get_userdb),
) -> dict:
    """Return all UserDB table names with their row counts."""
    tables = await db.table_names()
    result: dict[str, int] = {}
    for table in tables:
        result[table] = await db.count(table)
    return {"tables": result}


@router.get(
    "/userdb/query",
    summary="Execute a read-only SQL query",
    dependencies=[Depends(_require_dev)],
)
async def dev_userdb_query(
    sql: str = Query(..., description="SQL SELECT statement to execute"),
    db: UserDB = Depends(get_userdb),
) -> dict:
    """Execute a read-only SQL query against the UserDB.

    Only SELECT statements are permitted. Any other statement type returns 400.
    """
    stripped = sql.strip().upper()
    if not stripped.startswith("SELECT"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Only SELECT statements are allowed",
                "suggestion": "This endpoint is read-only; use it for inspection only",
            },
        )
    try:
        rows = await db.fetch_all(sql)
        return {"rows": rows, "count": len(rows)}
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "Query failed", "detail": str(exc)},
        ) from exc


@router.get(
    "/config",
    summary="Resolved Shell configuration",
    dependencies=[Depends(_require_dev)],
)
async def dev_config(request: Request) -> dict:
    """Return the resolved Shell configuration (env vars, with secrets redacted)."""
    config: dict = dict(getattr(request.app.state, "config", {}))
    # Redact the API key.
    if config.get("core_api_key"):
        config["core_api_key"] = "***REDACTED***"
    return {"config": config}


@router.get(
    "/modules",
    summary="Full module debug info",
    dependencies=[Depends(_require_dev)],
)
async def dev_modules(request: Request) -> dict:
    """Return full debug info for all loaded and failed modules.

    Includes manifest details, registered keywords, panels, endpoints, and tables.
    """
    registry = getattr(request.app.state, "module_registry", None)
    if registry is None:
        return {"loaded": [], "failed": [], "note": "Module registry not yet initialised"}

    loaded = []
    for m in registry.get_loaded():
        loaded.append({
            "name": m.name,
            "version": m.manifest.version,
            "display_name": m.manifest.display_name,
            "description": m.manifest.description,
            "package_path": m.package_path,
            "has_backend": m.manifest.has_backend,
            "has_frontend": m.manifest.has_frontend,
            "mount_prefix": m.mount_prefix,
            "keywords": [kw.model_dump() for kw in m.manifest.keywords],
            "api_endpoints": [ep.model_dump() for ep in m.manifest.api_endpoints],
            "panels": [p.model_dump() for p in m.manifest.panels],
            "userdb_tables": [t.model_dump() for t in m.manifest.userdb_tables],
        })

    failed = [{"name": f.name, "error": f.error} for f in registry.get_failed()]

    return {
        "loaded": loaded,
        "failed": failed,
        "total_loaded": len(loaded),
        "total_failed": len(failed),
    }


@router.get(
    "/keywords",
    summary="Full keyword renderer registry",
    dependencies=[Depends(_require_dev)],
)
async def dev_keywords(request: Request) -> dict:
    """Return all registered keyword renderers grouped by source.

    Source is one of: core, module (with module name).
    Widget pack keywords are registered at frontend build time and not visible here.
    """
    registry = getattr(request.app.state, "module_registry", None)
    module_keywords: dict[str, str] = {}
    if registry is not None:
        module_keywords = registry.get_all_keywords()

    # Core keywords are fixed — list them statically.
    core_keywords = [
        "TIMER_", "MEASUREMENT_", "MATERIAL_REF_", "TOOL_REF_",
        "TECHNIQUE_REF_", "IMAGE_", "LINK_", "NOTE_", "CHECKLIST_",
    ]

    result = []
    for kw in core_keywords:
        result.append({"keyword": kw, "source": "core", "module": None})
    for kw, module_name in sorted(module_keywords.items()):
        result.append({"keyword": kw, "source": "module", "module": module_name})

    return {
        "keywords": result,
        "total": len(result),
        "core_count": len(core_keywords),
        "module_count": len(module_keywords),
    }
