"""Version history and diff routes.

These are standalone Shell-namespaced routes (separate from the catalogue proxy)
so the frontend and MCP server have a clean API surface for version operations.
They proxy Core's history and diff endpoints via the CatalogueClient.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as FPath

from ..core_client import CatalogueClient, CoreNotFoundError, CoreUnavailableError
from ..dependencies import get_core_client
from ..models import DiffResponse, HistoryResponse

log = structlog.get_logger().bind(component="version_router")

router = APIRouter(prefix="/api/version", tags=["version"])


def _unavailable(url: str) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "error": "Catalogue unavailable",
            "detail": "Core is not connected",
            "suggestion": f"Check that makestack-core is running at {url}",
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


@router.get(
    "/{path:path}/history",
    response_model=HistoryResponse,
    summary="Get commit history for a primitive",
)
async def get_history(
    path: str = FPath(..., description="Primitive path (e.g. tools/stitching-chisel/manifest.json)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    core: CatalogueClient = Depends(get_core_client),
) -> HistoryResponse:
    """Paginated commit history for a catalogue primitive."""
    try:
        return await core.get_history(path, limit=limit, offset=offset)
    except CoreUnavailableError as exc:
        raise _unavailable(exc.url) from exc
    except CoreNotFoundError:
        raise _not_found(path)


@router.get(
    "/{path:path}/diff",
    response_model=DiffResponse,
    summary="Get structured diff between two versions of a primitive",
)
async def get_diff(
    path: str = FPath(...),
    from_hash: str | None = Query(None, alias="from", description="Starting commit hash"),
    to_hash: str | None = Query(None, alias="to", description="Ending commit hash (defaults to HEAD)"),
    core: CatalogueClient = Depends(get_core_client),
) -> DiffResponse:
    """Structured field-level diff between two versions of a primitive.

    If ``from`` is omitted, defaults to the parent of ``to``.
    If ``to`` is omitted, defaults to HEAD.
    """
    try:
        return await core.get_diff(path, from_hash=from_hash, to_hash=to_hash)
    except CoreUnavailableError as exc:
        raise _unavailable(exc.url) from exc
    except CoreNotFoundError:
        raise _not_found(path)
