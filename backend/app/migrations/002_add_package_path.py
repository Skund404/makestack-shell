"""Migration 002 — add package_path column to installed_modules.

package_path stores the filesystem path to the module directory.
Required for local-path module loading (dev mode and direct installs).

NULL means the module is installed as a Python package in the environment.
A path means the module is loaded from that directory (dev / direct install).
"""

ID = "002_add_package_path"


async def up(conn) -> None:
    """Add package_path column to installed_modules."""
    await conn.execute(
        "ALTER TABLE installed_modules ADD COLUMN package_path TEXT"
    )
    await conn.commit()
