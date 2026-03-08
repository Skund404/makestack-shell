"""Migration 004 — extend users table with profile fields.

Adds bio, timezone, and locale to the users table for richer profile management.
These are nullable so existing rows remain valid without a backfill.
"""

ID = "004_user_profile"


async def up(conn) -> None:
    """Apply profile field additions."""

    # SQLite only supports ADD COLUMN, not multi-column ALTER in one statement.
    for col, definition in [
        ("bio",      "TEXT DEFAULT ''"),
        ("timezone", "TEXT DEFAULT 'UTC'"),
        ("locale",   "TEXT DEFAULT 'en'"),
    ]:
        # Ignore if the column already exists (idempotent).
        try:
            await conn.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
        except Exception:
            pass  # Column already present — safe to continue.

    await conn.commit()
