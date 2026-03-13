"""Shared pytest fixtures for the Makestack Shell test suite."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.core_client import CatalogueClient
from backend.app.dependencies import get_core_client, get_userdb
from backend.app.main import create_app
from backend.app.models import (
    CommitInfo,
    DiffResponse,
    FieldChange,
    HistoryResponse,
    Primitive,
    Relationship,
)
from backend.app.userdb import UserDB


# ---------------------------------------------------------------------------
# In-memory UserDB fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[UserDB, None]:
    """Provide a fresh in-memory UserDB with all migrations applied."""
    database = UserDB(":memory:", dev_mode=True)
    await database.open()
    await database.run_migrations()
    yield database
    await database.close()


# ---------------------------------------------------------------------------
# Fixture primitive data
# ---------------------------------------------------------------------------

SAMPLE_PRIMITIVE = Primitive(
    id="tool-stitching-chisel-001",
    type="tool",
    name="Stitching Chisel (4-prong)",
    slug="stitching-chisel",
    path="tools/stitching-chisel/manifest.json",
    created="2026-01-01T00:00:00Z",
    modified="2026-01-15T00:00:00Z",
    description="A 4-prong stitching chisel for leatherwork.",
    tags=["leather", "stitching"],
    properties={"prongs": 4, "spacing_mm": 4},
    manifest={"id": "tool-stitching-chisel-001", "type": "tool", "name": "Stitching Chisel (4-prong)"},
)

SAMPLE_HASH = "abc123def456"

SAMPLE_HISTORY = HistoryResponse(
    path="tools/stitching-chisel/manifest.json",
    total=2,
    commits=[
        CommitInfo(hash="abc123def456", message="Update description", author="Maker", timestamp="2026-01-15T00:00:00Z"),
        CommitInfo(hash="111aaa222bbb", message="Initial commit", author="Maker", timestamp="2026-01-01T00:00:00Z"),
    ],
)

SAMPLE_DIFF = DiffResponse(
    path="tools/stitching-chisel/manifest.json",
    from_hash="111aaa222bbb",
    to_hash="abc123def456",
    from_timestamp="2026-01-01T00:00:00Z",
    to_timestamp="2026-01-15T00:00:00Z",
    changes=[
        FieldChange(field="description", type="modified", old_value="A chisel.", new_value="A 4-prong stitching chisel for leatherwork."),
    ],
)

SAMPLE_RELATIONSHIP = Relationship(
    source_path="techniques/saddle-stitching/manifest.json",
    source_type="technique",
    relationship_type="uses_tool",
    target_path="tools/stitching-chisel/manifest.json",
    target_type="tool",
)


# ---------------------------------------------------------------------------
# Mock CatalogueClient
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_core() -> MagicMock:
    """Return a fully mocked CatalogueClient with sensible default returns."""
    client = MagicMock(spec=CatalogueClient)
    client.connected = True
    client.cache_size = 0
    client._base_url = "http://localhost:8420"

    # Wire up async methods with AsyncMock.
    client.list_primitives = AsyncMock(return_value=[SAMPLE_PRIMITIVE])
    client.get_primitive = AsyncMock(return_value=SAMPLE_PRIMITIVE)
    client.get_primitive_at_version = AsyncMock(return_value=SAMPLE_PRIMITIVE)
    client.get_commit_hash = AsyncMock(return_value=SAMPLE_HASH)
    client.get_history = AsyncMock(return_value=SAMPLE_HISTORY)
    client.get_diff = AsyncMock(return_value=SAMPLE_DIFF)
    client.search = AsyncMock(return_value=[SAMPLE_PRIMITIVE])
    client.get_relationships = AsyncMock(return_value=[SAMPLE_RELATIONSHIP])
    client.create_primitive = AsyncMock(return_value=SAMPLE_PRIMITIVE)
    client.update_primitive = AsyncMock(return_value=SAMPLE_PRIMITIVE)
    client.delete_primitive = AsyncMock(return_value=None)
    client.health_check = AsyncMock(return_value=True)

    return client


# ---------------------------------------------------------------------------
# FastAPI test application with dependency overrides
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_app(db: UserDB, mock_core: MagicMock) -> FastAPI:
    """Create a FastAPI test app with mocked Core and real in-memory UserDB."""
    application = create_app()

    # Override lifespan-set state before the test client starts.
    application.state.userdb = db
    application.state.core_client = mock_core
    application.state.core_connected = True
    application.state.last_core_check = "2026-03-07T00:00:00+00:00"
    application.state.dev_mode = True
    application.state.config = {"core_url": "http://localhost:8420"}

    import time
    application.state.start_time = time.monotonic()

    # Module registry — empty by default. Tests that need specific behavior can
    # override attributes: test_app.state.module_registry.is_loaded = lambda n: n == "..."
    from unittest.mock import MagicMock as _MagicMock
    _registry = _MagicMock()
    _registry.is_loaded = _MagicMock(return_value=False)
    _registry.get_module = _MagicMock(return_value=None)
    _registry.get_module_views = _MagicMock(return_value=[])
    _registry.get_module_panels = _MagicMock(return_value=[])
    application.state.module_registry = _registry

    # Override FastAPI dependencies.
    application.dependency_overrides[get_userdb] = lambda: db
    application.dependency_overrides[get_core_client] = lambda: mock_core

    return application


@pytest_asyncio.fixture
async def client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx AsyncClient connected to the test app via ASGI transport.

    The lifespan is disabled — dependencies are injected directly via overrides.
    """
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
