"""Workshop routes — CRUD for user-defined organisational containers.

Workshops are pure UserDB operations. Core is never involved.
"""

import re
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi import Path as FPath

from ..dependencies import get_userdb
from ..models import (
    ActiveWorkshopSet,
    PaginatedList,
    Workshop,
    WorkshopCreate,
    WorkshopMember,
    WorkshopMemberAdd,
    WorkshopUpdate,
    WorkshopWithMembers,
)
from ..userdb import UserDB

log = structlog.get_logger().bind(component="workshops_router")

router = APIRouter(prefix="/api/workshops", tags=["workshops"])

_DEFAULT_USER_ID = "default"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(name: str) -> str:
    """Convert a name to a URL-safe slug (lowercase, hyphens, trimmed)."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "workshop"


def _row_to_workshop(row: dict) -> Workshop:
    return Workshop(
        id=row["id"],
        name=row["name"],
        slug=row["slug"],
        description=row["description"] or "",
        icon=row["icon"] or "",
        color=row["color"] or "",
        sort_order=row["sort_order"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def _get_or_404(workshop_id: str, db: UserDB) -> dict:
    row = await db.fetch_one("SELECT * FROM workshops WHERE id = ?", [workshop_id])
    if not row:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Workshop not found",
                "workshop_id": workshop_id,
                "suggestion": "Use GET /api/workshops to list available workshops",
            },
        )
    return row


# ---------------------------------------------------------------------------
# Active workshop (declared before /{id} to prevent routing collision)
# ---------------------------------------------------------------------------


@router.put("/active", summary="Set the active workshop context")
async def set_active_workshop(
    payload: ActiveWorkshopSet,
    db: UserDB = Depends(get_userdb),
) -> dict:
    """Set or clear the active workshop context for the default user.

    Stored as a user preference under the key ``active_workshop_id``.
    """
    import json

    if payload.workshop_id:
        await _get_or_404(payload.workshop_id, db)

    value = json.dumps(payload.workshop_id)
    await db.execute(
        """
        INSERT INTO user_preferences (user_id, key, value)
        VALUES (?, 'active_workshop_id', ?)
        ON CONFLICT (user_id, key) DO UPDATE SET value = excluded.value
        """,
        [_DEFAULT_USER_ID, value],
    )
    log.info("active_workshop_set", workshop_id=payload.workshop_id)
    return {"active_workshop_id": payload.workshop_id}


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedList[Workshop], summary="List workshops")
async def list_workshops(
    limit: int = 50,
    offset: int = 0,
    db: UserDB = Depends(get_userdb),
) -> PaginatedList[Workshop]:
    """List all workshops ordered by sort_order then name."""
    total = await db.count("workshops")
    rows = await db.fetch_all(
        "SELECT * FROM workshops ORDER BY sort_order ASC, name ASC LIMIT ? OFFSET ?",
        [limit, offset],
    )
    return PaginatedList(
        items=[_row_to_workshop(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Get single workshop with members
# ---------------------------------------------------------------------------


@router.get("/{workshop_id}", response_model=WorkshopWithMembers, summary="Get a workshop")
async def get_workshop(
    workshop_id: str = FPath(...),
    db: UserDB = Depends(get_userdb),
) -> WorkshopWithMembers:
    """Get a single workshop with its full primitive member list."""
    row = await _get_or_404(workshop_id, db)
    member_rows = await db.fetch_all(
        "SELECT * FROM workshop_members WHERE workshop_id = ? ORDER BY added_at ASC",
        [workshop_id],
    )
    members = [
        WorkshopMember(
            primitive_path=m["primitive_path"],
            primitive_type=m["primitive_type"],
            added_at=m["added_at"],
        )
        for m in member_rows
    ]
    ws = _row_to_workshop(row)
    return WorkshopWithMembers(**ws.model_dump(), members=members)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@router.post("", response_model=Workshop, status_code=201, summary="Create a workshop")
async def create_workshop(
    payload: WorkshopCreate,
    db: UserDB = Depends(get_userdb),
) -> Workshop:
    """Create a new workshop. Slug is auto-generated from the name."""
    now = _now()
    workshop_id = str(uuid.uuid4())
    base_slug = _slugify(payload.name)

    # Ensure slug uniqueness: append a short UUID suffix if needed.
    slug = base_slug
    existing = await db.fetch_one("SELECT id FROM workshops WHERE slug = ?", [slug])
    if existing:
        slug = f"{base_slug}-{workshop_id[:8]}"

    row = await db.execute_returning(
        """
        INSERT INTO workshops (id, name, slug, description, icon, color, sort_order, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
        RETURNING *
        """,
        [
            workshop_id,
            payload.name,
            slug,
            payload.description,
            payload.icon,
            payload.color,
            now,
            now,
        ],
    )
    log.info("workshop_created", id=workshop_id, name=payload.name)
    return _row_to_workshop(row)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@router.put("/{workshop_id}", response_model=Workshop, summary="Update a workshop")
async def update_workshop(
    workshop_id: str = FPath(...),
    payload: WorkshopUpdate = ...,
    db: UserDB = Depends(get_userdb),
) -> Workshop:
    """Update workshop fields. Only provided fields are updated."""
    await _get_or_404(workshop_id, db)

    updates: dict = {}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.description is not None:
        updates["description"] = payload.description
    if payload.icon is not None:
        updates["icon"] = payload.icon
    if payload.color is not None:
        updates["color"] = payload.color
    if payload.sort_order is not None:
        updates["sort_order"] = payload.sort_order

    if not updates:
        row = await db.fetch_one("SELECT * FROM workshops WHERE id = ?", [workshop_id])
        return _row_to_workshop(row)  # type: ignore[arg-type]

    updates["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [workshop_id]
    updated = await db.execute_returning(
        f"UPDATE workshops SET {set_clause} WHERE id = ? RETURNING *",  # noqa: S608
        values,
    )
    log.info("workshop_updated", id=workshop_id, fields=list(updates.keys()))
    return _row_to_workshop(updated)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete("/{workshop_id}", status_code=204, summary="Delete a workshop")
async def delete_workshop(
    workshop_id: str = FPath(...),
    db: UserDB = Depends(get_userdb),
) -> None:
    """Delete a workshop. Members are removed by CASCADE; primitives are unaffected."""
    await _get_or_404(workshop_id, db)
    await db.execute("DELETE FROM workshops WHERE id = ?", [workshop_id])
    log.info("workshop_deleted", id=workshop_id)


# ---------------------------------------------------------------------------
# Members — add / remove
# ---------------------------------------------------------------------------


@router.post(
    "/{workshop_id}/members",
    response_model=WorkshopMember,
    status_code=201,
    summary="Add a primitive to a workshop",
)
async def add_member(
    workshop_id: str = FPath(...),
    payload: WorkshopMemberAdd = ...,
    db: UserDB = Depends(get_userdb),
) -> WorkshopMember:
    """Add a catalogue primitive reference to a workshop.

    Idempotent — if the primitive is already a member, returns the existing record.
    """
    await _get_or_404(workshop_id, db)

    existing = await db.fetch_one(
        "SELECT * FROM workshop_members WHERE workshop_id = ? AND primitive_path = ?",
        [workshop_id, payload.primitive_path],
    )
    if existing:
        return WorkshopMember(
            primitive_path=existing["primitive_path"],
            primitive_type=existing["primitive_type"],
            added_at=existing["added_at"],
        )

    now = _now()
    await db.execute(
        """
        INSERT INTO workshop_members (workshop_id, primitive_path, primitive_type, added_at)
        VALUES (?, ?, ?, ?)
        """,
        [workshop_id, payload.primitive_path, payload.primitive_type, now],
    )
    log.info("workshop_member_added", workshop_id=workshop_id, path=payload.primitive_path)
    return WorkshopMember(
        primitive_path=payload.primitive_path,
        primitive_type=payload.primitive_type,
        added_at=now,
    )


@router.delete(
    "/{workshop_id}/members/{path:path}",
    status_code=204,
    summary="Remove a primitive from a workshop",
)
async def remove_member(
    workshop_id: str = FPath(...),
    path: str = FPath(...),
    db: UserDB = Depends(get_userdb),
) -> None:
    """Remove a primitive reference from a workshop. Does not delete the primitive."""
    await _get_or_404(workshop_id, db)
    member = await db.fetch_one(
        "SELECT workshop_id FROM workshop_members WHERE workshop_id = ? AND primitive_path = ?",
        [workshop_id, path],
    )
    if not member:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Member not found",
                "workshop_id": workshop_id,
                "primitive_path": path,
                "suggestion": "Use GET /api/workshops/{id} to see the member list",
            },
        )
    await db.execute(
        "DELETE FROM workshop_members WHERE workshop_id = ? AND primitive_path = ?",
        [workshop_id, path],
    )
    log.info("workshop_member_removed", workshop_id=workshop_id, path=path)
