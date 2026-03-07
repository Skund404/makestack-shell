"""Module installer — registers a module package into the Shell.

Install flow:
  1. Read manifest.json (module manifest from Phase 5) to verify it's valid.
  2. pip install declared Python dependencies.
  3. Register in installed_modules with package_path pointing to the cache dir.
  4. Mark restart_required=True (module routes mount at startup, not dynamically).

UserDB migrations are NOT run here — the module loader runs them at next startup.
This keeps the installer idempotent and independent of the loader internals.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import structlog

from ..userdb import UserDB
from .base import InstallResult

log = structlog.get_logger().bind(component="module_installer")


class ModuleInstaller:
    """Installs and uninstalls module packages."""

    def __init__(self, db: UserDB) -> None:
        self._db = db

    async def install(
        self,
        package_path: str,
        manifest,  # PackageManifest
        git_url: str | None = None,
        registry_name: str | None = None,
    ) -> InstallResult:
        """Register a module package and install its Python dependencies."""
        warnings: list[str] = []
        module_dir = Path(package_path)

        # Verify manifest.json exists (the module manifest, not the package one).
        module_manifest_path = module_dir / "manifest.json"
        if not module_manifest_path.exists():
            return InstallResult(
                success=False,
                package_name=manifest.name,
                package_type="module",
                version=manifest.version,
                message=(
                    f"manifest.json not found at {module_manifest_path}. "
                    "A module package must contain both makestack-package.json "
                    "and manifest.json."
                ),
            )

        # Validate the module manifest (basic JSON parse).
        try:
            raw_module_manifest = json.loads(
                module_manifest_path.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError) as exc:
            return InstallResult(
                success=False,
                package_name=manifest.name,
                package_type="module",
                version=manifest.version,
                message=f"manifest.json is not valid JSON: {exc}",
            )

        # Install Python dependencies declared in the module manifest.
        python_deps: list[str] = (
            raw_module_manifest.get("dependencies", {}).get("python", [])
        )
        if python_deps:
            dep_warnings = await self._pip_install(python_deps)
            warnings.extend(dep_warnings)

        # Register (or update) in installed_modules.
        existing = await self._db.fetch_one(
            "SELECT name FROM installed_modules WHERE name = ?", [manifest.name]
        )
        if existing:
            await self._db.execute(
                """
                UPDATE installed_modules
                   SET version = ?, enabled = 1, package_path = ?
                 WHERE name = ?
                """,
                [manifest.version, package_path, manifest.name],
            )
            action = "updated"
        else:
            await self._db.execute(
                """
                INSERT INTO installed_modules
                    (name, version, installed_at, enabled, package_path)
                VALUES (?, ?, datetime('now'), 1, ?)
                """,
                [manifest.name, manifest.version, package_path],
            )
            action = "registered"

        log.info(
            "module_installed",
            name=manifest.name,
            version=manifest.version,
            action=action,
            package_path=package_path,
        )

        return InstallResult(
            success=True,
            package_name=manifest.name,
            package_type="module",
            version=manifest.version,
            restart_required=True,
            message=(
                f"Module '{manifest.name}' {action} successfully. "
                "Restart the Shell to activate it."
            ),
            warnings=warnings,
        )

    async def uninstall(self, name: str) -> InstallResult:
        """Disable and de-register a module.

        Tables created by the module are NOT dropped — data persists.
        The package cache directory is managed separately by the route handler.
        """
        row = await self._db.fetch_one(
            "SELECT version FROM installed_modules WHERE name = ?", [name]
        )
        if not row:
            return InstallResult(
                success=False,
                package_name=name,
                package_type="module",
                version="",
                message=f"Module '{name}' is not installed.",
            )

        version = row["version"]
        await self._db.execute(
            "UPDATE installed_modules SET enabled = 0 WHERE name = ?", [name]
        )

        log.info("module_uninstalled", name=name)
        return InstallResult(
            success=True,
            package_name=name,
            package_type="module",
            version=version,
            restart_required=True,
            message=(
                f"Module '{name}' has been disabled. "
                "Module data tables are preserved. "
                "Restart the Shell to complete uninstallation."
            ),
        )

    # -------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------

    async def _pip_install(self, packages: list[str]) -> list[str]:
        """Install Python packages via pip. Returns a list of warning strings."""
        warnings: list[str] = []
        for pkg in packages:
            rc = await asyncio.to_thread(
                lambda p=pkg: subprocess.run(
                    ["pip", "install", p],
                    capture_output=True,
                ).returncode
            )
            if rc != 0:
                warnings.append(f"pip install {pkg!r} failed (exit {rc}).")
                log.warning("pip_install_failed", package=pkg, returncode=rc)
            else:
                log.info("pip_install_done", package=pkg)
        return warnings
