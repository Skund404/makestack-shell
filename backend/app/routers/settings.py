"""Settings routes — user preferences and theme management.

All preferences are stored in UserDB as JSON-encoded key-value pairs.
"""

import json

import structlog
from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_userdb
from ..models import ThemeInfo, ThemeSet, UserPreferences
from ..userdb import UserDB

log = structlog.get_logger().bind(component="settings_router")

router = APIRouter(prefix="/api/settings", tags=["settings"])

_DEFAULT_USER_ID = "default"
_THEME_KEY = "active_theme"
_DEFAULT_THEME = "cyberpunk"


async def _get_prefs(db: UserDB) -> dict:
    """Read all preferences for the default user as a decoded dict."""
    rows = await db.fetch_all(
        "SELECT key, value FROM user_preferences WHERE user_id = ?",
        [_DEFAULT_USER_ID],
    )
    prefs: dict = {}
    for row in rows:
        try:
            prefs[row["key"]] = json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            prefs[row["key"]] = row["value"]
    return prefs


async def _set_pref(db: UserDB, key: str, value) -> None:
    """Upsert a single preference key for the default user."""
    await db.execute(
        """
        INSERT INTO user_preferences (user_id, key, value)
        VALUES (?, ?, ?)
        ON CONFLICT (user_id, key) DO UPDATE SET value = excluded.value
        """,
        [_DEFAULT_USER_ID, key, json.dumps(value)],
    )


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------


@router.get("", response_model=UserPreferences, summary="Get all settings")
async def get_settings(
    db: UserDB = Depends(get_userdb),
) -> UserPreferences:
    """Return all user preferences as a flat key-value map."""
    prefs = await _get_prefs(db)
    return UserPreferences(preferences=prefs)


@router.put("/preferences", response_model=UserPreferences, summary="Update user preferences")
async def update_preferences(
    payload: UserPreferences,
    db: UserDB = Depends(get_userdb),
) -> UserPreferences:
    """Merge the provided preferences into the stored set.

    Existing keys not present in the payload are unchanged.
    To clear a preference, set its value to null.
    """
    for key, value in payload.preferences.items():
        if value is None:
            await db.execute(
                "DELETE FROM user_preferences WHERE user_id = ? AND key = ?",
                [_DEFAULT_USER_ID, key],
            )
        else:
            await _set_pref(db, key, value)

    log.info("preferences_updated", keys=list(payload.preferences.keys()))
    prefs = await _get_prefs(db)
    return UserPreferences(preferences=prefs)


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------


@router.get("/theme", response_model=ThemeInfo, summary="Get active theme")
async def get_theme(
    db: UserDB = Depends(get_userdb),
) -> ThemeInfo:
    """Return the active theme name."""
    prefs = await _get_prefs(db)
    return ThemeInfo(name=str(prefs.get(_THEME_KEY, _DEFAULT_THEME)))


@router.put("/theme", response_model=ThemeInfo, summary="Switch theme")
async def set_theme(
    payload: ThemeSet,
    db: UserDB = Depends(get_userdb),
) -> ThemeInfo:
    """Switch the active theme (stored in user preferences)."""
    await _set_pref(db, _THEME_KEY, payload.name)
    log.info("theme_set", name=payload.name)
    return ThemeInfo(name=payload.name)
