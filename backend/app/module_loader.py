"""Module loader — discovers, validates, migrates, and mounts installed modules.

Called during the Shell lifespan startup sequence, after the UserDB is ready.

Loading sequence for each enabled module:
  1. Read record from installed_modules table
  2. Resolve manifest.json (from package_path or installed Python package)
  3. Parse and validate ModuleManifest
  4. Run pending UserDB migrations
  5. Import the backend router (if has_backend)
  6. Mount the router on the FastAPI app
  7. Register keywords, panels, and endpoint declarations in ModuleRegistry

Failure modes:
  - Manifest not found / invalid → module marked as failed, Shell continues
  - Migration failure → module marked as failed, Shell continues
  - Import failure → module marked as failed, Shell continues
  - A failed module is skipped entirely (no routes mounted, no keywords registered)
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import structlog
from fastapi import APIRouter, FastAPI

from .module_manifest import ModuleManifest, ModuleEndpoint, ModulePanel, ModuleView
from .userdb import UserDB

log = structlog.get_logger().bind(component="module_loader")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class LoadedModule:
    """A successfully loaded module with its manifest and mounted router."""

    name: str
    manifest: ModuleManifest
    package_path: str | None          # Filesystem path; None if installed as Python package
    router: APIRouter | None = None   # The FastAPI router, if has_backend

    @property
    def mount_prefix(self) -> str:
        return f"/modules/{self.name}"


@dataclass
class FailedModule:
    """A module that failed to load, with the error reason."""

    name: str
    error: str


class ModuleRegistry:
    """Runtime registry of all loaded modules.

    Provides lookups used by the MCP tool generator, dev API, and MCP module tools.
    Stored on app.state.module_registry at startup.
    """

    def __init__(self) -> None:
        self._loaded: list[LoadedModule] = []
        self._failed: list[FailedModule] = []
        # Tracks which module last claimed each shell view via replaces_shell_view.
        # At most one module may claim each view; last-to-load wins (with a warning).
        self._shell_view_claims: dict[str, str] = {}  # shell_view_id → module_name

    # --- Mutation (only during startup) ---

    def _add_loaded(self, m: LoadedModule) -> None:
        for view in m.manifest.views:
            if view.replaces_shell_view:
                existing = self._shell_view_claims.get(view.replaces_shell_view)
                if existing:
                    log.warning(
                        "shell_view_claim_conflict",
                        shell_view=view.replaces_shell_view,
                        existing_module=existing,
                        new_module=m.name,
                    )
                self._shell_view_claims[view.replaces_shell_view] = m.name
        self._loaded.append(m)

    def _add_failed(self, name: str, error: str) -> None:
        self._failed.append(FailedModule(name=name, error=error))

    # --- Queries ---

    def get_loaded(self) -> list[LoadedModule]:
        return list(self._loaded)

    def get_failed(self) -> list[FailedModule]:
        return list(self._failed)

    def get_module(self, name: str) -> LoadedModule | None:
        return next((m for m in self._loaded if m.name == name), None)

    def is_loaded(self, name: str) -> bool:
        return any(m.name == name for m in self._loaded)

    def get_all_keywords(self) -> dict[str, str]:
        """Return a mapping of keyword → module_name for all registered keywords."""
        result: dict[str, str] = {}
        for m in self._loaded:
            for kw in m.manifest.keywords:
                result[kw.keyword] = m.name
        return result

    def get_all_views(self) -> list[dict]:
        """Return all module views with module context, ordered by sort_order."""
        result = []
        for m in self._loaded:
            for view in m.manifest.views:
                result.append({"module": m.name, **view.model_dump()})
        result.sort(key=lambda v: v["sort_order"])
        return result

    def get_module_views(self, name: str) -> list[ModuleView]:
        """Return the declared views for a loaded module, or [] if not loaded."""
        loaded = self.get_module(name)
        return list(loaded.manifest.views) if loaded else []

    def get_all_panels(self) -> list[dict]:
        """Return all module panels with module context."""
        result = []
        for m in self._loaded:
            for panel in m.manifest.panels:
                result.append({"module": m.name, **panel.model_dump()})
        return result

    def get_module_panels(self, name: str) -> list[ModulePanel]:
        """Return the declared panels for a loaded module, or [] if not loaded."""
        loaded = self.get_module(name)
        return list(loaded.manifest.panels) if loaded else []

    def get_all_endpoints(self) -> list[dict]:
        """Return all module API endpoints with module context (for MCP generation)."""
        result = []
        for m in self._loaded:
            for ep in m.manifest.api_endpoints:
                result.append({
                    "module_name": m.name,
                    "module_display_name": m.manifest.display_name,
                    **ep.model_dump(),
                })
        return result


# ---------------------------------------------------------------------------
# Manifest resolution
# ---------------------------------------------------------------------------


def _find_manifest_path(name: str, package_path: str | None) -> Path:
    """Locate manifest.json for a module."""
    if package_path:
        p = Path(package_path) / "manifest.json"
        if not p.exists():
            raise FileNotFoundError(
                f"manifest.json not found at expected path: {p}"
            )
        return p

    # Installed Python package — try both naming conventions:
    # 1. {name_underscored} (simple)
    # 2. makestack_module_{name_underscored} (namespaced)
    snake = name.replace("-", "_")
    for pkg_name in (snake, f"makestack_module_{snake}"):
        try:
            pkg = importlib.import_module(pkg_name)
            p = Path(pkg.__file__).parent / "manifest.json"  # type: ignore[arg-type]
            if p.exists():
                return p
        except ImportError:
            pass

    raise ModuleNotFoundError(
        f"Cannot find Python package for module '{name}'. "
        f"Tried: '{snake}', 'makestack_module_{snake}'. "
        f"Install the package or use package_path for local loading."
    )


def _load_manifest(name: str, package_path: str | None) -> ModuleManifest:
    """Read and validate the manifest for a module."""
    manifest_path = _find_manifest_path(name, package_path)
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    return ModuleManifest.model_validate(raw)


# ---------------------------------------------------------------------------
# Backend route import
# ---------------------------------------------------------------------------


def _import_routes(name: str, package_path: str | None) -> ModuleType:
    """Import the module's backend.routes module.

    Returns the imported Python module (which must expose a `router` attribute).
    """
    if package_path:
        routes_path = Path(package_path) / "backend" / "routes.py"
        if not routes_path.exists():
            raise FileNotFoundError(
                f"backend/routes.py not found at {routes_path}"
            )
        module_key = f"_makestack_module_{name.replace('-', '_')}_routes"
        spec = importlib.util.spec_from_file_location(module_key, routes_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not create module spec from {routes_path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_key] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    # Installed package
    snake = name.replace("-", "_")
    for pkg_name in (f"{snake}.backend.routes", f"makestack_module_{snake}.backend.routes"):
        try:
            return importlib.import_module(pkg_name)
        except ImportError:
            pass

    raise ImportError(
        f"Cannot import backend.routes for module '{name}'. "
        f"Ensure the package is installed or use package_path."
    )


def _get_router(routes_module: ModuleType, name: str) -> APIRouter:
    """Extract the FastAPI router from the imported routes module."""
    router = getattr(routes_module, "router", None)
    if router is None:
        raise AttributeError(
            f"Module '{name}' backend/routes.py must define a `router` attribute "
            f"(a FastAPI APIRouter instance)."
        )
    if not isinstance(router, APIRouter):
        raise TypeError(
            f"Module '{name}' routes.router must be a FastAPI APIRouter, "
            f"got {type(router).__name__}"
        )
    return router


# ---------------------------------------------------------------------------
# Migration runner
# ---------------------------------------------------------------------------


async def _run_module_migrations(
    name: str,
    package_path: str | None,
    db: UserDB,
) -> None:
    """Discover and run any pending migrations for a module.

    Migrations are numbered Python files in backend/migrations/ that expose:
      ID = "migration_id"
      async def up(conn) -> None: ...

    Applied migrations are tracked in the module_migrations table.
    """
    if package_path:
        migrations_dir = Path(package_path) / "backend" / "migrations"
    else:
        snake = name.replace("-", "_")
        pkg = None
        for pkg_name in (snake, f"makestack_module_{snake}"):
            try:
                pkg = importlib.import_module(pkg_name)
                break
            except ImportError:
                pass
        if pkg is None:
            log.warning("module_migrations_pkg_not_found", module=name)
            return
        migrations_dir = Path(pkg.__file__).parent / "backend" / "migrations"  # type: ignore[arg-type]

    if not migrations_dir.exists():
        return  # No migrations defined — that's fine

    conn = db._require_connection()

    # Load already-applied migration IDs for this module.
    cursor = await conn.execute(
        "SELECT migration_id FROM module_migrations WHERE module_name = ?",
        (name,),
    )
    applied: set[str] = {row["migration_id"] async for row in cursor}

    migration_files = sorted(migrations_dir.glob("[0-9]*.py"))

    for migration_file in migration_files:
        module_key = f"_makestack_module_{name.replace('-', '_')}_migration_{migration_file.stem}"
        spec = importlib.util.spec_from_file_location(module_key, migration_file)
        if spec is None or spec.loader is None:
            log.error("module_migration_load_failed", module=name, file=str(migration_file))
            continue

        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_key] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        migration_id: str = getattr(mod, "ID", migration_file.stem)

        if migration_id in applied:
            log.debug("module_migration_already_applied", module=name, id=migration_id)
            continue

        log.info("module_migration_applying", module=name, id=migration_id)
        start = time.monotonic()

        await mod.up(conn)
        await conn.execute(
            "INSERT INTO module_migrations (module_name, migration_id, applied_at) "
            "VALUES (?, ?, datetime('now'))",
            (name, migration_id),
        )
        await conn.commit()

        # Update last_migration in installed_modules.
        await db.execute(
            "UPDATE installed_modules SET last_migration = ? WHERE name = ?",
            [migration_id, name],
        )

        elapsed_ms = (time.monotonic() - start) * 1000
        log.info(
            "module_migration_applied",
            module=name,
            id=migration_id,
            elapsed_ms=round(elapsed_ms, 1),
        )


# ---------------------------------------------------------------------------
# Single-module loader
# ---------------------------------------------------------------------------


async def _load_module(
    name: str,
    package_path: str | None,
    db: UserDB,
) -> LoadedModule:
    """Load a single module: validate manifest, run migrations, import router."""
    logger = log.bind(module=name)

    # 1. Parse manifest
    manifest = _load_manifest(name, package_path)
    logger.info("module_manifest_loaded", version=manifest.version)

    # 2. Run migrations (before importing routes, so tables exist)
    await _run_module_migrations(name, package_path, db)

    # 3. Import backend router (if the module has a backend)
    router: APIRouter | None = None
    if manifest.has_backend:
        routes_module = _import_routes(name, package_path)
        router = _get_router(routes_module, name)
        logger.debug("module_router_imported")

    return LoadedModule(
        name=name,
        manifest=manifest,
        package_path=package_path,
        router=router,
    )


# ---------------------------------------------------------------------------
# Startup recovery — roll back interrupted install transactions
# ---------------------------------------------------------------------------


async def _recover_incomplete_installs(db: UserDB) -> None:
    """Roll back any install transactions that were left in_progress.

    Called at startup BEFORE any modules are loaded, so that a crashed install
    does not leave the system in a half-installed state.
    """
    import json as _json

    rows = await db.fetch_all(
        "SELECT id, package_name, steps_completed, backup_path "
        "FROM install_transactions WHERE status = 'in_progress'"
    )
    if not rows:
        return

    log.warning(
        "startup_recovery_found_incomplete_installs",
        count=len(rows),
    )

    from .installers.module_installer import ModuleInstaller

    module_installer = ModuleInstaller(db)

    for row in rows:
        tx_id = row["id"]
        pkg_name = row["package_name"]
        try:
            steps = _json.loads(row["steps_completed"] or "[]")
        except Exception:
            steps = []
        snapshot = row.get("backup_path")

        log.info("startup_recovery_rolling_back", tx_id=tx_id, package=pkg_name)
        rolled_back, warnings = await module_installer._rollback(
            tx_id=tx_id,
            steps_completed=steps,
            package_name=pkg_name,
            package_path=None,
            snapshot_path=snapshot,
            python_deps=[],
        )
        await db.execute(
            "UPDATE install_transactions SET status = 'rolled_back', "
            "finished_at = datetime('now') WHERE id = ?",
            [tx_id],
        )
        log.info(
            "startup_recovery_complete",
            tx_id=tx_id,
            package=pkg_name,
            rolled_back=rolled_back,
            warnings=warnings,
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def load_modules(app: FastAPI, db: UserDB) -> ModuleRegistry:
    """Load all enabled modules from the installed_modules table.

    Mounts each module's router on the FastAPI app.
    Returns a populated ModuleRegistry stored on app.state.module_registry.

    Failures are logged and collected; the Shell always starts even if every
    module fails to load.
    """
    # Recover any install transactions interrupted by a crash before loading modules.
    await _recover_incomplete_installs(db)

    registry = ModuleRegistry()

    rows = await db.fetch_all(
        "SELECT name, version, package_path FROM installed_modules WHERE enabled = 1 ORDER BY name"
    )

    if not rows:
        log.info("module_loader_no_modules")
        return registry

    log.info("module_loader_start", count=len(rows))

    for row in rows:
        name: str = row["name"]
        package_path: str | None = row.get("package_path")
        logger = log.bind(module=name)

        try:
            loaded = await _load_module(name, package_path, db)
            registry._add_loaded(loaded)

            # Mount the FastAPI router at /modules/{name}/
            if loaded.router is not None:
                app.include_router(
                    loaded.router,
                    prefix=loaded.mount_prefix,
                    tags=[f"module:{name}"],
                )
                logger.info("module_router_mounted", prefix=loaded.mount_prefix)

            logger.info(
                "module_loaded",
                keywords=len(loaded.manifest.keywords),
                endpoints=len(loaded.manifest.api_endpoints),
                panels=len(loaded.manifest.panels),
            )

        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            registry._add_failed(name, error_msg)
            logger.error("module_load_failed", error=error_msg, exc_info=True)

    loaded_count = len(registry.get_loaded())
    failed_count = len(registry.get_failed())
    log.info(
        "module_loader_done",
        loaded=loaded_count,
        failed=failed_count,
    )

    return registry
