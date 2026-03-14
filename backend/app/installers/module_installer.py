"""Module installer — transactional install of module packages.

Phase 10 install flow (each step logged to install_transactions):
  1. Validate manifest.json with full Pydantic ModuleManifest validation
  2. Check shell_compatibility against SHELL_VERSION
  3. Check conflicts (keywords, panels, replaces_shell_view) against live registry
  4. Check every migration file declares a down() function
  5. Snapshot UserDB (pre-install backup)
  6. Run migrations up() in order
  7. pip install Python dependencies
  8. Register in installed_modules

On any failure after step 5, _rollback() undoes the completed steps in reverse.
On any failure before step 5, no writes have been made — no rollback needed.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import structlog
from pydantic import ValidationError

from ..constants import SHELL_VERSION
from ..module_manifest import ModuleManifest
from ..userdb import UserDB
from .base import InstallResult

log = structlog.get_logger().bind(component="module_installer")

# Core keywords that modules may not claim.
_CORE_KEYWORDS: frozenset[str] = frozenset({
    "TIMER_", "MEASUREMENT_", "MATERIAL_REF_", "TOOL_REF_",
    "TECHNIQUE_REF_", "IMAGE_", "LINK_", "NOTE_", "CHECKLIST_",
})


# ---------------------------------------------------------------------------
# Pure validation helpers (no DB writes, no side effects)
# ---------------------------------------------------------------------------


def _check_down_migrations(package_path: str) -> list[str]:
    """Return filenames of migration files that are missing a callable down().

    An empty list means all migrations are well-formed.
    """
    migrations_dir = Path(package_path) / "backend" / "migrations"
    if not migrations_dir.exists():
        return []

    missing: list[str] = []
    for migration_file in sorted(migrations_dir.glob("[0-9]*.py")):
        module_key = f"_chk_mig_{migration_file.stem}"
        spec = importlib.util.spec_from_file_location(module_key, migration_file)
        if spec is None or spec.loader is None:
            missing.append(migration_file.name)
            continue
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
        except Exception:
            missing.append(migration_file.name)
            continue
        if not (hasattr(mod, "down") and callable(mod.down)):
            missing.append(migration_file.name)
    return missing


def _check_conflicts(manifest: ModuleManifest, registry) -> list[str]:
    """Return a list of conflict descriptions between manifest and the live registry.

    Checks:
      - keywords against core keywords and other loaded modules
      - panel IDs against other loaded modules
      - replaces_shell_view claims against other loaded modules

    The registry argument is app.state.module_registry (ModuleRegistry).
    An empty return list means no conflicts.
    """
    conflicts: list[str] = []
    registered_keywords: dict[str, str] = registry.get_all_keywords()
    all_panels = registry.get_all_panels()
    registered_panel_ids: dict[str, str] = {p["id"]: p["module"] for p in all_panels}
    shell_view_claims: dict[str, str] = getattr(registry, "_shell_view_claims", {})

    for kw in manifest.keywords:
        if kw.keyword in _CORE_KEYWORDS:
            conflicts.append(
                f"Keyword {kw.keyword!r} is a core keyword and cannot be overridden"
            )
        elif kw.keyword in registered_keywords:
            owner = registered_keywords[kw.keyword]
            if owner != manifest.name:
                conflicts.append(
                    f"Keyword {kw.keyword!r} is already registered by '{owner}'"
                )

    for panel in manifest.panels:
        if panel.id in registered_panel_ids:
            owner = registered_panel_ids[panel.id]
            if owner != manifest.name:
                conflicts.append(
                    f"Panel ID {panel.id!r} is already registered by '{owner}'"
                )

    for view in manifest.views:
        if view.replaces_shell_view and view.replaces_shell_view in shell_view_claims:
            owner = shell_view_claims[view.replaces_shell_view]
            if owner != manifest.name:
                conflicts.append(
                    f"Shell view {view.replaces_shell_view!r} is already claimed by '{owner}'"
                )

    return conflicts


# ---------------------------------------------------------------------------
# ModuleInstaller
# ---------------------------------------------------------------------------


class ModuleInstaller:
    """Installs and uninstalls module packages with full transaction semantics."""

    def __init__(self, db: UserDB) -> None:
        self._db = db

    async def install(
        self,
        package_path: str,
        manifest,  # PackageManifest
        git_url: str | None = None,
        registry_name: str | None = None,
        module_registry=None,  # ModuleRegistry | None
        dry_run: bool = False,
    ) -> InstallResult:
        """Install a module package as an atomic transaction.

        Steps 1–4 are pure validation (no writes). If any fail, no rollback needed.
        Steps 5–8 write state; failures trigger _rollback() to undo completed steps.

        When dry_run=True, only steps 1–4 run. No writes are made.
        """
        tx_id = str(uuid.uuid4())
        steps_completed: list[str] = []
        snapshot_path: str | None = None
        python_deps: list[str] = []
        module_manifest: ModuleManifest | None = None

        # ------------------------------------------------------------------
        # Helpers (closures that close over tx_id / steps_completed)
        # ------------------------------------------------------------------

        async def _mark_step(step: str) -> None:
            """Append step to the completed list and persist to DB."""
            steps_completed.append(step)
            if not dry_run:
                await self._db.execute(
                    "UPDATE install_transactions SET steps_completed = ? WHERE id = ?",
                    [json.dumps(steps_completed), tx_id],
                )

        async def _fail_tx(step: str, error: str) -> None:
            """Mark the transaction as failed (only in non-dry-run mode)."""
            if not dry_run:
                await self._db.execute(
                    "UPDATE install_transactions "
                    "SET status = 'failed', failed_step = ?, error = ?, "
                    "    finished_at = datetime('now') "
                    "WHERE id = ?",
                    [step, error[:2000], tx_id],
                )

        def _fail_result(step: str, msg: str, suggestion: str | None = None) -> InstallResult:
            return InstallResult(
                success=False,
                package_name=manifest.name,
                package_type="module",
                version=manifest.version,
                message=msg,
                steps_completed=steps_completed,
                failed_step=step,
                suggestion=suggestion,
            )

        # ------------------------------------------------------------------
        # Begin transaction record
        # ------------------------------------------------------------------

        if not dry_run:
            await self._db.execute(
                """
                INSERT INTO install_transactions
                    (id, package_name, package_type, package_version, status,
                     steps_completed, started_at)
                VALUES (?, ?, 'module', ?, 'in_progress', '[]', datetime('now'))
                """,
                [tx_id, manifest.name, manifest.version],
            )

        # ------------------------------------------------------------------
        # Step 1: Validate manifest.json with full Pydantic validation
        # ------------------------------------------------------------------

        module_manifest_path = Path(package_path) / "manifest.json"
        if not module_manifest_path.exists():
            msg = (
                f"manifest.json not found at {module_manifest_path}. "
                "A module package must contain both makestack-package.json and manifest.json."
            )
            await _fail_tx("validate_manifest", msg)
            return _fail_result(
                "validate_manifest", msg,
                "Ensure the package directory contains a manifest.json alongside makestack-package.json.",
            )

        try:
            raw = json.loads(module_manifest_path.read_text(encoding="utf-8"))
            module_manifest = ModuleManifest.model_validate(raw)
        except json.JSONDecodeError as exc:
            msg = f"manifest.json is not valid JSON: {exc}"
            await _fail_tx("validate_manifest", msg)
            return _fail_result("validate_manifest", msg)
        except ValidationError as exc:
            first = exc.errors()[0]
            field = ".".join(str(x) for x in first.get("loc", []))
            msg = f"manifest.json failed validation on field '{field}': {first['msg']}"
            await _fail_tx("validate_manifest", msg)
            return _fail_result(
                "validate_manifest", msg,
                f"Check the '{field}' field in manifest.json against the ModuleManifest schema.",
            )

        await _mark_step("validate_manifest")
        python_deps = module_manifest.dependencies.get("python", [])

        # ------------------------------------------------------------------
        # Step 2: Check shell_compatibility
        # ------------------------------------------------------------------

        if module_manifest.shell_compatibility:
            try:
                from packaging.specifiers import InvalidSpecifier, SpecifierSet
                from packaging.version import Version

                spec = SpecifierSet(module_manifest.shell_compatibility)
                if Version(SHELL_VERSION) not in spec:
                    msg = (
                        f"Module requires shell {module_manifest.shell_compatibility!r} "
                        f"but the current shell version is {SHELL_VERSION!r}."
                    )
                    await _fail_tx("check_compat", msg)
                    return _fail_result(
                        "check_compat", msg,
                        f"Update the Shell to satisfy {module_manifest.shell_compatibility!r}, "
                        "or contact the module author to relax shell_compatibility.",
                    )
            except Exception as exc:
                msg = (
                    f"shell_compatibility '{module_manifest.shell_compatibility}' "
                    f"could not be evaluated: {exc}"
                )
                await _fail_tx("check_compat", msg)
                return _fail_result("check_compat", msg)

        await _mark_step("check_compat")

        # ------------------------------------------------------------------
        # Step 3: Conflict detection
        # ------------------------------------------------------------------

        if module_registry is not None:
            conflicts = _check_conflicts(module_manifest, module_registry)
            if conflicts:
                msg = "Conflicts detected:\n" + "\n".join(f"  • {c}" for c in conflicts)
                await _fail_tx("check_conflicts", msg)
                return _fail_result(
                    "check_conflicts", msg,
                    "Uninstall or disable the conflicting module(s) before installing this one.",
                )

        await _mark_step("check_conflicts")

        # ------------------------------------------------------------------
        # Step 3b: Check required peer modules are installed
        # ------------------------------------------------------------------

        for peer in module_manifest.peer_modules.get("required", []):
            peer_name = peer["name"] if isinstance(peer, dict) else peer
            row = await self._db.fetch_one(
                "SELECT name FROM installed_modules WHERE name = ? AND enabled = 1",
                [peer_name],
            )
            if not row:
                msg = (
                    f"Required peer module '{peer_name}' is not installed. "
                    f"Install it first before installing '{manifest.name}'."
                )
                await _fail_tx("check_peers", msg)
                return _fail_result(
                    "check_peers", msg,
                    f"Run: POST /api/packages/install with name='{peer_name}', then retry.",
                )

        await _mark_step("check_peers")

        # ------------------------------------------------------------------
        # Step 4: Validate all migration files declare down()
        # ------------------------------------------------------------------

        missing_down = _check_down_migrations(package_path)
        if missing_down:
            msg = (
                "The following migration files are missing a down() function: "
                + ", ".join(missing_down)
            )
            await _fail_tx("check_down_migrations", msg)
            return _fail_result(
                "check_down_migrations", msg,
                "Add a down() function to each migration file. "
                "See the module developer guide for the required structure.",
            )

        await _mark_step("check_down_migrations")

        # ------------------------------------------------------------------
        # Dry run stops here — all validation passed, no writes made
        # ------------------------------------------------------------------

        if dry_run:
            return InstallResult(
                success=True,
                package_name=manifest.name,
                package_type="module",
                version=manifest.version,
                message=(
                    f"Dry run: '{manifest.name}' {manifest.version} would install successfully. "
                    "All validation and conflict checks passed."
                ),
                steps_completed=steps_completed,
            )

        # ------------------------------------------------------------------
        # Step 5: Snapshot UserDB (pre-install backup)
        # ------------------------------------------------------------------

        db_path = self._db.path
        if db_path != ":memory:":
            backups_dir = Path(db_path).parent / "backups"
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            snap = backups_dir / f"userdb-preinstall-{ts}.sqlite"
            try:
                await self._db.backup(str(snap))
                snapshot_path = str(snap)
                await self._db.execute(
                    "UPDATE install_transactions SET backup_path = ? WHERE id = ?",
                    [snapshot_path, tx_id],
                )
            except Exception as exc:
                msg = f"Failed to snapshot UserDB before install: {exc}"
                await _fail_tx("snapshot_userdb", msg)
                return _fail_result(
                    "snapshot_userdb", msg,
                    "Check available disk space in ~/.makestack/backups/ and try again.",
                )

        await _mark_step("snapshot_userdb")

        # ------------------------------------------------------------------
        # Step 6: Run migrations up()
        # ------------------------------------------------------------------

        try:
            await self._run_migrations(manifest.name, package_path)
        except Exception as exc:
            msg = f"Migration failed: {exc}"
            log.error(
                "install_failed",
                module=manifest.name,
                step="run_migrations",
                error=msg,
            )
            await _fail_tx("run_migrations", msg)
            rolled_back, rb_warnings = await self._rollback(
                tx_id, steps_completed, manifest.name, package_path,
                snapshot_path, python_deps,
            )
            exc_str = str(exc)
            if "FOREIGN KEY" in exc_str:
                suggestion = (
                    "A required peer module may not be installed or enabled. "
                    "Check manifest.json peer_modules.required and ensure all peers "
                    "are installed and enabled before retrying."
                )
            elif "already exists" in exc_str:
                suggestion = (
                    "A table from a previous partial install may still exist. "
                    "Check module_migrations for stale rows and retry."
                )
            else:
                suggestion = "Check the migration file for errors and retry."
            return InstallResult(
                success=False,
                package_name=manifest.name,
                package_type="module",
                version=manifest.version,
                message=msg,
                steps_completed=steps_completed,
                failed_step="run_migrations",
                rolled_back=True,
                rollback_clean=rolled_back,
                warnings=rb_warnings,
                suggestion=suggestion,
            )

        await _mark_step("run_migrations")

        # ------------------------------------------------------------------
        # Step 7: pip install Python dependencies (failures are warnings only)
        # ------------------------------------------------------------------

        pip_warnings: list[str] = []
        if python_deps:
            pip_warnings = await self._pip_install(python_deps)

        await _mark_step("pip_install")

        # ------------------------------------------------------------------
        # Step 8: Register in installed_modules
        # ------------------------------------------------------------------

        try:
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
        except Exception as exc:
            msg = f"Failed to register module in installed_modules: {exc}"
            await _fail_tx("register", msg)
            rolled_back, rb_warnings = await self._rollback(
                tx_id, steps_completed, manifest.name, package_path,
                snapshot_path, python_deps,
            )
            return InstallResult(
                success=False,
                package_name=manifest.name,
                package_type="module",
                version=manifest.version,
                message=msg,
                steps_completed=steps_completed,
                failed_step="register",
                rolled_back=True,
                rollback_clean=rolled_back,
                warnings=rb_warnings + pip_warnings,
            )

        await _mark_step("register")

        # ------------------------------------------------------------------
        # Commit transaction
        # ------------------------------------------------------------------

        await self._db.execute(
            "UPDATE install_transactions "
            "SET status = 'completed', finished_at = datetime('now') WHERE id = ?",
            [tx_id],
        )

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
            warnings=pip_warnings,
            steps_completed=steps_completed,
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

    async def _run_migrations(self, module_name: str, package_path: str) -> None:
        """Discover and run any pending migrations for the module (up() only).

        Applied migrations are tracked in module_migrations. Both this method
        and the module_loader fallback check that table, so double-application
        is safe.
        """
        migrations_dir = Path(package_path) / "backend" / "migrations"
        if not migrations_dir.exists():
            return

        conn = self._db._require_connection()

        # Pre-register with a placeholder so the module_migrations FK is satisfied.
        # Step 8 (register) will UPDATE this row to enabled=1 with the real version.
        await conn.execute(
            """
            INSERT OR IGNORE INTO installed_modules
                (name, version, installed_at, enabled, package_path)
            VALUES (?, 'installing', datetime('now'), 0, ?)
            """,
            (module_name, package_path),
        )
        await conn.commit()

        cursor = await conn.execute(
            "SELECT migration_id FROM module_migrations WHERE module_name = ?",
            (module_name,),
        )
        applied: set[str] = {row["migration_id"] async for row in cursor}

        for migration_file in sorted(migrations_dir.glob("[0-9]*.py")):
            module_key = (
                f"_makestack_module_{module_name.replace('-', '_')}_migration_{migration_file.stem}"
            )
            spec = importlib.util.spec_from_file_location(module_key, migration_file)
            if spec is None or spec.loader is None:
                raise RuntimeError(
                    f"Could not load migration spec from {migration_file}"
                )

            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_key] = mod
            spec.loader.exec_module(mod)  # type: ignore[union-attr]

            migration_id: str = (
                getattr(mod, "ID", None) or getattr(mod, "id", None) or migration_file.stem
            )
            if migration_id in applied:
                continue

            log.info("module_migration_applying", module=module_name, id=migration_id)
            try:
                await mod.up(conn)
            except Exception as exc:
                log.error(
                    "module_migration_failed",
                    module=module_name,
                    migration=migration_file.name,
                    error=str(exc),
                    exc_info=True,
                )
                raise RuntimeError(
                    f"Migration '{migration_id}' in {migration_file.name} failed: {exc}"
                ) from exc
            await conn.execute(
                "INSERT INTO module_migrations (module_name, migration_id, applied_at) "
                "VALUES (?, ?, datetime('now'))",
                (module_name, migration_id),
            )
            await conn.commit()
            log.info("module_migration_applied", module=module_name, id=migration_id)

    async def _run_migrations_down(self, module_name: str, package_path: str) -> None:
        """Run down() for all applied migrations of this module, in reverse order.

        Used when a DB snapshot is unavailable for rollback.
        """
        migrations_dir = Path(package_path) / "backend" / "migrations"
        if not migrations_dir.exists():
            return

        conn = self._db._require_connection()

        cursor = await conn.execute(
            "SELECT migration_id FROM module_migrations "
            "WHERE module_name = ? ORDER BY applied_at DESC",
            (module_name,),
        )
        applied_ids: list[str] = [row["migration_id"] async for row in cursor]
        if not applied_ids:
            return

        applied_set = set(applied_ids)
        for migration_file in sorted(migrations_dir.glob("[0-9]*.py"), reverse=True):
            module_key = (
                f"_makestack_rollback_{module_name.replace('-', '_')}_{migration_file.stem}"
            )
            spec = importlib.util.spec_from_file_location(module_key, migration_file)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]

            migration_id: str = (
                getattr(mod, "ID", None) or getattr(mod, "id", None) or migration_file.stem
            )
            if migration_id not in applied_set:
                continue

            if hasattr(mod, "down") and callable(mod.down):
                log.info(
                    "module_migration_rolling_back",
                    module=module_name,
                    id=migration_id,
                )
                await mod.down(conn)
                await conn.execute(
                    "DELETE FROM module_migrations WHERE module_name = ? AND migration_id = ?",
                    (module_name, migration_id),
                )
                await conn.commit()
            else:
                log.warning(
                    "migration_down_missing_during_rollback",
                    module=module_name,
                    id=migration_id,
                )

    async def _rollback(
        self,
        tx_id: str,
        steps_completed: list[str],
        package_name: str,
        package_path: str,
        snapshot_path: str | None,
        python_deps: list[str],
    ) -> tuple[bool, list[str]]:
        """Reverse all completed steps in reverse order.

        Returns (rollback_clean, warning_messages).
        rollback_clean=False means manual cleanup may be required.
        """
        rollback_clean = True
        warnings: list[str] = []

        for step in reversed(steps_completed):
            if step == "register":
                try:
                    await self._db.execute(
                        "DELETE FROM installed_modules WHERE name = ?",
                        [package_name],
                    )
                    log.info("rollback_unregistered", module=package_name)
                except Exception as exc:
                    warnings.append(
                        f"Rollback: could not remove '{package_name}' from installed_modules: {exc}"
                    )
                    rollback_clean = False

            elif step == "pip_install":
                for dep in python_deps:
                    rc = await asyncio.to_thread(
                        lambda d=dep: subprocess.run(
                            ["pip", "uninstall", "-y", d],
                            capture_output=True,
                        ).returncode
                    )
                    if rc != 0:
                        warnings.append(
                            f"Rollback: pip uninstall {dep!r} failed (exit {rc}) "
                            "— orphan package may remain."
                        )
                        rollback_clean = False
                    else:
                        log.info("rollback_pip_uninstalled", package=dep)

            elif step == "run_migrations":
                if snapshot_path and Path(snapshot_path).exists():
                    try:
                        await self._db.restore(snapshot_path)
                        log.info("rollback_db_restored", path=snapshot_path)
                    except Exception as exc:
                        warnings.append(
                            f"Rollback: DB snapshot restore failed: {exc}. "
                            "Attempting manual migration down() as fallback."
                        )
                        rollback_clean = False
                        try:
                            await self._run_migrations_down(package_name, package_path)
                        except Exception as exc2:
                            warnings.append(
                                f"Rollback: manual migration down() also failed: {exc2}"
                            )
                else:
                    # No snapshot available — try manual down()
                    try:
                        await self._run_migrations_down(package_name, package_path)
                    except Exception as exc:
                        warnings.append(
                            f"Rollback: migration down() failed (no snapshot available): {exc}"
                        )
                        rollback_clean = False

            elif step == "snapshot_userdb":
                if snapshot_path:
                    try:
                        Path(snapshot_path).unlink(missing_ok=True)
                        log.info("rollback_snapshot_deleted", path=snapshot_path)
                    except Exception as exc:
                        warnings.append(
                            f"Rollback: could not delete snapshot at {snapshot_path}: {exc}"
                        )

        # Remove any pre-registration placeholder row left by _run_migrations.
        # This is a no-op if "register" already ran (row has version != 'installing')
        # or if a snapshot restore already wiped it.
        try:
            await self._db.execute(
                "DELETE FROM installed_modules WHERE name = ? AND version = 'installing'",
                [package_name],
            )
        except Exception as exc:
            warnings.append(
                f"Rollback: could not remove placeholder row for '{package_name}': {exc}"
            )
            rollback_clean = False

        # Update transaction row (if it still exists after potential DB restore)
        try:
            await self._db.execute(
                "UPDATE install_transactions "
                "SET status = 'rolled_back', finished_at = datetime('now') WHERE id = ?",
                [tx_id],
            )
        except Exception as exc:
            log.warning("rollback_tx_update_failed", tx_id=tx_id, error=str(exc))

        if rollback_clean:
            log.info("rollback_complete_clean", module=package_name, tx_id=tx_id)
        else:
            log.warning("rollback_complete_dirty", module=package_name, tx_id=tx_id)

        return rollback_clean, warnings

    async def _pip_install(self, packages: list[str]) -> list[str]:
        """Install Python packages via pip. Returns warning strings for failures."""
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
