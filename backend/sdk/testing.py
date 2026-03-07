"""SDK surface: Testing utilities for module authors.

Provides mock objects and a test app factory so module tests can run
without a real Shell instance, Core connection, or on-disk database.

Usage in a module's tests:

    import pytest
    import pytest_asyncio
    from makestack_sdk.testing import MockCatalogueClient, MockUserDB, create_test_app
    from my_module.backend.routes import router

    @pytest_asyncio.fixture
    async def db():
        db = MockUserDB()
        await db.setup(["CREATE TABLE inventory_stock (id TEXT PRIMARY KEY, qty INTEGER)"])
        return db

    @pytest.fixture
    def client(db):
        return create_test_app(router, userdb=db)

    async def test_list_stock(client):
        response = client.get("/stock")
        assert response.status_code == 200
"""

import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from backend.app.core_client import CatalogueClient
from backend.app.models import (
    CommitInfo,
    DiffResponse,
    HistoryResponse,
    Primitive,
    Relationship,
)
from backend.app.userdb import UserDB


# ---------------------------------------------------------------------------
# Mock CatalogueClient
# ---------------------------------------------------------------------------

_SAMPLE_PRIMITIVE = Primitive(
    id="tool-test-001",
    type="tool",
    name="Test Tool",
    slug="test-tool",
    path="tools/test-tool/manifest.json",
    created="2026-01-01T00:00:00Z",
    modified="2026-01-01T00:00:00Z",
    description="A test tool for module tests.",
    tags=["test"],
    properties={"material": "steel"},
    manifest={"id": "tool-test-001", "type": "tool", "name": "Test Tool"},
)


class MockCatalogueClient:
    """Mock CatalogueClient for use in module tests.

    Returns predictable fixture data. Attributes can be overridden before
    calling the mock methods:

        mock = MockCatalogueClient()
        mock.list_primitives = AsyncMock(return_value=[my_primitive])
    """

    def __init__(self) -> None:
        self.connected = True
        self._base_url = "http://localhost:8420"

        # Default async mocks return sensible fixture data.
        self.list_primitives = AsyncMock(return_value=[_SAMPLE_PRIMITIVE])
        self.get_primitive = AsyncMock(return_value=_SAMPLE_PRIMITIVE)
        self.get_primitive_at_version = AsyncMock(return_value=_SAMPLE_PRIMITIVE)
        self.get_commit_hash = AsyncMock(return_value="abc123def456")
        self.get_history = AsyncMock(
            return_value=HistoryResponse(
                path="tools/test-tool/manifest.json",
                total=1,
                commits=[
                    CommitInfo(
                        hash="abc123def456",
                        message="Initial commit",
                        author="Tester",
                        timestamp="2026-01-01T00:00:00Z",
                    )
                ],
            )
        )
        self.get_diff = AsyncMock(
            return_value=DiffResponse(
                path="tools/test-tool/manifest.json",
                from_hash="000",
                to_hash="abc123def456",
                from_timestamp="2026-01-01T00:00:00Z",
                to_timestamp="2026-01-01T00:00:00Z",
                changes=[],
            )
        )
        self.search = AsyncMock(return_value=[_SAMPLE_PRIMITIVE])
        self.get_relationships = AsyncMock(return_value=[])
        self.create_primitive = AsyncMock(return_value=_SAMPLE_PRIMITIVE)
        self.update_primitive = AsyncMock(return_value=_SAMPLE_PRIMITIVE)
        self.delete_primitive = AsyncMock(return_value=None)
        self.health_check = AsyncMock(return_value=True)


# ---------------------------------------------------------------------------
# MockUserDB — in-memory SQLite
# ---------------------------------------------------------------------------


class MockUserDB(UserDB):
    """In-memory UserDB for use in module tests.

    Call setup() with a list of CREATE TABLE statements to prepare the
    module's own tables before tests run.
    """

    def __init__(self) -> None:
        super().__init__(":memory:", dev_mode=True)

    async def setup(self, create_statements: list[str] | None = None) -> None:
        """Open the database, run Shell migrations, and optionally create module tables."""
        await self.open()
        await self.run_migrations()
        if create_statements:
            conn = self._require_connection()
            for stmt in create_statements:
                await conn.execute(stmt)
            await conn.commit()

    async def teardown(self) -> None:
        """Close the database."""
        await self.close()


# ---------------------------------------------------------------------------
# MockShellContext
# ---------------------------------------------------------------------------


class MockShellContext:
    """Configurable Shell context for module tests."""

    def __init__(
        self,
        user_id: str = "default",
        active_workshop_id: str | None = None,
        shell_version: str = "0.1.0",
        dev_mode: bool = True,
    ) -> None:
        self.user_id = user_id
        self.active_workshop_id = active_workshop_id
        self.shell_version = shell_version
        self.dev_mode = dev_mode


# ---------------------------------------------------------------------------
# MockPeerModules
# ---------------------------------------------------------------------------


class MockPeerModules:
    """Configurable peer modules mock for module tests."""

    def __init__(self, installed: list[str] | None = None) -> None:
        self._installed = set(installed or [])
        self._call_responses: dict[str, Any] = {}

    def register_response(self, module_name: str, path: str, response: Any) -> None:
        """Pre-register a response for a specific peer call."""
        self._call_responses[f"{module_name}:{path}"] = response

    def is_installed(self, module_name: str) -> bool:
        return module_name in self._installed

    async def call(self, module_name: str, method: str, path: str, **kwargs) -> Any:
        if not self.is_installed(module_name):
            raise ValueError(f"Mock peer module '{module_name}' is not installed")
        key = f"{module_name}:{path}"
        if key in self._call_responses:
            return self._call_responses[key]
        raise KeyError(
            f"No mock response registered for {module_name}:{path}. "
            f"Use mock_peers.register_response('{module_name}', '{path}', data)"
        )


# ---------------------------------------------------------------------------
# Test app factory
# ---------------------------------------------------------------------------


def create_test_app(
    router: Any,
    *,
    userdb: MockUserDB | None = None,
    catalogue: MockCatalogueClient | None = None,
    context: MockShellContext | None = None,
    peers: MockPeerModules | None = None,
    dev_mode: bool = True,
):
    """Create a test FastAPI app with the given module router and mocked dependencies.

    Returns an httpx.AsyncClient-compatible test client via the ASGI transport.

    Example:

        db = MockUserDB()
        await db.setup(["CREATE TABLE my_module_items (id TEXT PRIMARY KEY)"])
        client = create_test_app(router, userdb=db)
        response = await client.get("/my-endpoint")
    """
    import httpx
    from fastapi import FastAPI
    from httpx import ASGITransport

    _db = userdb or MockUserDB()
    _catalogue = catalogue or MockCatalogueClient()
    _context = context or MockShellContext()
    _peers = peers or MockPeerModules()

    app = FastAPI()

    # Pre-set app.state for dependencies that read from it.
    app.state.userdb = _db
    app.state.core_client = _catalogue
    app.state.dev_mode = dev_mode
    app.state.config = {"port": 3000, "shell_version": "0.1.0", "core_url": "http://localhost:8420"}
    app.state.start_time = time.monotonic()

    # Wire a minimal module_registry so PeerModules works.
    from backend.app.module_loader import ModuleRegistry
    registry = ModuleRegistry()
    app.state.module_registry = registry

    app.include_router(router)

    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


__all__ = [
    "MockCatalogueClient",
    "MockUserDB",
    "MockShellContext",
    "MockPeerModules",
    "create_test_app",
]
