"""Data installer — installs themes, presets, and other data assets.

Install flow:
  1. Verify package type is 'data'.
  2. Read 'targets' from makestack-package.json — a map of source → dest paths.
  3. Copy each file to its target (relative to makestack_home).
  4. Register in installed_packages.
  5. No restart required.

makestack-package.json for a data package:
{
  "name": "cyberpunk-theme",
  "type": "data",
  "version": "1.0.0",
  "targets": {
    "cyberpunk.json": ".makestack/themes/cyberpunk.json"
  }
}

Source paths are relative to the package root.
Target paths are relative to the user's home directory (~/).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import structlog

from ..userdb import UserDB
from .base import InstallResult

log = structlog.get_logger().bind(component="data_installer")


class DataInstaller:
    """Installs and uninstalls data packages (themes, presets, etc.)."""

    def __init__(self, db: UserDB, makestack_home: Path) -> None:
        self._db = db
        self._home = makestack_home

    async def install(
        self,
        package_path: str,
        manifest,  # PackageManifest — but we also need the raw dict for 'targets'
        git_url: str | None = None,
        registry_name: str | None = None,
    ) -> InstallResult:
        """Copy data files to their target locations."""
        warnings: list[str] = []
        package_dir = Path(package_path)

        # Re-read makestack-package.json to get the 'targets' field (not in manifest model).
        pkg_json_path = package_dir / "makestack-package.json"
        targets: dict[str, str] = {}
        if pkg_json_path.exists():
            import json
            try:
                raw = json.loads(pkg_json_path.read_text(encoding="utf-8"))
                targets = raw.get("targets", {})
            except (json.JSONDecodeError, OSError):
                pass

        copied = 0
        for src_rel, dst_rel in targets.items():
            src = package_dir / src_rel
            dst = Path.home() / dst_rel

            if not src.exists():
                warnings.append(f"Source file not found: {src_rel}")
                continue

            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
            log.debug("data_file_copied", src=str(src), dst=str(dst))

        # Register in installed_packages.
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
                VALUES (?, 'data', ?, ?, ?, datetime('now'), ?)
                """,
                [manifest.name, manifest.version, git_url, package_path, registry_name],
            )

        log.info("data_package_installed", name=manifest.name, files_copied=copied)

        return InstallResult(
            success=True,
            package_name=manifest.name,
            package_type="data",
            version=manifest.version,
            restart_required=False,
            message=(
                f"Data package '{manifest.name}' installed: {copied} file(s) copied."
            ),
            warnings=warnings,
        )

    async def uninstall(self, name: str) -> InstallResult:
        """Remove a data package registration.

        Installed files are NOT deleted — they may have been modified by the user.
        """
        row = await self._db.fetch_one(
            "SELECT version FROM installed_packages WHERE name = ? AND type = 'data'",
            [name],
        )
        if not row:
            return InstallResult(
                success=False,
                package_name=name,
                package_type="data",
                version="",
                message=f"Data package '{name}' is not installed.",
            )

        version = row["version"]
        await self._db.execute(
            "DELETE FROM installed_packages WHERE name = ? AND type = 'data'",
            [name],
        )

        log.info("data_package_uninstalled", name=name)
        return InstallResult(
            success=True,
            package_name=name,
            package_type="data",
            version=version,
            restart_required=False,
            message=(
                f"Data package '{name}' unregistered. "
                "Installed files were not removed."
            ),
        )
