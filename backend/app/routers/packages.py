"""Package and registry management routes.

Packages:
  GET    /api/packages               — list all installed packages (all types)
  POST   /api/packages/install       — install a package by name, URL, or path
  DELETE /api/packages/{name}        — uninstall a package
  POST   /api/packages/{name}/update — update a package to latest or pinned version
  GET    /api/packages/search?q=     — search across all registries

Registries:
  GET    /api/registries             — list configured registries
  POST   /api/registries             — add a registry
  DELETE /api/registries/{name}      — remove a registry
  POST   /api/registries/refresh     — pull latest from all registries
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from ..dependencies import get_core_client, get_userdb
from ..core_client import CatalogueClient
from ..models import (
    InstalledPackage,
    InstallResult,
    PaginatedList,
    PackageInstallRequest,
    RegistryAddRequest,
    RegistryRecord,
)
from ..package_manifest import PackageManifest
from ..userdb import UserDB
from pydantic import ValidationError

log = structlog.get_logger().bind(component="packages_router")

router = APIRouter(prefix="/api", tags=["packages"])


# ---------------------------------------------------------------------------
# Helpers — service access from app.state
# ---------------------------------------------------------------------------


def _get_registry_client(request: Request):
    return getattr(request.app.state, "registry_client", None)


def _get_package_cache(request: Request):
    return getattr(request.app.state, "package_cache", None)


def _get_installer(request: Request, db: UserDB, core: CatalogueClient):
    """Build the PackageInstaller dispatcher on demand."""
    from ..installers import (
        PackageInstaller,
        ModuleInstaller,
        SkillInstaller,
        WidgetInstaller,
        CatalogueInstaller,
        DataInstaller,
    )
    home = Path.home() / ".makestack"
    return PackageInstaller(
        module_installer=ModuleInstaller(db),
        widget_installer=WidgetInstaller(db),
        catalogue_installer=CatalogueInstaller(db, core),
        data_installer=DataInstaller(db, home),
        skill_installer=SkillInstaller(db),
    )


def _load_package_manifest(package_path: str) -> PackageManifest:
    """Read and validate makestack-package.json from a package directory."""
    pkg_json = Path(package_path) / "makestack-package.json"
    if not pkg_json.exists():
        raise HTTPException(
            status_code=422,
            detail={
                "error": "makestack-package.json not found",
                "path": package_path,
                "suggestion": "The package directory must contain a makestack-package.json file.",
            },
        )
    try:
        raw = json.loads(pkg_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "makestack-package.json is not valid JSON",
                "detail": str(exc),
            },
        )
    try:
        return PackageManifest.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "makestack-package.json failed validation",
                "errors": exc.errors(),
            },
        )


# ---------------------------------------------------------------------------
# Package list
# ---------------------------------------------------------------------------


@router.get(
    "/packages",
    summary="List all installed packages",
)
async def list_packages(
    limit: int = 50,
    offset: int = 0,
    db: UserDB = Depends(get_userdb),
    request: Request = None,
) -> dict:
    """List all installed packages across all types (modules + widget-packs + catalogues + data)."""
    # Modules from installed_modules
    module_rows = await db.fetch_all(
        "SELECT name, version, installed_at, package_path FROM installed_modules ORDER BY name"
    )
    modules = [
        {
            "name": r["name"],
            "type": "module",
            "version": r["version"],
            "installed_at": r["installed_at"],
            "package_path": r.get("package_path"),
            "git_url": None,
            "registry_name": None,
        }
        for r in module_rows
    ]

    # Non-module packages from installed_packages
    pkg_rows = await db.fetch_all(
        "SELECT name, type, version, git_url, package_path, installed_at, registry_name "
        "FROM installed_packages ORDER BY name"
    )
    other = [dict(r) for r in pkg_rows]

    all_packages = sorted(modules + other, key=lambda p: p["name"])
    total = len(all_packages)
    page = all_packages[offset : offset + limit]

    return {"items": page, "total": total, "limit": limit, "offset": offset}


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------


@router.post(
    "/packages/install",
    response_model=InstallResult,
    status_code=201,
    summary="Install a package",
)
async def install_package(
    body: PackageInstallRequest,
    request: Request,
    db: UserDB = Depends(get_userdb),
    core: CatalogueClient = Depends(get_core_client),
) -> InstallResult:
    """Install a package by registry name, Git URL, or local path.

    Provide either 'name' (resolved via configured registries) or 'source'
    (a Git URL starting with http/https, or a local directory path).
    """
    if not body.name and not body.source:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Either 'name' or 'source' must be provided.",
                "suggestion": (
                    "Use 'name' to install from a registry (e.g. 'inventory-stock'), "
                    "or 'source' for a Git URL or local path."
                ),
            },
        )

    registry_client = _get_registry_client(request)
    package_cache = _get_package_cache(request)
    installer = _get_installer(request, db, core)

    git_url: str | None = None
    registry_name: str | None = None
    package_path: str

    # --- Resolve source ---
    if body.source:
        if body.source.startswith("http://") or body.source.startswith("https://"):
            # Direct Git URL
            git_url = body.source
            pkg_name = body.name or body.source.rstrip("/").split("/")[-1].removesuffix(".git")
            if package_cache is None:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "Package cache not available",
                        "suggestion": "Restart the Shell to initialise the package manager.",
                    },
                )
            # Peek at the manifest to determine type before caching.
            # We clone to a temporary location first.
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                from ..registry_client import run_git
                rc, _, stderr = await run_git("clone", "--depth=1", git_url, tmpdir + "/pkg")
                if rc != 0:
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "error": f"git clone failed: {stderr}",
                            "git_url": git_url,
                        },
                    )
                manifest = _load_package_manifest(tmpdir + "/pkg")

            # Now fetch properly into the cache.
            cache_path = await package_cache.fetch(
                manifest.name, git_url, manifest.type, body.version
            )
            package_path = str(cache_path)
        else:
            # Local path
            local = Path(body.source)
            if not local.exists():
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": f"Local path not found: {body.source}",
                        "suggestion": "Provide an absolute or relative path to a package directory.",
                    },
                )
            package_path = str(local.resolve())
            manifest = _load_package_manifest(package_path)
            git_url = None

    else:
        # Resolve by name via registry
        if registry_client is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "Registry client not available",
                    "suggestion": "Restart the Shell to initialise the package manager.",
                },
            )
        info = registry_client.resolve(body.name)
        if info is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": f"Package '{body.name}' not found in any configured registry",
                    "suggestion": (
                        "Use GET /api/packages/search to search across registries, "
                        "or GET /api/registries to see configured registries."
                    ),
                },
            )
        git_url = info.git_url
        registry_name = info.registry_name

        if package_cache is None:
            raise HTTPException(
                status_code=503,
                detail={"error": "Package cache not available"},
            )

        cache_path = await package_cache.fetch(
            info.name, git_url, info.type, body.version, subdir=info.subdir
        )
        package_path = str(cache_path)
        manifest = _load_package_manifest(package_path)

    # --- Dispatch to installer ---
    module_registry = getattr(request.app.state, "module_registry", None)
    dry_run: bool = getattr(body, "dry_run", False)
    result = await installer.install(
        package_path=package_path,
        manifest=manifest,
        git_url=git_url,
        registry_name=registry_name,
        module_registry=module_registry,
        dry_run=dry_run,
    )

    if not result.success:
        raise HTTPException(
            status_code=422,
            detail={
                "error": result.message,
                "warnings": result.warnings,
                "failed_step": result.failed_step,
                "steps_completed": result.steps_completed,
                "rolled_back": result.rolled_back,
                "rollback_clean": result.rollback_clean,
                "suggestion": result.suggestion,
            },
        )

    log.info(
        "package_installed",
        name=manifest.name,
        type=manifest.type,
        version=manifest.version,
        dry_run=dry_run,
    )
    return InstallResult(
        success=result.success,
        package_name=result.package_name,
        package_type=result.package_type,
        version=result.version,
        restart_required=result.restart_required,
        message=result.message,
        warnings=result.warnings,
        steps_completed=result.steps_completed,
        failed_step=result.failed_step,
        rolled_back=result.rolled_back,
        rollback_clean=result.rollback_clean,
        suggestion=result.suggestion,
    )


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------


@router.delete(
    "/packages/{name}",
    response_model=InstallResult,
    summary="Uninstall a package",
)
async def uninstall_package(
    name: str,
    request: Request,
    db: UserDB = Depends(get_userdb),
    core: CatalogueClient = Depends(get_core_client),
) -> InstallResult:
    """Uninstall a package by name.

    For modules: disables the module (data tables are preserved).
    For other types: removes the registration from the database.
    The package cache is not purged automatically.
    """
    installer = _get_installer(request, db, core)
    package_cache = _get_package_cache(request)

    # Determine type by checking both tables.
    mod_row = await db.fetch_one(
        "SELECT version FROM installed_modules WHERE name = ?", [name]
    )
    pkg_row = await db.fetch_one(
        "SELECT type, version FROM installed_packages WHERE name = ?", [name]
    )

    if not mod_row and not pkg_row:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Package '{name}' is not installed",
                "suggestion": "Use GET /api/packages to list installed packages.",
            },
        )

    pkg_type = "module" if mod_row else pkg_row["type"]
    result = await installer.uninstall(name, pkg_type)

    if not result.success:
        raise HTTPException(
            status_code=422,
            detail={"error": result.message},
        )

    # Optionally clear from package cache.
    if package_cache:
        package_cache.remove(name, pkg_type)

    log.info("package_uninstalled", name=name, type=pkg_type)
    return InstallResult(
        success=result.success,
        package_name=result.package_name,
        package_type=result.package_type,
        version=result.version,
        restart_required=result.restart_required,
        message=result.message,
        warnings=result.warnings,
        steps_completed=result.steps_completed,
        failed_step=result.failed_step,
        rolled_back=result.rolled_back,
        rollback_clean=result.rollback_clean,
        suggestion=result.suggestion,
    )


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@router.post(
    "/packages/{name}/update",
    response_model=InstallResult,
    summary="Update an installed package",
)
async def update_package(
    name: str,
    version: str | None = None,
    request: Request = None,
    db: UserDB = Depends(get_userdb),
    core: CatalogueClient = Depends(get_core_client),
) -> InstallResult:
    """Update an installed package to its latest version (or a specific version).

    Fetches the latest from the Git remote, re-reads makestack-package.json,
    and re-runs the type-specific installer.
    """
    installer = _get_installer(request, db, core)
    package_cache = _get_package_cache(request)

    # Find where the package is stored.
    mod_row = await db.fetch_one(
        "SELECT version, package_path FROM installed_modules WHERE name = ?", [name]
    )
    pkg_row = await db.fetch_one(
        "SELECT type, version, git_url, package_path FROM installed_packages WHERE name = ?",
        [name],
    )

    if not mod_row and not pkg_row:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Package '{name}' is not installed",
                "suggestion": "Use GET /api/packages to list installed packages.",
            },
        )

    if mod_row:
        pkg_type = "module"
        git_url = None
        package_path = mod_row.get("package_path")
    else:
        pkg_type = pkg_row["type"]
        git_url = pkg_row.get("git_url")
        package_path = pkg_row.get("package_path")

    # If there's a Git URL, re-fetch.
    if git_url and package_cache:
        cache_path = await package_cache.fetch(name, git_url, pkg_type, version)
        package_path = str(cache_path)
    elif not package_path:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Cannot update '{name}': no Git URL or local path recorded.",
                "suggestion": "Packages installed from local paths must be updated manually.",
            },
        )

    manifest = _load_package_manifest(package_path)
    result = await installer.install(
        package_path=package_path,
        manifest=manifest,
        git_url=git_url,
    )

    if not result.success:
        raise HTTPException(status_code=422, detail={"error": result.message})

    log.info("package_updated", name=name, version=result.version)
    return InstallResult(
        success=result.success,
        package_name=result.package_name,
        package_type=result.package_type,
        version=result.version,
        restart_required=result.restart_required,
        message=result.message,
        warnings=result.warnings,
        steps_completed=result.steps_completed,
        failed_step=result.failed_step,
        rolled_back=result.rolled_back,
        rollback_clean=result.rollback_clean,
        suggestion=result.suggestion,
    )


# ---------------------------------------------------------------------------
# Preview — dependency resolution before install
# ---------------------------------------------------------------------------


@router.get(
    "/packages/{name}/preview",
    summary="Preview what installing a package would do",
)
async def preview_package(
    name: str,
    request: Request,
    db: UserDB = Depends(get_userdb),
) -> dict:
    """Preview a package install: reads the manifest from the registry without installing,
    resolves required peer_modules recursively, and reports which are already installed.
    """
    registry_client = _get_registry_client(request)
    if registry_client is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "Registry client not available"},
        )

    info = registry_client.resolve(name)
    if info is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Package '{name}' not found in any configured registry",
                "suggestion": "Use GET /api/packages/search to search across registries.",
            },
        )

    # Fetch the manifest to read peer_modules
    package_cache = _get_package_cache(request)
    manifest_data: dict = {
        "name": info.name,
        "type": info.type,
        "description": info.description,
    }
    dependencies: list[dict] = []
    warnings: list[str] = []

    if package_cache:
        try:
            cache_path = await package_cache.fetch(
                info.name, info.git_url, info.type, subdir=info.subdir
            )
            manifest = _load_package_manifest(str(cache_path))
            manifest_data = {
                "name": manifest.name,
                "type": manifest.type,
                "version": manifest.version,
                "description": getattr(manifest, "description", ""),
            }

            # Read peer_modules from the module's own manifest.json (not package manifest)
            module_manifest_path = Path(cache_path) / "manifest.json"
            if module_manifest_path.exists():
                try:
                    raw = json.loads(module_manifest_path.read_text(encoding="utf-8"))
                    peers = raw.get("peer_modules", {})
                    for peer in peers.get("required", []):
                        peer_name = peer["name"] if isinstance(peer, dict) else peer
                        installed = await db.fetch_one(
                            "SELECT name FROM installed_modules WHERE name = ?", [peer_name]
                        )
                        dependencies.append({
                            "name": peer_name,
                            "type": "required",
                            "already_installed": installed is not None,
                        })
                    for peer in peers.get("optional", []):
                        peer_name = peer["name"] if isinstance(peer, dict) else peer
                        installed = await db.fetch_one(
                            "SELECT name FROM installed_modules WHERE name = ?", [peer_name]
                        )
                        dependencies.append({
                            "name": peer_name,
                            "type": "optional",
                            "already_installed": installed is not None,
                        })
                except (json.JSONDecodeError, KeyError):
                    warnings.append("Could not parse module manifest.json for peer dependencies")
        except Exception as exc:
            warnings.append(f"Could not fetch package for preview: {exc}")

    # Check if the target itself is already installed
    already_installed = await db.fetch_one(
        "SELECT name FROM installed_modules WHERE name = ?", [name]
    )

    return {
        "module": manifest_data,
        "already_installed": already_installed is not None,
        "dependencies": dependencies,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@router.get(
    "/packages/search",
    summary="Search packages across all registries",
)
async def search_packages(
    request: Request,
    q: str = "",
) -> dict:
    """Search package names and descriptions across all configured registries.

    When 'q' is empty or omitted, lists all packages from all registries.
    Returns matching packages de-duplicated by name (first-match wins in
    alphabetical registry order).
    """
    registry_client = _get_registry_client(request)
    if registry_client is None:
        return {"items": [], "total": 0, "query": q}

    if not q:
        # No query — list everything from all registries.
        from ..registry_client import PackageInfo
        results: list[PackageInfo] = []
        seen: set[str] = set()
        for registry_dir in registry_client._registry_dirs():
            for pkg in registry_client.list_packages_in_registry(registry_dir.name):
                if pkg.name not in seen:
                    results.append(pkg)
                    seen.add(pkg.name)
    else:
        results = registry_client.search(q)
    items = [
        {
            "name": p.name,
            "type": p.type,
            "description": p.description,
            "git_url": p.git_url,
            "registry": p.registry_name,
        }
        for p in results
    ]
    return {"items": items, "total": len(items), "query": q}


# ---------------------------------------------------------------------------
# Repair — recover in_progress install transactions
# ---------------------------------------------------------------------------


@router.get(
    "/packages/repair",
    summary="Report and roll back any in-progress install transactions",
)
async def repair_packages(
    request: Request,
    db: UserDB = Depends(get_userdb),
) -> dict:
    """Detect and roll back install transactions that were interrupted (e.g. crash).

    This is the same recovery logic that runs automatically at startup, but
    exposed as an API endpoint for manual invocation and for the CLI
    'makestack repair' command.

    Returns a list of transaction IDs that were found in_progress and the
    outcome of each rollback attempt.
    """
    rows = await db.fetch_all(
        "SELECT id, package_name, package_type, steps_completed, backup_path "
        "FROM install_transactions WHERE status = 'in_progress'"
    )
    if not rows:
        return {"transactions": [], "message": "No in-progress transactions found."}

    import json as _json
    from ..installers.module_installer import ModuleInstaller

    results = []
    for row in rows:
        tx_id = row["id"]
        pkg_name = row["package_name"]
        try:
            steps = _json.loads(row["steps_completed"] or "[]")
        except Exception:
            steps = []
        snapshot = row.get("backup_path")

        module_installer = ModuleInstaller(db)
        rolled_back, warnings = await module_installer._rollback(
            tx_id=tx_id,
            steps_completed=steps,
            package_name=pkg_name,
            package_path=None,
            snapshot_path=snapshot,
            python_deps=[],
        )
        await db.execute(
            "UPDATE install_transactions SET status = 'rolled_back', finished_at = datetime('now') "
            "WHERE id = ?",
            [tx_id],
        )
        results.append({
            "transaction_id": tx_id,
            "package_name": pkg_name,
            "steps_completed": steps,
            "rolled_back": rolled_back,
            "warnings": warnings,
        })
        log.info("repair_rollback", tx_id=tx_id, name=pkg_name, success=rolled_back)

    return {
        "transactions": results,
        "message": f"Rolled back {len(results)} in-progress transaction(s).",
    }


# ---------------------------------------------------------------------------
# Registry management
# ---------------------------------------------------------------------------


@router.get(
    "/registries",
    summary="List configured registries",
)
async def list_registries(
    request: Request,
    db: UserDB = Depends(get_userdb),
) -> dict:
    """List all configured package registries with their package counts."""
    registry_client = _get_registry_client(request)
    rows = await db.fetch_all(
        "SELECT name, git_url, added_at, last_refreshed FROM installed_registries ORDER BY name"
    )
    items = []
    for row in rows:
        count = (
            registry_client.count_packages(row["name"])
            if registry_client
            else 0
        )
        items.append({
            "name": row["name"],
            "git_url": row["git_url"],
            "added_at": row["added_at"],
            "last_refreshed": row.get("last_refreshed"),
            "package_count": count,
        })
    return {"items": items, "total": len(items)}


@router.post(
    "/registries",
    summary="Add a package registry",
    status_code=201,
)
async def add_registry(
    body: RegistryAddRequest,
    request: Request,
    db: UserDB = Depends(get_userdb),
) -> dict:
    """Clone a registry Git repo and register it.

    The registry must contain an index.json at its root.
    """
    registry_client = _get_registry_client(request)

    # Check for duplicates.
    existing = await db.fetch_one(
        "SELECT name FROM installed_registries WHERE name = ?", [body.name]
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": f"Registry '{body.name}' is already configured.",
                "suggestion": "Use POST /api/registries/refresh to update it.",
            },
        )

    if registry_client:
        try:
            await registry_client.clone_registry(body.name, body.git_url)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": f"Failed to clone registry '{body.name}': {exc}",
                    "git_url": body.git_url,
                },
            )

    await db.execute(
        """
        INSERT INTO installed_registries (name, git_url, added_at)
        VALUES (?, ?, datetime('now'))
        """,
        [body.name, body.git_url],
    )

    package_count = registry_client.count_packages(body.name) if registry_client else 0
    log.info("registry_added", name=body.name, packages=package_count)

    return {
        "name": body.name,
        "git_url": body.git_url,
        "added_at": "now",
        "package_count": package_count,
    }


@router.delete(
    "/registries/{name}",
    summary="Remove a registry",
)
async def remove_registry(
    name: str,
    request: Request,
    db: UserDB = Depends(get_userdb),
) -> dict:
    """Remove a configured registry and delete its local clone."""
    row = await db.fetch_one(
        "SELECT name FROM installed_registries WHERE name = ?", [name]
    )
    if not row:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Registry '{name}' is not configured.",
                "suggestion": "Use GET /api/registries to list configured registries.",
            },
        )

    registry_client = _get_registry_client(request)
    if registry_client:
        registry_client.remove_registry(name)

    await db.execute(
        "DELETE FROM installed_registries WHERE name = ?", [name]
    )
    log.info("registry_removed", name=name)
    return {"removed": name}


@router.post(
    "/registries/refresh",
    summary="Refresh all registries",
)
async def refresh_registries(
    request: Request,
    db: UserDB = Depends(get_userdb),
) -> dict:
    """Pull the latest index.json from all configured registries.

    Returns per-registry refresh results. Errors do not abort other refreshes.
    """
    registry_client = _get_registry_client(request)
    rows = await db.fetch_all("SELECT name FROM installed_registries")
    names = [r["name"] for r in rows]

    if not names:
        return {"refreshed": [], "errors": {}}

    results: dict[str, str | None] = {}
    if registry_client:
        results = await registry_client.refresh_all(names)
    else:
        results = {n: "Registry client not available" for n in names}

    # Update last_refreshed for successful refreshes.
    for name, error in results.items():
        if error is None:
            await db.execute(
                "UPDATE installed_registries SET last_refreshed = datetime('now') WHERE name = ?",
                [name],
            )

    refreshed = [n for n, e in results.items() if e is None]
    errors = {n: e for n, e in results.items() if e is not None}

    log.info("registries_refreshed", count=len(refreshed), errors=len(errors))
    return {"refreshed": refreshed, "errors": errors}
