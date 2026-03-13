"""Skill installer — installs Markdown skill files for Claude domain knowledge.

Skills are the simplest installable type. A skill is a single Markdown file
that teaches Claude how to work in a specific domain. There are no migrations,
no pip installs, no frontend rebuild, and no Shell restart required.

Install flow:
  1. Verify skill.md exists in the package directory.
  2. Verify skill.md is non-empty.
  3. Copy skill.md to ~/.makestack/skills/{name}.md.
  4. Register in installed_packages.

Uninstall flow:
  1. Delete ~/.makestack/skills/{name}.md.
  2. Remove from installed_packages.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import structlog

from ..userdb import UserDB
from .base import InstallResult

log = structlog.get_logger().bind(component="skill_installer")

_SKILLS_DIR = Path.home() / ".makestack" / "skills"


class SkillInstaller:
    """Installs and uninstalls skill packages."""

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
        """Copy skill.md to the skills directory and register in installed_packages."""
        skill_file = Path(package_path) / "skill.md"

        if not skill_file.exists():
            return InstallResult(
                success=False,
                package_name=manifest.name,
                package_type="skill",
                version=manifest.version,
                message=(
                    f"skill.md not found at {skill_file}. "
                    "A skill package must contain a skill.md file at its root."
                ),
                suggestion="Create skill.md with the domain knowledge for Claude.",
            )

        content = skill_file.read_text(encoding="utf-8").strip()
        if not content:
            return InstallResult(
                success=False,
                package_name=manifest.name,
                package_type="skill",
                version=manifest.version,
                message=f"skill.md in '{manifest.name}' is empty. Skills must contain content.",
                suggestion="Add Markdown content to skill.md before installing.",
            )

        if dry_run:
            return InstallResult(
                success=True,
                package_name=manifest.name,
                package_type="skill",
                version=manifest.version,
                message=f"Dry run: skill '{manifest.name}' would install successfully.",
            )

        _SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        dest = _SKILLS_DIR / f"{manifest.name}.md"
        shutil.copy2(str(skill_file), str(dest))

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
                VALUES (?, 'skill', ?, ?, ?, datetime('now'), ?)
                """,
                [manifest.name, manifest.version, git_url, package_path, registry_name],
            )
            action = "registered"

        log.info(
            "skill_installed",
            name=manifest.name,
            version=manifest.version,
            dest=str(dest),
            action=action,
        )

        return InstallResult(
            success=True,
            package_name=manifest.name,
            package_type="skill",
            version=manifest.version,
            restart_required=False,
            message=(
                f"Skill '{manifest.name}' {action} at {dest}. "
                "No restart required."
            ),
        )

    async def uninstall(self, name: str) -> InstallResult:
        """Remove the skill file and de-register from installed_packages."""
        row = await self._db.fetch_one(
            "SELECT version FROM installed_packages WHERE name = ? AND type = 'skill'",
            [name],
        )
        if not row:
            return InstallResult(
                success=False,
                package_name=name,
                package_type="skill",
                version="",
                message=f"Skill '{name}' is not installed.",
            )

        version = row["version"]

        skill_file = _SKILLS_DIR / f"{name}.md"
        try:
            skill_file.unlink(missing_ok=True)
        except OSError as exc:
            log.warning("skill_file_delete_failed", name=name, error=str(exc))

        await self._db.execute(
            "DELETE FROM installed_packages WHERE name = ? AND type = 'skill'", [name]
        )

        log.info("skill_uninstalled", name=name)
        return InstallResult(
            success=True,
            package_name=name,
            package_type="skill",
            version=version,
            restart_required=False,
            message=f"Skill '{name}' uninstalled.",
        )
