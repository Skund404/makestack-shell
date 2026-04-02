"""Binary file reference routes — proxy to makestack-core /api/binary-refs.

Binary refs are git-backed JSON pointer files that track binary assets
(photos, videos, 3D models, documents) without storing them in Git.
Each ref records local path, backup location, checksum, and an optional
link to a catalogue primitive.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as FPath

from ..core_client import CatalogueClient, CoreNotFoundError, CoreUnavailableError, CoreValidationError
from ..dependencies import get_core_client
from ..models import BinaryRef, BinaryRefCreate, BinaryRefUpdate

log = structlog.get_logger().bind(component="binary_refs_router")

router = APIRouter(prefix="/api/binary-refs", tags=["binary-refs"])


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


def _not_found(slug: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "error": "Binary ref not found",
            "slug": slug,
            "suggestion": "Use GET /api/binary-refs to list all binary refs",
        },
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=list[BinaryRef], summary="List binary refs")
async def list_binary_refs(
    asset_type: str | None = Query(None, description="Filter by asset type (photo, video, document, model, etc.)"),
    primitive_ref: str | None = Query(None, description="Filter by linked primitive path"),
    core: CatalogueClient = Depends(get_core_client),
) -> list[BinaryRef]:
    """List all binary file references, optionally filtered by asset type or primitive."""
    try:
        return await core.list_binary_refs(asset_type=asset_type, primitive_ref=primitive_ref)
    except CoreUnavailableError as exc:
        raise _unavailable(exc.url) from exc


@router.get("/{slug}", response_model=BinaryRef, summary="Get a binary ref")
async def get_binary_ref(
    slug: str = FPath(..., description="Binary ref slug"),
    core: CatalogueClient = Depends(get_core_client),
) -> BinaryRef:
    """Get a single binary file reference by slug."""
    try:
        return await core.get_binary_ref(slug)
    except CoreUnavailableError as exc:
        raise _unavailable(exc.url) from exc
    except CoreNotFoundError:
        raise _not_found(slug)


@router.post("", response_model=BinaryRef, status_code=201, summary="Create a binary ref")
async def create_binary_ref(
    payload: BinaryRefCreate,
    core: CatalogueClient = Depends(get_core_client),
) -> BinaryRef:
    """Create a new binary file reference.

    Core auto-generates id, slug (from filename), and timestamps.
    The binary file itself is not stored — only the pointer metadata.
    """
    try:
        return await core.create_binary_ref(payload)
    except CoreUnavailableError as exc:
        raise _unavailable(exc.url) from exc
    except CoreValidationError as exc:
        raise HTTPException(status_code=400, detail={"error": exc.message}) from exc


@router.put("/{slug}", response_model=BinaryRef, summary="Update a binary ref")
async def update_binary_ref(
    slug: str = FPath(...),
    payload: BinaryRefUpdate = ...,
    core: CatalogueClient = Depends(get_core_client),
) -> BinaryRef:
    """Update an existing binary file reference."""
    try:
        return await core.update_binary_ref(slug, payload)
    except CoreUnavailableError as exc:
        raise _unavailable(exc.url) from exc
    except CoreNotFoundError:
        raise _not_found(slug)
    except CoreValidationError as exc:
        raise HTTPException(status_code=400, detail={"error": exc.message}) from exc


@router.delete("/{slug}", status_code=204, summary="Delete a binary ref")
async def delete_binary_ref(
    slug: str = FPath(...),
    core: CatalogueClient = Depends(get_core_client),
) -> None:
    """Delete a binary file reference. The actual binary file is not deleted."""
    try:
        await core.delete_binary_ref(slug)
    except CoreUnavailableError as exc:
        raise _unavailable(exc.url) from exc
    except CoreNotFoundError:
        raise _not_found(slug)
