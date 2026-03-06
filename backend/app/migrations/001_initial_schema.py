"""Initial Shell schema — all core UserDB tables.

Creates the full personal-state schema including users, preferences,
workshops, inventory, and module tracking tables.
"""

ID = "001_initial_schema"


async def up(conn) -> None:
    """Apply the initial schema."""

    await conn.executescript(
        """
        -- User identity (single-user for v0; schema supports multi-user later)
        CREATE TABLE IF NOT EXISTS users (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            avatar_path TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );

        -- Key-value preferences per user (values are JSON-encoded)
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            key     TEXT NOT NULL,
            value   TEXT NOT NULL,
            PRIMARY KEY (user_id, key)
        );

        -- Workshops: schema-free organisational containers
        CREATE TABLE IF NOT EXISTS workshops (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            slug        TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            icon        TEXT DEFAULT '',
            color       TEXT DEFAULT '',
            sort_order  INTEGER DEFAULT 0,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );

        -- Which catalogue primitives belong to which workshop
        CREATE TABLE IF NOT EXISTS workshop_members (
            workshop_id    TEXT NOT NULL REFERENCES workshops(id) ON DELETE CASCADE,
            primitive_path TEXT NOT NULL,
            primitive_type TEXT NOT NULL,
            added_at       TEXT NOT NULL,
            PRIMARY KEY (workshop_id, primitive_path)
        );

        -- Inventory: hash-pointer references into the catalogue
        CREATE TABLE IF NOT EXISTS inventory (
            id             TEXT PRIMARY KEY,
            catalogue_path TEXT NOT NULL,
            catalogue_hash TEXT NOT NULL,
            primitive_type TEXT NOT NULL,
            workshop_id    TEXT REFERENCES workshops(id) ON DELETE SET NULL,
            added_at       TEXT NOT NULL,
            updated_at     TEXT NOT NULL
        );

        -- Registered modules and their enabled state
        CREATE TABLE IF NOT EXISTS installed_modules (
            name           TEXT PRIMARY KEY,
            version        TEXT NOT NULL,
            installed_at   TEXT NOT NULL,
            enabled        INTEGER NOT NULL DEFAULT 1,
            last_migration TEXT
        );

        -- Applied migrations per module
        CREATE TABLE IF NOT EXISTS module_migrations (
            module_name  TEXT NOT NULL REFERENCES installed_modules(name) ON DELETE CASCADE,
            migration_id TEXT NOT NULL,
            applied_at   TEXT NOT NULL,
            PRIMARY KEY (module_name, migration_id)
        );
        """
    )

    # Seed the default user for v0 (single-user mode).
    await conn.execute(
        """
        INSERT OR IGNORE INTO users (id, name, created_at, updated_at)
        VALUES ('default', 'Maker', datetime('now'), datetime('now'))
        """
    )
    await conn.commit()
