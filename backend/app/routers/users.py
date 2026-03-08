"""User account management routes.

Provides profile read/write and a stats summary for the current user.
The Shell is single-user for v0 — all operations apply to user id "default".

Routes:
  GET  /api/users/me         → current user profile
  PUT  /api/users/me         → update profile fields
  GET  /api/users/me/stats   → activity summary (workshops, inventory, modules)
"""

import json
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_userdb
from ..models import UserProfile, UserProfileUpdate, UserStats
from ..userdb import UserDB

log = structlog.get_logger().bind(component="users_router")

router = APIRouter(prefix="/api/users", tags=["users"])

_DEFAULT_USER_ID = "default"
_ACTIVE_WORKSHOP_PREF = "active_workshop_id"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_user_row(db: UserDB) -> dict:
    """Return the default user row or raise 404."""
    row = await db.fetch_one("SELECT * FROM users WHERE id = ?", [_DEFAULT_USER_ID])
    if not row:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "User not found",
                "user_id": _DEFAULT_USER_ID,
                "suggestion": "The UserDB may not have been initialised — restart the Shell.",
            },
        )
    return row


async def _get_active_workshop_pref(db: UserDB) -> str | None:
    """Return the raw active_workshop_id preference value (or None)."""
    row = await db.fetch_one(
        "SELECT value FROM user_preferences WHERE user_id = ? AND key = ?",
        [_DEFAULT_USER_ID, _ACTIVE_WORKSHOP_PREF],
    )
    if row:
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _row_to_profile(row: dict) -> UserProfile:
    """Convert a users table row to a UserProfile model."""
    return UserProfile(
        id=row["id"],
        name=row["name"],
        avatar_path=row.get("avatar_path"),
        bio=row.get("bio") or "",
        timezone=row.get("timezone") or "UTC",
        locale=row.get("locale") or "en",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ---------------------------------------------------------------------------
# Profile endpoints
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserProfile, summary="Get current user profile")
async def get_profile(
    db: UserDB = Depends(get_userdb),
) -> UserProfile:
    """Return the current user's profile information.

    In v0 this always returns the single "default" user.
    """
    row = await _get_user_row(db)
    return _row_to_profile(row)


@router.put("/me", response_model=UserProfile, summary="Update current user profile")
async def update_profile(
    payload: UserProfileUpdate,
    db: UserDB = Depends(get_userdb),
) -> UserProfile:
    """Update one or more profile fields for the current user.

    Only fields included in the request body are changed; omitted fields
    are left as-is.  An empty string is a valid value (clears the field).
    """
    # Make sure the user row exists.
    current = await _get_user_row(db)

    # Build SET clause dynamically from provided fields.
    updates: dict[str, object] = {}
    if payload.name is not None:
        if not payload.name.strip():
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "Validation error",
                    "field": "name",
                    "message": "Name must not be blank.",
                    "suggestion": "Provide a non-empty name string.",
                },
            )
        updates["name"] = payload.name.strip()

    if payload.avatar_path is not None:
        updates["avatar_path"] = payload.avatar_path or None  # empty → NULL

    if payload.bio is not None:
        updates["bio"] = payload.bio

    if payload.timezone is not None:
        updates["timezone"] = payload.timezone or "UTC"

    if payload.locale is not None:
        updates["locale"] = payload.locale or "en"

    if not updates:
        # Nothing to change — return current profile unchanged.
        return _row_to_profile(current)

    now = datetime.now(timezone.utc).isoformat()
    updates["updated_at"] = now

    set_clause = ", ".join(f"{col} = ?" for col in updates)
    values = list(updates.values()) + [_DEFAULT_USER_ID]

    await db.execute(
        f"UPDATE users SET {set_clause} WHERE id = ?",
        values,
    )
    log.info("profile_updated", fields=list(updates.keys()))

    updated = await _get_user_row(db)
    return _row_to_profile(updated)


# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------


@router.get("/me/stats", response_model=UserStats, summary="Get current user activity stats")
async def get_stats(
    db: UserDB = Depends(get_userdb),
) -> UserStats:
    """Return an activity summary for the current user.

    Includes counts of workshops, inventory items (total + stale candidates),
    installed modules, and active workshop context.
    """
    workshops_count = await db.count("workshops", where=None, params=[])
    inventory_count = await db.count("inventory", where=None, params=[])
    modules_installed = await db.count("installed_modules", where=None, params=[])
    modules_enabled = await db.count(
        "installed_modules", where="enabled = 1", params=[]
    )

    # Stale inventory: any row where catalogue_hash is not NULL (a rough proxy;
    # true staleness requires a Core round-trip — we report count only here).
    # We count items that have ever been updated (updated_at != added_at) as a
    # lightweight signal without hitting Core.
    stale_row = await db.fetch_one(
        "SELECT COUNT(*) AS cnt FROM inventory WHERE updated_at != added_at",
        [],
    )
    stale_inventory_count = stale_row["cnt"] if stale_row else 0

    # Active workshop
    active_workshop_id = await _get_active_workshop_pref(db)
    active_workshop_name: str | None = None
    if active_workshop_id:
        ws_row = await db.fetch_one(
            "SELECT name FROM workshops WHERE id = ?",
            [active_workshop_id],
        )
        if ws_row:
            active_workshop_name = ws_row["name"]
        else:
            # Preference references a deleted workshop — treat as unset.
            active_workshop_id = None

    return UserStats(
        workshops_count=workshops_count,
        inventory_count=inventory_count,
        stale_inventory_count=stale_inventory_count,
        modules_installed=modules_installed,
        modules_enabled=modules_enabled,
        active_workshop_id=active_workshop_id,
        active_workshop_name=active_workshop_name,
    )
