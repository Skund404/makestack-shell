"""Migration without a down() function — should fail install validation."""

ID = "001_initial"


async def up(conn) -> None:
    """Create a table."""
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS missing_down_items (id TEXT PRIMARY KEY)"
    )
    await conn.commit()

# Note: no down() function defined — this is intentional for testing
