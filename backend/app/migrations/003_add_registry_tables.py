"""Migration 003: Registry and non-module package tracking tables.

Adds:
  - installed_registries  — configured Git-based package registries
  - installed_packages    — non-module installed packages (widget-packs,
                            catalogues, data). Modules stay in installed_modules.
"""

ID = "003_add_registry_tables"


async def up(conn) -> None:
    """Add registry and package tracking tables."""
    await conn.executescript(
        """
        -- Configured package registries.
        -- Each registry is a cloned Git repo in ~/.makestack/registries/{name}/.
        -- index.json in that repo maps package names to Git URLs.
        CREATE TABLE IF NOT EXISTS installed_registries (
            name           TEXT PRIMARY KEY,
            git_url        TEXT NOT NULL,
            added_at       TEXT NOT NULL,
            last_refreshed TEXT
        );

        -- Non-module installed packages (widget-packs, catalogues, data).
        -- Modules are tracked separately in installed_modules so that their
        -- migration lifecycle and enable/disable state remain self-contained.
        CREATE TABLE IF NOT EXISTS installed_packages (
            name           TEXT PRIMARY KEY,
            type           TEXT NOT NULL,
            version        TEXT NOT NULL,
            git_url        TEXT,
            package_path   TEXT,
            installed_at   TEXT NOT NULL,
            registry_name  TEXT
        );
        """
    )
    await conn.commit()
