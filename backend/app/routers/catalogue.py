"""Catalogue proxy routes — pass-through to makestack-core.

Every endpoint here proxies a Core API call with:
  - Consistent response shapes (Pydantic models)
  - Actionable 503 errors when Core is unavailable
  - structlog instrumentation
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as FPath

from ..core_client import CatalogueClient, CoreNotFoundError, CoreUnavailableError, CoreValidationError
from ..dependencies import get_core_client
from ..models import DiffResponse, HistoryResponse, PaginatedList, Primitive, PrimitiveCreate, PrimitiveUpdate, Relationship

log = structlog.get_logger().bind(component="catalogue_router")

router = APIRouter(prefix="/api/catalogue", tags=["catalogue"])

# ---------------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------------


def _unavailable(core_url: str) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "error": "Catalogue unavailable",
            "detail": "Core is not connected",
            "suggestion": f"Check that makestack-core is running at {core_url}",
        },
    )


def _not_found(path: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "error": "Primitive not found",
            "path": path,
            "suggestion": "Use GET /api/catalogue/search to find the correct path",
        },
    )


def _bad_request(message: str) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"error": "Catalogue validation error", "detail": message},
    )


# ---------------------------------------------------------------------------
# List and search
# ---------------------------------------------------------------------------


@router.get("/primitives", response_model=PaginatedList[Primitive], summary="List primitives")
async def list_primitives(
    type: str | None = Query(None, description="Filter by primitive type: tool, material, technique, workflow, project, event"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    core: CatalogueClient = Depends(get_core_client),
) -> PaginatedList[Primitive]:
    """List all catalogue primitives, optionally filtered by type."""
    try:
        items = await core.list_primitives(type_filter=type)
    except CoreUnavailableError as exc:
        raise _unavailable(exc.url) from exc
    # Apply offset/limit in-memory (Core doesn't paginate list yet).
    total = len(items)
    page = items[offset : offset + limit]
    return PaginatedList(items=page, total=total, limit=limit, offset=offset)


@router.get("/search", response_model=PaginatedList[Primitive], summary="Search catalogue")
async def search_catalogue(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    core: CatalogueClient = Depends(get_core_client),
) -> PaginatedList[Primitive]:
    """Full-text search across name, description, tags, and properties."""
    try:
        items = await core.search(q)
    except CoreUnavailableError as exc:
        raise _unavailable(exc.url) from exc
    total = len(items)
    page = items[offset : offset + limit]
    return PaginatedList(items=page, total=total, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------


@router.get(
    "/relationships/{path:path}",
    response_model=list[Relationship],
    summary="Get relationships for a primitive",
)
async def get_relationships(
    path: str = FPath(..., description="Primitive path (e.g. tools/stitching-chisel/manifest.json)"),
    core: CatalogueClient = Depends(get_core_client),
) -> list[Relationship]:
    """Return all bidirectional relationships for a primitive."""
    try:
        return await core.get_relationships(path)
    except CoreUnavailableError as exc:
        raise _unavailable(exc.url) from exc
    except CoreNotFoundError:
        raise _not_found(path)


# ---------------------------------------------------------------------------
# Version history and diff — must be declared before the bare {path:path} GET
# to prevent FastAPI routing ambiguity.
# ---------------------------------------------------------------------------


@router.get(
    "/primitives/{path:path}/history",
    response_model=HistoryResponse,
    summary="Get version history for a primitive",
)
async def get_primitive_history(
    path: str = FPath(...),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    core: CatalogueClient = Depends(get_core_client),
) -> HistoryResponse:
    """Paginated commit history for a primitive (proxied from Core)."""
    try:
        return await core.get_history(path, limit=limit, offset=offset)
    except CoreUnavailableError as exc:
        raise _unavailable(exc.url) from exc
    except CoreNotFoundError:
        raise _not_found(path)


@router.get(
    "/primitives/{path:path}/diff",
    response_model=DiffResponse,
    summary="Get structured diff between two versions",
)
async def get_primitive_diff(
    path: str = FPath(...),
    from_hash: str | None = Query(None, alias="from", description="Starting commit hash"),
    to_hash: str | None = Query(None, alias="to", description="Ending commit hash (defaults to HEAD)"),
    core: CatalogueClient = Depends(get_core_client),
) -> DiffResponse:
    """Structured field-level diff between two versions of a primitive."""
    try:
        return await core.get_diff(path, from_hash=from_hash, to_hash=to_hash)
    except CoreUnavailableError as exc:
        raise _unavailable(exc.url) from exc
    except CoreNotFoundError:
        raise _not_found(path)


@router.get(
    "/primitives/{path:path}/hash",
    summary="Get current commit hash for a primitive",
)
async def get_primitive_hash(
    path: str = FPath(...),
    core: CatalogueClient = Depends(get_core_client),
) -> dict:
    """Return the last commit hash that touched this specific primitive."""
    try:
        commit_hash = await core.get_commit_hash(path)
        return {"path": path, "hash": commit_hash}
    except CoreUnavailableError as exc:
        raise _unavailable(exc.url) from exc
    except CoreNotFoundError:
        raise _not_found(path)


# ---------------------------------------------------------------------------
# Single primitive CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/primitives/{path:path}",
    response_model=Primitive,
    summary="Get a primitive",
)
async def get_primitive(
    path: str = FPath(..., description="Primitive path (e.g. tools/stitching-chisel/manifest.json)"),
    at: str | None = Query(None, description="Commit hash to read historical version"),
    core: CatalogueClient = Depends(get_core_client),
) -> Primitive:
    """Get a primitive at its current version or at a specific historical commit."""
    try:
        if at:
            return await core.get_primitive_at_version(path, at)
        return await core.get_primitive(path)
    except CoreUnavailableError as exc:
        raise _unavailable(exc.url) from exc
    except CoreNotFoundError:
        raise _not_found(path)


@router.post(
    "/primitives",
    response_model=Primitive,
    status_code=201,
    summary="Create a primitive",
)
async def create_primitive(
    payload: PrimitiveCreate,
    core: CatalogueClient = Depends(get_core_client),
) -> Primitive:
    """Create a new primitive in the catalogue.

    Core auto-generates id, slug, created, and modified.
    Returns 503 if Core is unreachable or the data directory is not a git repo.
    """
    try:
        return await core.create_primitive(payload)
    except CoreUnavailableError as exc:
        raise _unavailable(exc.url) from exc
    except CoreValidationError as exc:
        raise _bad_request(exc.message) from exc


@router.put(
    "/primitives/{path:path}",
    response_model=Primitive,
    summary="Update a primitive",
)
async def update_primitive(
    path: str = FPath(...),
    payload: PrimitiveUpdate = ...,
    core: CatalogueClient = Depends(get_core_client),
) -> Primitive:
    """Update a primitive. The request body must include id, type, name, and slug."""
    try:
        return await core.update_primitive(path, payload)
    except CoreUnavailableError as exc:
        raise _unavailable(exc.url) from exc
    except CoreNotFoundError:
        raise _not_found(path)
    except CoreValidationError as exc:
        raise _bad_request(exc.message) from exc


@router.delete(
    "/primitives/{path:path}",
    status_code=204,
    summary="Delete a primitive",
)
async def delete_primitive(
    path: str = FPath(...),
    core: CatalogueClient = Depends(get_core_client),
) -> None:
    """Delete a primitive and its parent directory from the catalogue."""
    try:
        await core.delete_primitive(path)
    except CoreUnavailableError as exc:
        raise _unavailable(exc.url) from exc
    except CoreNotFoundError:
        raise _not_found(path)
