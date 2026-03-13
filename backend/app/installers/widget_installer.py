"""Widget pack installer — registers a frontend-only keyword renderer bundle.

Install flow:
  1. Verify package type is 'widget-pack'.
  2. Register in installed_packages table.
  3. No restart required (frontend rebuild picks it up).

The actual frontend integration (copying components, triggering rebuild) happens
through the 'makestack rebuild-frontend' CLI command after install.
"""

from __future__ import annotations

import structlog

from ..userdb import UserDB
from .base import InstallResult

log = structlog.get_logger().bind(component="widget_installer")


class WidgetInstaller:
    """Installs and uninstalls widget pack packages."""

    def __init__(self, db: UserDB) -> None:
        self._db = db

    async def install(
        self,
        package_path: str,
        manifest,  # PackageManifest
        git_url: str | None = None,
        registry_name: str | None = None,
        module_registry=None,
        dry_run: bool = False,
    ) -> InstallResult:
        """Register a widget pack in installed_packages."""
        existing = await self._db.fetch_one(
            "SELECT name FROM installed_packages WHERE name = ?", [manifest.name]
        )
        if existing:
            await self._db.execute(
                """
                UPDATE installed_packages
                   SET version = ?, git_url = ?, package_path = ?, registry_name = ?
                 WHERE name = ?
                """,
                [manifest.version, git_url, package_path, registry_name, manifest.name],
            )
            action = "updated"
        else:
            await self._db.execute(
                """
                INSERT INTO installed_packages
                    (name, type, version, git_url, package_path, installed_at, registry_name)
                VALUES (?, 'widget-pack', ?, ?, ?, datetime('now'), ?)
                """,
                [manifest.name, manifest.version, git_url, package_path, registry_name],
            )
            action = "registered"

        log.info(
            "widget_pack_installed",
            name=manifest.name,
            version=manifest.version,
            action=action,
        )

        return InstallResult(
            success=True,
            package_name=manifest.name,
            package_type="widget-pack",
            version=manifest.version,
            restart_required=False,
            message=(
                f"Widget pack '{manifest.name}' {action}. "
                "Run 'makestack rebuild-frontend' to activate new keyword renderers."
            ),
        )

    async def uninstall(self, name: str) -> InstallResult:
        """Remove a widget pack registration."""
        row = await self._db.fetch_one(
            "SELECT version FROM installed_packages WHERE name = ? AND type = 'widget-pack'",
            [name],
        )
        if not row:
            return InstallResult(
                success=False,
                package_name=name,
                package_type="widget-pack",
                version="",
                message=f"Widget pack '{name}' is not installed.",
            )

        version = row["version"]
        await self._db.execute(
            "DELETE FROM installed_packages WHERE name = ? AND type = 'widget-pack'",
            [name],
        )

        log.info("widget_pack_uninstalled", name=name)
        return InstallResult(
            success=True,
            package_name=name,
            package_type="widget-pack",
            version=version,
            restart_required=False,
            message=(
                f"Widget pack '{name}' unregistered. "
                "Run 'makestack rebuild-frontend' to remove its keyword renderers."
            ),
        )
