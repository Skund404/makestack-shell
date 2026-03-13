"""Data export/import routes — personal UserDB portability.

GET /api/data/export              → Export all personal data as portable JSON
GET /api/data/export?only=X       → Export a specific section
POST /api/data/import             → Import data (additive by default)
POST /api/data/import?only=X      → Import only a specific section
POST /api/data/import?strategy=X  → Import with a specific conflict strategy

Export sections:
  workshops, inventory, preferences, module:{name}

Import strategies:
  additive (default) — add new items, skip existing
  overwrite          — add new items, replace existing
  skip_conflicts     — same as additive (alias for clarity)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from ..dependencies import get_userdb
from ..userdb import UserDB

log = structlog.get_logger().bind(component="data_router")

router = APIRouter(prefix="/api/data", tags=["data"])

from ..constants import SHELL_VERSION

EXPORT_FORMAT_VERSION = "1.0.0"

ImportStrategy = Literal["additive", "overwrite", "skip_conflicts"]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ImportResult(BaseModel):
    """Summary of an import operation."""

    imported: dict[str, int]
    skipped: dict[str, int]
    replaced: dict[str, int]
    errors: list[str]


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------


async def _export_workshops(db: UserDB) -> list[dict]:
    rows = await db.fetch_all("SELECT * FROM workshops ORDER BY sort_order, created_at")
    result = []
    for ws in rows:
        members = await db.fetch_all(
            "SELECT primitive_path, primitive_type, added_at FROM workshop_members "
            "WHERE workshop_id = ? ORDER BY added_at",
            [ws["id"]],
        )
        result.append({**ws, "members": members})
    return result


async def _export_inventory(db: UserDB) -> list[dict]:
    return await db.fetch_all("SELECT * FROM inventory ORDER BY added_at")


async def _export_preferences(db: UserDB) -> dict[str, Any]:
    rows = await db.fetch_all("SELECT key, value FROM user_preferences")
    prefs: dict[str, Any] = {}
    for row in rows:
        try:
            prefs[row["key"]] = json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            prefs[row["key"]] = row["value"]
    return prefs


async def _export_module_data(db: UserDB, module_name: str, request: Request) -> dict[str, Any]:
    """Export all table data for a specific module.

    Reads table names from the module registry's manifest declarations.
    """
    registry = getattr(request.app.state, "module_registry", None)
    if registry is None:
        return {}

    # Find the loaded module
    loaded = {m.name: m for m in registry.get_loaded()}
    module = loaded.get(module_name)
    if module is None:
        return {}

    tables: dict[str, list[dict]] = {}
    for table_decl in module.manifest.userdb_tables:
        try:
            rows = await db.fetch_all(f"SELECT * FROM {table_decl.name}")  # noqa: S608
            tables[table_decl.name] = rows
        except Exception as exc:
            log.warning("module_export_table_failed", module=module_name, table=table_decl.name, error=str(exc))
            tables[table_decl.name] = []

    return {"tables": tables}


async def _export_all_modules(db: UserDB, request: Request) -> dict[str, Any]:
    registry = getattr(request.app.state, "module_registry", None)
    if registry is None:
        return {}

    result: dict[str, Any] = {}
    for module in registry.get_loaded():
        data = await _export_module_data(db, module.name, request)
        if data.get("tables"):
            result[module.name] = data
    return result


# ---------------------------------------------------------------------------
# Export endpoint
# ---------------------------------------------------------------------------


@router.get("/export", summary="Export personal data as portable JSON")
async def export_data(
    request: Request,
    only: str | None = Query(
        None,
        description=(
            "Section to export: workshops, inventory, preferences, "
            "or module:{name} for a specific module's data"
        ),
    ),
    db: UserDB = Depends(get_userdb),
) -> dict:
    """Export personal UserDB data as a portable JSON document.

    By default exports everything: workshops, inventory, preferences, and all
    module data. Use the `only` parameter to export a specific section.

    The exported document includes format version, export timestamp, and shell
    version for compatibility checks during import.
    """
    now = datetime.now(timezone.utc).isoformat()
    sections: dict[str, Any] = {}

    if only is None or only == "workshops":
        sections["workshops"] = await _export_workshops(db)
    if only is None or only == "inventory":
        sections["inventory"] = await _export_inventory(db)
    if only is None or only == "preferences":
        sections["preferences"] = await _export_preferences(db)

    if only is None:
        # Export all module data
        sections["module_data"] = await _export_all_modules(db, request)
    elif only.startswith("module:"):
        module_name = only[len("module:"):]
        module_data = await _export_module_data(db, module_name, request)
        if not module_data:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": f"Module '{module_name}' not found or has no data tables",
                    "suggestion": "Use GET /api/modules to list installed modules",
                },
            )
        sections["module_data"] = {module_name: module_data}

    if only is not None and only not in ("workshops", "inventory", "preferences") and not only.startswith("module:"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"Unknown section '{only}'",
                "suggestion": "Valid values: workshops, inventory, preferences, module:<name>",
            },
        )

    return {
        "version": EXPORT_FORMAT_VERSION,
        "exported_at": now,
        "shell_version": SHELL_VERSION,
        "sections": sections,
    }


# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------


async def _import_workshops(
    db: UserDB,
    workshops: list[dict],
    strategy: ImportStrategy,
) -> tuple[int, int, int, list[str]]:
    """Import workshops. Returns (imported, skipped, replaced, errors)."""
    imported = skipped = replaced = 0
    errors: list[str] = []

    for ws in workshops:
        ws_id = ws.get("id", "")
        members = ws.pop("members", [])
        existing = await db.fetch_one("SELECT id FROM workshops WHERE id = ?", [ws_id])

        if existing:
            if strategy == "overwrite":
                await db.execute(
                    "UPDATE workshops SET name=?, slug=?, description=?, icon=?, color=?, "
                    "sort_order=?, updated_at=? WHERE id=?",
                    [ws.get("name"), ws.get("slug"), ws.get("description", ""),
                     ws.get("icon", ""), ws.get("color", ""), ws.get("sort_order", 0),
                     datetime.now(timezone.utc).isoformat(), ws_id],
                )
                replaced += 1
            else:
                skipped += 1
                continue
        else:
            try:
                await db.execute(
                    "INSERT INTO workshops (id, name, slug, description, icon, color, sort_order, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [ws_id, ws.get("name"), ws.get("slug"), ws.get("description", ""),
                     ws.get("icon", ""), ws.get("color", ""), ws.get("sort_order", 0),
                     ws.get("created_at", datetime.now(timezone.utc).isoformat()),
                     ws.get("updated_at", datetime.now(timezone.utc).isoformat())],
                )
                imported += 1
            except Exception as exc:
                errors.append(f"Workshop {ws_id}: {exc}")
                continue

        # Import members (always additive — membership is idempotent)
        for m in members:
            try:
                await db.execute(
                    "INSERT OR IGNORE INTO workshop_members (workshop_id, primitive_path, primitive_type, added_at) "
                    "VALUES (?, ?, ?, ?)",
                    [ws_id, m.get("primitive_path"), m.get("primitive_type"), m.get("added_at")],
                )
            except Exception as exc:
                errors.append(f"Workshop {ws_id} member {m.get('primitive_path')}: {exc}")

    return imported, skipped, replaced, errors


async def _import_inventory(
    db: UserDB,
    inventory: list[dict],
    strategy: ImportStrategy,
) -> tuple[int, int, int, list[str]]:
    imported = skipped = replaced = 0
    errors: list[str] = []

    for item in inventory:
        item_id = item.get("id", "")
        existing = await db.fetch_one("SELECT id FROM inventory WHERE id = ?", [item_id])

        if existing:
            if strategy == "overwrite":
                await db.execute(
                    "UPDATE inventory SET catalogue_path=?, catalogue_hash=?, primitive_type=?, "
                    "workshop_id=?, updated_at=? WHERE id=?",
                    [item.get("catalogue_path"), item.get("catalogue_hash"),
                     item.get("primitive_type"), item.get("workshop_id"),
                     datetime.now(timezone.utc).isoformat(), item_id],
                )
                replaced += 1
            else:
                skipped += 1
        else:
            try:
                await db.execute(
                    "INSERT INTO inventory (id, catalogue_path, catalogue_hash, primitive_type, "
                    "workshop_id, added_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [item_id, item.get("catalogue_path"), item.get("catalogue_hash"),
                     item.get("primitive_type"), item.get("workshop_id"),
                     item.get("added_at", datetime.now(timezone.utc).isoformat()),
                     item.get("updated_at", datetime.now(timezone.utc).isoformat())],
                )
                imported += 1
            except Exception as exc:
                errors.append(f"Inventory {item_id}: {exc}")

    return imported, skipped, replaced, errors


async def _import_preferences(
    db: UserDB,
    preferences: dict[str, Any],
    strategy: ImportStrategy,
) -> tuple[int, int, int, list[str]]:
    imported = skipped = replaced = 0
    errors: list[str] = []

    # Get user_id — default to "default" if no users exist
    user_row = await db.fetch_one("SELECT id FROM users LIMIT 1")
    user_id = user_row["id"] if user_row else "default"

    for key, value in preferences.items():
        encoded = json.dumps(value)
        existing = await db.fetch_one(
            "SELECT key FROM user_preferences WHERE user_id = ? AND key = ?",
            [user_id, key],
        )
        if existing:
            if strategy == "overwrite":
                await db.execute(
                    "UPDATE user_preferences SET value = ? WHERE user_id = ? AND key = ?",
                    [encoded, user_id, key],
                )
                replaced += 1
            else:
                skipped += 1
        else:
            try:
                await db.execute(
                    "INSERT INTO user_preferences (user_id, key, value) VALUES (?, ?, ?)",
                    [user_id, key, encoded],
                )
                imported += 1
            except Exception as exc:
                errors.append(f"Preference {key}: {exc}")

    return imported, skipped, replaced, errors


# ---------------------------------------------------------------------------
# Import endpoint
# ---------------------------------------------------------------------------


class ImportRequest(BaseModel):
    """Body for POST /api/data/import."""

    data: dict[str, Any]


@router.post("/import", response_model=ImportResult, summary="Import personal data from JSON")
async def import_data(
    payload: ImportRequest,
    only: str | None = Query(
        None,
        description="Section to import: workshops, inventory, preferences",
    ),
    strategy: ImportStrategy = Query(
        "additive",
        description="Conflict strategy: additive (default), overwrite, skip_conflicts",
    ),
    db: UserDB = Depends(get_userdb),
) -> ImportResult:
    """Import personal data from an export document.

    The `data` field must be a document produced by GET /api/data/export.
    By default, the import is additive — new items are added and existing items
    are skipped. Use `strategy=overwrite` to replace existing items.

    Module data import is not supported via this endpoint because modules may
    have complex schema constraints. Use each module's own import mechanism.
    """
    exported = payload.data
    sections = exported.get("sections", {})

    total_imported: dict[str, int] = {}
    total_skipped: dict[str, int] = {}
    total_replaced: dict[str, int] = {}
    all_errors: list[str] = []

    if (only is None or only == "workshops") and "workshops" in sections:
        imp, skp, rep, errs = await _import_workshops(db, sections["workshops"], strategy)
        total_imported["workshops"] = imp
        total_skipped["workshops"] = skp
        total_replaced["workshops"] = rep
        all_errors.extend(errs)

    if (only is None or only == "inventory") and "inventory" in sections:
        imp, skp, rep, errs = await _import_inventory(db, sections["inventory"], strategy)
        total_imported["inventory"] = imp
        total_skipped["inventory"] = skp
        total_replaced["inventory"] = rep
        all_errors.extend(errs)

    if (only is None or only == "preferences") and "preferences" in sections:
        imp, skp, rep, errs = await _import_preferences(db, sections["preferences"], strategy)
        total_imported["preferences"] = imp
        total_skipped["preferences"] = skp
        total_replaced["preferences"] = rep
        all_errors.extend(errs)

    if only is not None and only not in ("workshops", "inventory", "preferences"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"Unknown import section '{only}'",
                "suggestion": "Valid values: workshops, inventory, preferences",
            },
        )

    log.info(
        "data_imported",
        strategy=strategy,
        imported=total_imported,
        skipped=total_skipped,
        replaced=total_replaced,
        errors=len(all_errors),
    )

    return ImportResult(
        imported=total_imported,
        skipped=total_skipped,
        replaced=total_replaced,
        errors=all_errors,
    )
