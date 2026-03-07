"""SDK surface: CatalogueClient for module authors.

Module authors never construct a CatalogueClient directly. Instead, they
declare a FastAPI dependency on ``get_catalogue_client`` and let the Shell
inject the singleton via dependency injection.

This module re-exports the Shell's CatalogueClient and provides the
FastAPI dependency function that modules should use.

Usage in a module's routes.py:

    from makestack_sdk.catalogue_client import get_catalogue_client, CatalogueClient
    from fastapi import APIRouter, Depends

    router = APIRouter()

    @router.get("/my-endpoint")
    async def my_endpoint(catalogue: CatalogueClient = Depends(get_catalogue_client)):
        results = await catalogue.search("leather")
        return results
"""

from fastapi import Request

# Re-export the Shell's CatalogueClient so modules have a single import point.
from backend.app.core_client import (
    CatalogueClient,
    CoreUnavailableError,
    CoreNotFoundError,
    CoreValidationError,
)


async def get_catalogue_client(request: Request) -> CatalogueClient:
    """FastAPI dependency: inject the Shell's CatalogueClient singleton.

    This is the same client used by the Shell's own routers. Module routes
    should declare this as a Depends() parameter.
    """
    return request.app.state.core_client  # type: ignore[no-any-return]


__all__ = [
    "CatalogueClient",
    "CoreUnavailableError",
    "CoreNotFoundError",
    "CoreValidationError",
    "get_catalogue_client",
]
