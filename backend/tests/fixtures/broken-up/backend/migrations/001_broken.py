"""Migration with a broken up() that raises an exception."""

ID = "001_broken"


async def up(conn) -> None:
    """This migration always fails."""
    raise RuntimeError("Intentional migration failure for testing")


async def down(conn) -> None:
    """Rollback (never reached since up() fails)."""
    pass
