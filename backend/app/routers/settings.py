"""Settings routes — user preferences and theme management.

All preferences are stored in UserDB as JSON-encoded key-value pairs.
"""

import json

import structlog
from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_userdb
from ..models import ThemeData, ThemeInfo, ThemeSet, UserPreferences
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


_BUILTIN_THEMES: dict[str, dict[str, str]] = {
    "cyberpunk": {
        "--ms-bg":             "#09090f",
        "--ms-bg-secondary":   "#11111e",
        "--ms-surface":        "#16162a",
        "--ms-surface-el":     "#1e1e38",
        "--ms-accent":         "#00e5ff",
        "--ms-accent-dim":     "rgba(0, 229, 255, 0.12)",
        "--ms-accent-border":  "rgba(0, 229, 255, 0.25)",
        "--ms-purple":         "#bf5fff",
        "--ms-text":           "#e2e8f0",
        "--ms-text-muted":     "#8892aa",
        "--ms-text-faint":     "#4a5168",
        "--ms-border":         "#1a1a30",
        "--ms-border-bright":  "#2a2d4a",
        "--ms-success":        "#00e676",
        "--ms-warning":        "#ffd600",
        "--ms-danger":         "#ff1744",
        "--ms-radius":         "0.375rem",
    },
    "workshop": {
        "--ms-bg":             "#1a1210",
        "--ms-bg-secondary":   "#221a16",
        "--ms-surface":        "#2a2018",
        "--ms-surface-el":     "#342820",
        "--ms-accent":         "#ff9800",
        "--ms-accent-dim":     "rgba(255, 152, 0, 0.12)",
        "--ms-accent-border":  "rgba(255, 152, 0, 0.25)",
        "--ms-purple":         "#ce93d8",
        "--ms-text":           "#ede0d4",
        "--ms-text-muted":     "#a08070",
        "--ms-text-faint":     "#5a4038",
        "--ms-border":         "#2e2018",
        "--ms-border-bright":  "#3e3028",
        "--ms-success":        "#66bb6a",
        "--ms-warning":        "#ffa726",
        "--ms-danger":         "#ef5350",
        "--ms-radius":         "0.25rem",
    },
    "daylight": {
        "--ms-bg":             "#f8f9fa",
        "--ms-bg-secondary":   "#f1f3f5",
        "--ms-surface":        "#ffffff",
        "--ms-surface-el":     "#ffffff",
        "--ms-accent":         "#0066cc",
        "--ms-accent-dim":     "rgba(0, 102, 204, 0.08)",
        "--ms-accent-border":  "rgba(0, 102, 204, 0.2)",
        "--ms-purple":         "#7b3fe4",
        "--ms-text":           "#1a1a2e",
        "--ms-text-muted":     "#5a6070",
        "--ms-text-faint":     "#9aa0b0",
        "--ms-border":         "#dde1e7",
        "--ms-border-bright":  "#c8ced8",
        "--ms-success":        "#1a7f37",
        "--ms-warning":        "#9a6700",
        "--ms-danger":         "#cf222e",
        "--ms-radius":         "0.5rem",
    },
    "high-contrast": {
        "--ms-bg":             "#000000",
        "--ms-bg-secondary":   "#0a0a0a",
        "--ms-surface":        "#141414",
        "--ms-surface-el":     "#1e1e1e",
        "--ms-accent":         "#ffff00",
        "--ms-accent-dim":     "rgba(255, 255, 0, 0.15)",
        "--ms-accent-border":  "rgba(255, 255, 0, 0.5)",
        "--ms-purple":         "#ff80ff",
        "--ms-text":           "#ffffff",
        "--ms-text-muted":     "#cccccc",
        "--ms-text-faint":     "#888888",
        "--ms-border":         "#333333",
        "--ms-border-bright":  "#555555",
        "--ms-success":        "#00ff00",
        "--ms-warning":        "#ffff00",
        "--ms-danger":         "#ff0000",
        "--ms-radius":         "0",
    },
}


@router.get("/theme/data", response_model=ThemeData, summary="Get active theme data (CSS variables)")
async def get_theme_data(
    db: UserDB = Depends(get_userdb),
) -> ThemeData:
    """Return the full CSS variable set for the active theme.

    The frontend theme loader calls this endpoint on startup and injects
    the variables as CSS custom properties on :root.
    """
    prefs = await _get_prefs(db)
    name = str(prefs.get(_THEME_KEY, _DEFAULT_THEME))
    variables = _BUILTIN_THEMES.get(name, _BUILTIN_THEMES[_DEFAULT_THEME])
    return ThemeData(name=name, variables=variables)


@router.put("/theme", response_model=ThemeInfo, summary="Switch theme")
async def set_theme(
    payload: ThemeSet,
    db: UserDB = Depends(get_userdb),
) -> ThemeInfo:
    """Switch the active theme (stored in user preferences)."""
    await _set_pref(db, _THEME_KEY, payload.name)
    log.info("theme_set", name=payload.name)
    return ThemeInfo(name=payload.name)
