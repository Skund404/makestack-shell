"""Workshop routes — CRUD for user-defined organisational containers.

Workshops are pure UserDB operations. Core is never involved.
"""

import re
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import Path as FPath

from ..dependencies import get_userdb
from pydantic import BaseModel as _PydanticBaseModel

from ..models import (
    ActiveWorkshopSet,
    NavItem,
    PaginatedList,
    Workshop,
    WorkshopCreate,
    WorkshopMember,
    WorkshopMemberAdd,
    WorkshopModule,
    WorkshopModuleAdd,
    WorkshopModuleUpdate,
    WorkshopNav,
    WorkshopUpdate,
    WorkshopWithMembers,
)
from ..userdb import UserDB

log = structlog.get_logger().bind(component="workshops_router")

router = APIRouter(prefix="/api/workshops", tags=["workshops"])

_DEFAULT_USER_ID = "default"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(name: str) -> str:
    """Convert a name to a URL-safe slug (lowercase, hyphens, trimmed)."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "workshop"


def _row_to_workshop(row: dict) -> Workshop:
    return Workshop(
        id=row["id"],
        name=row["name"],
        slug=row["slug"],
        description=row["description"] or "",
        icon=row["icon"] or "",
        color=row["color"] or "",
        sort_order=row["sort_order"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def _get_or_404(workshop_id: str, db: UserDB) -> dict:
    row = await db.fetch_one("SELECT * FROM workshops WHERE id = ?", [workshop_id])
    if not row:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Workshop not found",
                "workshop_id": workshop_id,
                "suggestion": "Use GET /api/workshops to list available workshops",
            },
        )
    return row


# ---------------------------------------------------------------------------
# Active workshop (declared before /{id} to prevent routing collision)
# ---------------------------------------------------------------------------


@router.put("/active", summary="Set the active workshop context")
async def set_active_workshop(
    payload: ActiveWorkshopSet,
    db: UserDB = Depends(get_userdb),
) -> dict:
    """Set or clear the active workshop context for the default user.

    Stored as a user preference under the key ``active_workshop_id``.
    """
    import json

    if payload.workshop_id:
        await _get_or_404(payload.workshop_id, db)

    value = json.dumps(payload.workshop_id)
    await db.execute(
        """
        INSERT INTO user_preferences (user_id, key, value)
        VALUES (?, 'active_workshop_id', ?)
        ON CONFLICT (user_id, key) DO UPDATE SET value = excluded.value
        """,
        [_DEFAULT_USER_ID, value],
    )
    log.info("active_workshop_set", workshop_id=payload.workshop_id)
    return {"active_workshop_id": payload.workshop_id}


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedList[Workshop], summary="List workshops")
async def list_workshops(
    limit: int = 50,
    offset: int = 0,
    db: UserDB = Depends(get_userdb),
) -> PaginatedList[Workshop]:
    """List all workshops ordered by sort_order then name."""
    total = await db.count("workshops")
    rows = await db.fetch_all(
        "SELECT * FROM workshops ORDER BY sort_order ASC, name ASC LIMIT ? OFFSET ?",
        [limit, offset],
    )
    return PaginatedList(
        items=[_row_to_workshop(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Get single workshop with members
# ---------------------------------------------------------------------------


@router.get("/{workshop_id}", response_model=WorkshopWithMembers, summary="Get a workshop")
async def get_workshop(
    workshop_id: str = FPath(...),
    db: UserDB = Depends(get_userdb),
) -> WorkshopWithMembers:
    """Get a single workshop with its full primitive member list."""
    row = await _get_or_404(workshop_id, db)
    member_rows = await db.fetch_all(
        "SELECT * FROM workshop_members WHERE workshop_id = ? ORDER BY added_at ASC",
        [workshop_id],
    )
    members = [
        WorkshopMember(
            primitive_path=m["primitive_path"],
            primitive_type=m["primitive_type"],
            added_at=m["added_at"],
        )
        for m in member_rows
    ]
    ws = _row_to_workshop(row)
    return WorkshopWithMembers(**ws.model_dump(), members=members)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@router.post("", response_model=Workshop, status_code=201, summary="Create a workshop")
async def create_workshop(
    payload: WorkshopCreate,
    db: UserDB = Depends(get_userdb),
) -> Workshop:
    """Create a new workshop. Slug is auto-generated from the name."""
    now = _now()
    workshop_id = str(uuid.uuid4())
    base_slug = _slugify(payload.name)

    # Ensure slug uniqueness: append a short UUID suffix if needed.
    slug = base_slug
    existing = await db.fetch_one("SELECT id FROM workshops WHERE slug = ?", [slug])
    if existing:
        slug = f"{base_slug}-{workshop_id[:8]}"

    row = await db.execute_returning(
        """
        INSERT INTO workshops (id, name, slug, description, icon, color, sort_order, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
        RETURNING *
        """,
        [
            workshop_id,
            payload.name,
            slug,
            payload.description,
            payload.icon,
            payload.color,
            now,
            now,
        ],
    )
    log.info("workshop_created", id=workshop_id, name=payload.name)
    return _row_to_workshop(row)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@router.put("/{workshop_id}", response_model=Workshop, summary="Update a workshop")
async def update_workshop(
    workshop_id: str = FPath(...),
    payload: WorkshopUpdate = ...,
    db: UserDB = Depends(get_userdb),
) -> Workshop:
    """Update workshop fields. Only provided fields are updated."""
    await _get_or_404(workshop_id, db)

    updates: dict = {}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.description is not None:
        updates["description"] = payload.description
    if payload.icon is not None:
        updates["icon"] = payload.icon
    if payload.color is not None:
        updates["color"] = payload.color
    if payload.sort_order is not None:
        updates["sort_order"] = payload.sort_order

    if not updates:
        row = await db.fetch_one("SELECT * FROM workshops WHERE id = ?", [workshop_id])
        return _row_to_workshop(row)  # type: ignore[arg-type]

    updates["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [workshop_id]
    updated = await db.execute_returning(
        f"UPDATE workshops SET {set_clause} WHERE id = ? RETURNING *",  # noqa: S608
        values,
    )
    log.info("workshop_updated", id=workshop_id, fields=list(updates.keys()))
    return _row_to_workshop(updated)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete("/{workshop_id}", status_code=204, summary="Delete a workshop")
async def delete_workshop(
    workshop_id: str = FPath(...),
    db: UserDB = Depends(get_userdb),
) -> None:
    """Delete a workshop. Members are removed by CASCADE; primitives are unaffected."""
    await _get_or_404(workshop_id, db)
    await db.execute("DELETE FROM workshops WHERE id = ?", [workshop_id])
    log.info("workshop_deleted", id=workshop_id)


# ---------------------------------------------------------------------------
# Members — add / remove
# ---------------------------------------------------------------------------


@router.post(
    "/{workshop_id}/members",
    response_model=WorkshopMember,
    status_code=201,
    summary="Add a primitive to a workshop",
)
async def add_member(
    workshop_id: str = FPath(...),
    payload: WorkshopMemberAdd = ...,
    db: UserDB = Depends(get_userdb),
) -> WorkshopMember:
    """Add a catalogue primitive reference to a workshop.

    Idempotent — if the primitive is already a member, returns the existing record.
    """
    await _get_or_404(workshop_id, db)

    existing = await db.fetch_one(
        "SELECT * FROM workshop_members WHERE workshop_id = ? AND primitive_path = ?",
        [workshop_id, payload.primitive_path],
    )
    if existing:
        return WorkshopMember(
            primitive_path=existing["primitive_path"],
            primitive_type=existing["primitive_type"],
            added_at=existing["added_at"],
        )

    now = _now()
    await db.execute(
        """
        INSERT INTO workshop_members (workshop_id, primitive_path, primitive_type, added_at)
        VALUES (?, ?, ?, ?)
        """,
        [workshop_id, payload.primitive_path, payload.primitive_type, now],
    )
    log.info("workshop_member_added", workshop_id=workshop_id, path=payload.primitive_path)
    return WorkshopMember(
        primitive_path=payload.primitive_path,
        primitive_type=payload.primitive_type,
        added_at=now,
    )


@router.delete(
    "/{workshop_id}/members/{path:path}",
    status_code=204,
    summary="Remove a primitive from a workshop",
)
async def remove_member(
    workshop_id: str = FPath(...),
    path: str = FPath(...),
    db: UserDB = Depends(get_userdb),
) -> None:
    """Remove a primitive reference from a workshop. Does not delete the primitive."""
    await _get_or_404(workshop_id, db)
    member = await db.fetch_one(
        "SELECT workshop_id FROM workshop_members WHERE workshop_id = ? AND primitive_path = ?",
        [workshop_id, path],
    )
    if not member:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Member not found",
                "workshop_id": workshop_id,
                "primitive_path": path,
                "suggestion": "Use GET /api/workshops/{id} to see the member list",
            },
        )
    await db.execute(
        "DELETE FROM workshop_members WHERE workshop_id = ? AND primitive_path = ?",
        [workshop_id, path],
    )
    log.info("workshop_member_removed", workshop_id=workshop_id, path=path)


# ---------------------------------------------------------------------------
# Module associations — list / add / remove
# ---------------------------------------------------------------------------

_SHELL_NAV_ITEMS = [
    NavItem(id="inventory", label="Inventory", route="/inventory", icon="package", source="shell"),
    NavItem(id="catalogue", label="Catalogue", route="/catalogue", icon="book", source="shell"),
    NavItem(id="workshops", label="Workshops", route="/workshops", icon="layers", source="shell"),
]


@router.get(
    "/{workshop_id}/modules",
    summary="List modules associated with a workshop",
)
async def list_workshop_modules(
    workshop_id: str = FPath(...),
    request: Request = None,
    db: UserDB = Depends(get_userdb),
) -> list[dict]:
    """List all module associations for a workshop, ordered by sort_order then name.

    Includes app_mode data for each module so the workshop home can render
    launcher cards without extra fetches.
    """
    await _get_or_404(workshop_id, db)
    rows = await db.fetch_all(
        "SELECT * FROM workshop_modules WHERE workshop_id = ? ORDER BY sort_order ASC, module_name ASC",
        [workshop_id],
    )
    registry = getattr(request.app.state, "module_registry", None) if request else None

    result = []
    for r in rows:
        item: dict = {
            "workshop_id": r["workshop_id"],
            "module_name": r["module_name"],
            "sort_order": r["sort_order"],
            "enabled": bool(r["enabled"]),
        }
        # Enrich with app_mode + display_name from loaded manifest
        if registry is not None:
            loaded = registry.get_module(r["module_name"])
            if loaded is not None and loaded.manifest.app_mode is not None:
                item["app_mode"] = loaded.manifest.app_mode.model_dump()
                item["display_name"] = loaded.manifest.display_name
        result.append(item)
    return result


@router.post(
    "/{workshop_id}/modules",
    response_model=WorkshopModule,
    status_code=201,
    summary="Associate a module with a workshop",
)
async def add_workshop_module(
    workshop_id: str = FPath(...),
    payload: WorkshopModuleAdd = ...,
    db: UserDB = Depends(get_userdb),
) -> WorkshopModule:
    """Associate a module with a workshop.

    Idempotent — if the association already exists, returns the existing record.
    The module does not need to be loaded for the association to be stored.
    """
    await _get_or_404(workshop_id, db)

    existing = await db.fetch_one(
        "SELECT * FROM workshop_modules WHERE workshop_id = ? AND module_name = ?",
        [workshop_id, payload.module_name],
    )
    if existing:
        return WorkshopModule(
            workshop_id=workshop_id,
            module_name=existing["module_name"],
            sort_order=existing["sort_order"],
            enabled=bool(existing["enabled"]),
        )

    await db.execute(
        "INSERT INTO workshop_modules (workshop_id, module_name, sort_order, enabled) VALUES (?, ?, ?, 1)",
        [workshop_id, payload.module_name, payload.sort_order],
    )
    log.info("workshop_module_added", workshop_id=workshop_id, module=payload.module_name)
    return WorkshopModule(
        workshop_id=workshop_id,
        module_name=payload.module_name,
        sort_order=payload.sort_order,
        enabled=True,
    )


@router.delete(
    "/{workshop_id}/modules/{name}",
    status_code=204,
    summary="Remove a module association from a workshop",
)
async def remove_workshop_module(
    workshop_id: str = FPath(...),
    name: str = FPath(...),
    db: UserDB = Depends(get_userdb),
) -> None:
    """Remove a module association from a workshop.

    The association row is deleted. The module itself and its data are unaffected.
    """
    await _get_or_404(workshop_id, db)
    row = await db.fetch_one(
        "SELECT workshop_id FROM workshop_modules WHERE workshop_id = ? AND module_name = ?",
        [workshop_id, name],
    )
    if not row:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Module association not found",
                "workshop_id": workshop_id,
                "module_name": name,
                "suggestion": "Use GET /api/workshops/{id}/modules to see current associations",
            },
        )
    await db.execute(
        "DELETE FROM workshop_modules WHERE workshop_id = ? AND module_name = ?",
        [workshop_id, name],
    )
    log.info("workshop_module_removed", workshop_id=workshop_id, module=name)


@router.patch(
    "/{workshop_id}/modules/{name}",
    response_model=WorkshopModule,
    summary="Update a workshop-module association",
)
async def update_workshop_module(
    workshop_id: str = FPath(...),
    name: str = FPath(...),
    payload: WorkshopModuleUpdate = ...,
    db: UserDB = Depends(get_userdb),
) -> WorkshopModule:
    """Update the sort_order of a module association.

    Used by the workshop settings page to reorder modules in the nav.
    """
    await _get_or_404(workshop_id, db)
    row = await db.fetch_one(
        "SELECT * FROM workshop_modules WHERE workshop_id = ? AND module_name = ?",
        [workshop_id, name],
    )
    if not row:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Module association not found",
                "workshop_id": workshop_id,
                "module_name": name,
                "suggestion": "Use GET /api/workshops/{id}/modules to see current associations",
            },
        )
    updated = await db.execute_returning(
        "UPDATE workshop_modules SET sort_order = ? WHERE workshop_id = ? AND module_name = ? RETURNING *",
        [payload.sort_order, workshop_id, name],
    )
    log.info("workshop_module_updated", workshop_id=workshop_id, module=name, sort_order=payload.sort_order)
    return WorkshopModule(
        workshop_id=updated["workshop_id"],
        module_name=updated["module_name"],
        sort_order=updated["sort_order"],
        enabled=bool(updated["enabled"]),
    )


# ---------------------------------------------------------------------------
# Add app — bundled install + assign flow
# ---------------------------------------------------------------------------


class AddAppRequest(_PydanticBaseModel):
    """Request body for the bundled install+assign flow."""

    package_name: str
    source: str | None = None  # git URL or local path (optional — name resolved via registry)


@router.post(
    "/{workshop_id}/add-app",
    status_code=201,
    summary="Install a module and assign it to a workshop in one step",
)
async def add_app(
    workshop_id: str = FPath(...),
    payload: AddAppRequest = ...,
    request: Request = None,
    db: UserDB = Depends(get_userdb),
) -> dict:
    """Bundled install+assign: resolves dependencies, installs missing modules,
    and assigns all of them to the workshop.

    If the module is already installed, it is simply assigned to the workshop.
    """
    await _get_or_404(workshop_id, db)

    from ..routers.packages import (
        install_package as _install_package,
        _get_registry_client,
    )
    from ..models import PackageInstallRequest

    # Check if already installed
    mod_row = await db.fetch_one(
        "SELECT name FROM installed_modules WHERE name = ?", [payload.package_name]
    )

    installed_names: list[str] = []
    install_results: list[dict] = []
    restart_required = False

    if not mod_row:
        # Need to install — resolve dependencies first
        registry_client = _get_registry_client(request)
        pkg_info = None
        if registry_client and not payload.source:
            pkg_info = registry_client.resolve(payload.package_name)

        # Read the manifest to find required peers
        required_peers: list[str] = []
        if pkg_info or payload.source:
            try:
                from ..routers.packages import _get_package_cache, _load_package_manifest
                from pathlib import Path

                package_cache = _get_package_cache(request)
                if payload.source and not payload.source.startswith("http"):
                    manifest = _load_package_manifest(payload.source)
                elif pkg_info and package_cache:
                    cache_path = await package_cache.fetch(
                        pkg_info.name, pkg_info.git_url, pkg_info.type, subdir=pkg_info.subdir
                    )
                    manifest = _load_package_manifest(str(cache_path))
                else:
                    manifest = None

                if manifest:
                    peers = manifest.raw.get("peer_modules", {}) if hasattr(manifest, "raw") else {}
                    if not peers and hasattr(manifest, "model_dump"):
                        # PackageManifest may not have peer_modules; check raw JSON
                        pass
            except Exception:
                required_peers = []

        # Install the target package
        install_req = PackageInstallRequest(
            name=payload.package_name,
            source=payload.source,
        )
        try:
            from ..dependencies import get_core_client
            core = await get_core_client(request)
            result = await _install_package(install_req, request, db, core)
            install_results.append({
                "package_name": result.package_name,
                "version": result.version,
                "restart_required": result.restart_required,
            })
            installed_names.append(payload.package_name)
            if result.restart_required:
                restart_required = True
        except HTTPException as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={
                    "error": f"Failed to install '{payload.package_name}'",
                    "install_error": exc.detail,
                    "suggestion": "Check the package name or source and try again.",
                },
            )
    else:
        installed_names.append(payload.package_name)

    # Assign the module (and any peers) to the workshop
    assigned: list[str] = []
    for name in installed_names:
        existing = await db.fetch_one(
            "SELECT module_name FROM workshop_modules WHERE workshop_id = ? AND module_name = ?",
            [workshop_id, name],
        )
        if not existing:
            await db.execute(
                "INSERT INTO workshop_modules (workshop_id, module_name, sort_order, enabled) VALUES (?, ?, ?, 1)",
                [workshop_id, name, 0],
            )
            assigned.append(name)

    log.info("add_app", workshop_id=workshop_id, package=payload.package_name, assigned=assigned)
    return {
        "package_name": payload.package_name,
        "installed": install_results,
        "assigned": assigned,
        "restart_required": restart_required,
    }


# ---------------------------------------------------------------------------
# Nav — intersection of DB associations and loaded module registry
# ---------------------------------------------------------------------------


@router.get(
    "/{workshop_id}/nav",
    response_model=WorkshopNav,
    summary="Computed nav items for a workshop",
)
async def get_workshop_nav(
    request: Request,
    workshop_id: str = FPath(...),
    db: UserDB = Depends(get_userdb),
) -> WorkshopNav:
    """Return the computed nav item list for a workshop.

    Only modules present in BOTH the workshop_modules table (enabled=1) AND
    app.state.module_registry appear in the result. A module that is associated
    but not loaded is silently absent — its association row is never removed.

    Shell fallback views (Inventory, Catalogue, Workshops) are always appended.
    """
    await _get_or_404(workshop_id, db)
    rows = await db.fetch_all(
        "SELECT * FROM workshop_modules WHERE workshop_id = ? AND enabled = 1 ORDER BY sort_order ASC, module_name ASC",
        [workshop_id],
    )
    registry = request.app.state.module_registry
    items: list[NavItem] = []

    for row in rows:
        module_name = row["module_name"]
        if not registry.is_loaded(module_name):
            continue  # silently absent — association row never removed

        loaded = registry.get_module(module_name)
        if loaded and loaded.manifest.app_mode and loaded.manifest.app_mode.enabled:
            continue  # app_mode modules use their own branded sidebar — skip shell nav

        views = registry.get_module_views(module_name)
        if views:
            # Use declared views, ordered by their sort_order.
            for view in sorted(views, key=lambda v: v.sort_order):
                items.append(
                    NavItem(
                        id=view.id,
                        label=view.label,
                        route=view.route,
                        icon=view.icon,
                        source="module",
                        replaces_shell_view=view.replaces_shell_view,
                    )
                )
        else:
            # Module is loaded but has no views declared — generate a default entry.
            items.append(
                NavItem(
                    id=module_name,
                    label=module_name.replace("-", " ").title(),
                    route=f"/modules/{module_name}",
                    icon="",
                    source="module",
                )
            )

    items.extend(_SHELL_NAV_ITEMS)
    return WorkshopNav(items=items)
