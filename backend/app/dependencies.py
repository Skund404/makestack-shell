"""FastAPI dependency injection providers.

All routers import their dependencies from here.
Singletons are stored on app.state and injected via Request.
"""

from fastapi import Request

from .core_client import CatalogueClient
from .userdb import UserDB


async def get_core_client(request: Request) -> CatalogueClient:
    """Return the singleton CatalogueClient stored on app.state."""
    return request.app.state.core_client  # type: ignore[no-any-return]


async def get_userdb(request: Request) -> UserDB:
    """Return the singleton UserDB connection stored on app.state."""
    return request.app.state.userdb  # type: ignore[no-any-return]


async def get_dev_mode(request: Request) -> bool:
    """Return whether the Shell is running in dev mode."""
    return request.app.state.dev_mode  # type: ignore[no-any-return]
