"""Catalogue installer — imports primitives from a catalogue package into Core.

Install flow:
  1. Verify package type is 'catalogue'.
  2. Scan the package directory for primitive manifests (*/manifest.json).
  3. POST each primitive to Core via the CatalogueClient.
  4. Report: N imported, M skipped (already exist), K failed.
  5. No restart required.

A catalogue package is a Git repo whose root contains primitive directories
(tools/, materials/, techniques/, workflows/, projects/, events/) each
containing manifest.json files.
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from ..core_client import CatalogueClient
from ..userdb import UserDB
from .base import InstallResult

log = structlog.get_logger().bind(component="catalogue_installer")

_PRIMITIVE_TYPES = frozenset({
    "tools", "materials", "techniques", "workflows", "projects", "events"
})


class CatalogueInstaller:
    """Installs catalogue packages by importing primitives into Core."""

    def __init__(self, db: UserDB, core: CatalogueClient) -> None:
        self._db = db
        self._core = core

    async def install(
        self,
        package_path: str,
        manifest,  # PackageManifest
        git_url: str | None = None,
        registry_name: str | None = None,
    ) -> InstallResult:
        """Scan the catalogue package and POST all primitives to Core."""
        warnings: list[str] = []
        package_dir = Path(package_path)

        if not self._core.connected:
            return InstallResult(
                success=False,
                package_name=manifest.name,
                package_type="catalogue",
                version=manifest.version,
                message=(
                    "Core is not connected. "
                    "Catalogue packages require Core to be running to import primitives."
                ),
            )

        # Collect all manifest.json files under primitive-type directories.
        primitive_files = self._find_primitives(package_dir)

        if not primitive_files:
            return InstallResult(
                success=True,
                package_name=manifest.name,
                package_type="catalogue",
                version=manifest.version,
                message=(
                    f"No primitives found in catalogue '{manifest.name}'. "
                    "Expected subdirectories: tools/, materials/, techniques/, "
                    "workflows/, projects/, events/"
                ),
                warnings=["Catalogue appears to be empty."],
            )

        imported = 0
        skipped = 0
        failed = 0

        for primitive_file in primitive_files:
            try:
                raw = json.loads(primitive_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                warnings.append(f"Skipped {primitive_file.parent.name}/manifest.json: {exc}")
                failed += 1
                continue

            try:
                await self._core.create_primitive(raw)
                imported += 1
                log.debug("primitive_imported", path=str(primitive_file))
            except Exception as exc:
                err_str = str(exc)
                # 409 Conflict = already exists, skip gracefully.
                if "409" in err_str or "already exists" in err_str.lower():
                    skipped += 1
                else:
                    warnings.append(
                        f"Failed to import {primitive_file.parent.name}: {err_str}"
                    )
                    failed += 1

        # Register in installed_packages for tracking.
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
        else:
            await self._db.execute(
                """
                INSERT INTO installed_packages
                    (name, type, version, git_url, package_path, installed_at, registry_name)
                VALUES (?, 'catalogue', ?, ?, ?, datetime('now'), ?)
                """,
                [manifest.name, manifest.version, git_url, package_path, registry_name],
            )

        log.info(
            "catalogue_installed",
            name=manifest.name,
            imported=imported,
            skipped=skipped,
            failed=failed,
        )

        return InstallResult(
            success=True,
            package_name=manifest.name,
            package_type="catalogue",
            version=manifest.version,
            restart_required=False,
            message=(
                f"Catalogue '{manifest.name}' imported: "
                f"{imported} added, {skipped} already existed, {failed} failed."
            ),
            warnings=warnings,
        )

    async def uninstall(self, name: str) -> InstallResult:
        """Remove a catalogue registration.

        This does NOT delete imported primitives from Core — that would require
        individual DELETE calls and could destroy data the user has modified.
        """
        row = await self._db.fetch_one(
            "SELECT version FROM installed_packages WHERE name = ? AND type = 'catalogue'",
            [name],
        )
        if not row:
            return InstallResult(
                success=False,
                package_name=name,
                package_type="catalogue",
                version="",
                message=f"Catalogue '{name}' is not installed.",
            )

        version = row["version"]
        await self._db.execute(
            "DELETE FROM installed_packages WHERE name = ? AND type = 'catalogue'",
            [name],
        )

        log.info("catalogue_uninstalled", name=name)
        return InstallResult(
            success=True,
            package_name=name,
            package_type="catalogue",
            version=version,
            restart_required=False,
            message=(
                f"Catalogue '{name}' unregistered. "
                "Imported primitives remain in the catalogue."
            ),
        )

    # -------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------

    def _find_primitives(self, package_dir: Path) -> list[Path]:
        """Find all manifest.json files under primitive-type subdirectories."""
        results: list[Path] = []
        for type_dir in _PRIMITIVE_TYPES:
            subdir = package_dir / type_dir
            if subdir.is_dir():
                results.extend(sorted(subdir.glob("*/manifest.json")))
        return results
