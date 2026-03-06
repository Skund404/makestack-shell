"""Inventory routes — personal hash-pointer references to catalogue entries.

Inventory records live entirely in UserDB. They reference catalogue entries
via immutable Git commit hashes, never by copying catalogue data.
"""

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException

from ..core_client import CatalogueClient, CoreNotFoundError, CoreUnavailableError
from ..dependencies import get_core_client, get_userdb
from ..models import (
    InventoryCreate,
    InventoryItem,
    InventoryItemWithCatalogue,
    InventoryUpdate,
    PaginatedList,
    Primitive,
)
from ..userdb import UserDB

log = structlog.get_logger().bind(component="inventory_router")

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_item(row: dict) -> InventoryItem:
    return InventoryItem(
        id=row["id"],
        catalogue_path=row["catalogue_path"],
        catalogue_hash=row["catalogue_hash"],
        primitive_type=row["primitive_type"],
        workshop_id=row["workshop_id"],
        added_at=row["added_at"],
        updated_at=row["updated_at"],
    )


# ---------------------------------------------------------------------------
# Stale check (must be declared before /{id} to avoid routing collision)
# ---------------------------------------------------------------------------


@router.get(
    "/stale",
    response_model=PaginatedList[InventoryItemWithCatalogue],
    summary="List stale inventory items",
)
async def list_stale_inventory(
    limit: int = 50,
    offset: int = 0,
    db: UserDB = Depends(get_userdb),
    core: CatalogueClient = Depends(get_core_client),
) -> PaginatedList[InventoryItemWithCatalogue]:
    """List inventory items where the catalogue has been updated since the hash was pinned.

    Calls Core once per item to check the current hash. For large inventories
    this can be slow; caching will be added in a later phase.
    """
    all_rows = await db.fetch_all("SELECT * FROM inventory ORDER BY added_at DESC")
    stale: list[InventoryItemWithCatalogue] = []

    for row in all_rows:
        try:
            current_hash = await core.get_commit_hash(row["catalogue_path"])
        except (CoreUnavailableError, CoreNotFoundError):
            continue
        if current_hash != row["catalogue_hash"]:
            item = _row_to_item(row)
            stale.append(
                InventoryItemWithCatalogue(
                    **item.model_dump(),
                    is_stale=True,
                    current_hash=current_hash,
                )
            )

    total = len(stale)
    page = stale[offset : offset + limit]
    return PaginatedList(items=page, total=total, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=PaginatedList[InventoryItem],
    summary="List inventory items",
)
async def list_inventory(
    workshop_id: str | None = None,
    type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: UserDB = Depends(get_userdb),
) -> PaginatedList[InventoryItem]:
    """List personal inventory items. Optionally filter by workshop or primitive type."""
    conditions: list[str] = []
    params: list = []

    if workshop_id:
        conditions.append("workshop_id = ?")
        params.append(workshop_id)
    if type:
        conditions.append("primitive_type = ?")
        params.append(type)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    total = await db.count("inventory", " AND ".join(conditions) if conditions else "", params)
    rows = await db.fetch_all(
        f"SELECT * FROM inventory {where} ORDER BY added_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    )
    return PaginatedList(
        items=[_row_to_item(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Get single item with resolved catalogue data
# ---------------------------------------------------------------------------


@router.get(
    "/{item_id}",
    response_model=InventoryItemWithCatalogue,
    summary="Get inventory item with resolved catalogue data",
)
async def get_inventory_item(
    item_id: str,
    db: UserDB = Depends(get_userdb),
    core: CatalogueClient = Depends(get_core_client),
) -> InventoryItemWithCatalogue:
    """Get a single inventory item enriched with its pinned catalogue data.

    Returns the catalogue entry as it was at the stored hash, plus a staleness
    flag indicating whether the catalogue has since been updated.
    """
    row = await db.fetch_one("SELECT * FROM inventory WHERE id = ?", [item_id])
    if not row:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Inventory item not found",
                "item_id": item_id,
                "suggestion": "Use GET /api/inventory to list available items",
            },
        )

    item = _row_to_item(row)
    catalogue_data: Primitive | None = None
    current_hash: str | None = None
    is_stale = False

    try:
        catalogue_data = await core.get_primitive_at_version(item.catalogue_path, item.catalogue_hash)
        current_hash = await core.get_commit_hash(item.catalogue_path)
        is_stale = current_hash != item.catalogue_hash
    except CoreUnavailableError:
        log.warning("core_unavailable_for_inventory_resolve", item_id=item_id)
    except CoreNotFoundError:
        log.warning("catalogue_entry_missing", path=item.catalogue_path, hash=item.catalogue_hash)

    return InventoryItemWithCatalogue(
        **item.model_dump(),
        catalogue_data=catalogue_data,
        is_stale=is_stale,
        current_hash=current_hash,
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=InventoryItem,
    status_code=201,
    summary="Add a catalogue item to inventory",
)
async def add_to_inventory(
    payload: InventoryCreate,
    db: UserDB = Depends(get_userdb),
    core: CatalogueClient = Depends(get_core_client),
) -> InventoryItem:
    """Add a catalogue entry to personal inventory.

    Resolves the current commit hash for the given path and stores it as an
    immutable reference. Future staleness checks compare against this hash.
    """
    # Verify the catalogue entry exists and fetch its current hash.
    try:
        primitive = await core.get_primitive(payload.catalogue_path)
        catalogue_hash = await core.get_commit_hash(payload.catalogue_path)
    except CoreUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Catalogue unavailable",
                "detail": "Cannot resolve catalogue path — Core is not connected",
                "suggestion": f"Check that makestack-core is running at {exc.url}",
            },
        )
    except CoreNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Catalogue entry not found",
                "path": payload.catalogue_path,
                "suggestion": "Use GET /api/catalogue/search to find the correct path",
            },
        )

    # Validate workshop exists if provided.
    if payload.workshop_id:
        ws = await db.fetch_one("SELECT id FROM workshops WHERE id = ?", [payload.workshop_id])
        if not ws:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Workshop not found",
                    "workshop_id": payload.workshop_id,
                    "suggestion": "Use GET /api/workshops to list available workshops",
                },
            )

    now = _now()
    item_id = str(uuid.uuid4())

    row = await db.execute_returning(
        """
        INSERT INTO inventory (id, catalogue_path, catalogue_hash, primitive_type, workshop_id, added_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        RETURNING *
        """,
        [item_id, payload.catalogue_path, catalogue_hash, primitive.type, payload.workshop_id, now, now],
    )

    log.info("inventory_item_added", id=item_id, path=payload.catalogue_path, hash=catalogue_hash)
    return _row_to_item(row)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@router.put(
    "/{item_id}",
    response_model=InventoryItem,
    summary="Update an inventory item",
)
async def update_inventory_item(
    item_id: str,
    payload: InventoryUpdate,
    db: UserDB = Depends(get_userdb),
    core: CatalogueClient = Depends(get_core_client),
) -> InventoryItem:
    """Update an inventory item.

    Supports changing the associated workshop and updating the pinned catalogue
    hash (e.g. after reviewing a diff and accepting the new version).
    """
    row = await db.fetch_one("SELECT * FROM inventory WHERE id = ?", [item_id])
    if not row:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Inventory item not found",
                "item_id": item_id,
                "suggestion": "Use GET /api/inventory to list available items",
            },
        )

    updates: dict = {}

    if payload.workshop_id is not None:
        if payload.workshop_id:
            ws = await db.fetch_one("SELECT id FROM workshops WHERE id = ?", [payload.workshop_id])
            if not ws:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "Workshop not found",
                        "workshop_id": payload.workshop_id,
                        "suggestion": "Use GET /api/workshops to list available workshops",
                    },
                )
        updates["workshop_id"] = payload.workshop_id or None

    if payload.catalogue_hash is not None:
        # Validate the hash exists in the catalogue.
        try:
            await core.get_primitive_at_version(row["catalogue_path"], payload.catalogue_hash)
        except CoreUnavailableError as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "Catalogue unavailable",
                    "detail": "Cannot validate new hash — Core is not connected",
                    "suggestion": f"Check that makestack-core is running at {exc.url}",
                },
            )
        except CoreNotFoundError:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Commit hash not found",
                    "catalogue_hash": payload.catalogue_hash,
                    "suggestion": "Use GET /api/catalogue/primitives/{path}/history to browse available versions",
                },
            )
        updates["catalogue_hash"] = payload.catalogue_hash

    if not updates:
        return _row_to_item(row)

    updates["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [item_id]
    updated = await db.execute_returning(
        f"UPDATE inventory SET {set_clause} WHERE id = ? RETURNING *",  # noqa: S608
        values,
    )
    log.info("inventory_item_updated", id=item_id, fields=list(updates.keys()))
    return _row_to_item(updated)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete(
    "/{item_id}",
    status_code=204,
    summary="Remove an item from inventory",
)
async def delete_inventory_item(
    item_id: str,
    db: UserDB = Depends(get_userdb),
) -> None:
    """Remove a personal inventory record. Does not touch the catalogue."""
    row = await db.fetch_one("SELECT id FROM inventory WHERE id = ?", [item_id])
    if not row:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Inventory item not found",
                "item_id": item_id,
                "suggestion": "Use GET /api/inventory to list available items",
            },
        )
    await db.execute("DELETE FROM inventory WHERE id = ?", [item_id])
    log.info("inventory_item_deleted", id=item_id)
