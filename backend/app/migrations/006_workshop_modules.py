"""Migration 006 — create workshop_modules table.

Associates modules with workshops. The nav intersection rule reads this table
alongside app.state.module_registry — modules must appear in BOTH to show in nav.
Association rows are never removed by nav computation (intersection, not sync).
"""

ID = "006_workshop_modules"


async def up(conn) -> None:
    """Create workshop_modules table."""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workshop_modules (
            workshop_id TEXT NOT NULL REFERENCES workshops(id) ON DELETE CASCADE,
            module_name TEXT NOT NULL,
            sort_order  INTEGER DEFAULT 0,
            enabled     INTEGER DEFAULT 1,
            PRIMARY KEY (workshop_id, module_name)
        )
        """
    )
    await conn.commit()
