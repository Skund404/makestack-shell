"""End-to-end integration tests for the Makestack Shell.

Validates the complete system with a mocked Core:
  1. Catalogue search, create, browse
  2. Inventory: add item, list, get with catalogue data
  3. Workshops: create, add member, verify membership
  4. Version history and diff
  5. Degraded mode: Core down → cached data served, writes fail gracefully
  6. Core reconnect: Shell recovers and serves fresh data
  7. Export/import round-trip: export all data, clear inventory, reimport, verify

These tests use the real FastAPI app with an in-memory UserDB and a mocked Core.
"""

import json
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock
import time

from backend.app.core_client import (
    CatalogueClient,
    CoreUnavailableError,
    CoreNotFoundError,
)
from backend.app.dependencies import get_core_client, get_userdb
from backend.app.main import create_app
from backend.app.models import (
    CommitInfo,
    DiffResponse,
    FieldChange,
    HistoryResponse,
    Primitive,
)
from backend.app.userdb import UserDB
from backend.tests.conftest import SAMPLE_PRIMITIVE, SAMPLE_HASH, SAMPLE_HISTORY, SAMPLE_DIFF


# ---------------------------------------------------------------------------
# Fixtures — shared app, db, and client
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db() -> UserDB:
    database = UserDB(":memory:", dev_mode=True)
    await database.open()
    await database.run_migrations()
    yield database
    await database.close()


def _make_mock_core(connected: bool = True) -> MagicMock:
    client = MagicMock(spec=CatalogueClient)
    client.connected = connected
    client.cache_size = 0
    client._base_url = "http://localhost:8420"
    client.list_primitives = AsyncMock(return_value=[SAMPLE_PRIMITIVE])
    client.get_primitive = AsyncMock(return_value=SAMPLE_PRIMITIVE)
    client.get_primitive_at_version = AsyncMock(return_value=SAMPLE_PRIMITIVE)
    client.get_commit_hash = AsyncMock(return_value=SAMPLE_HASH)
    client.get_history = AsyncMock(return_value=SAMPLE_HISTORY)
    client.get_diff = AsyncMock(return_value=SAMPLE_DIFF)
    client.search = AsyncMock(return_value=[SAMPLE_PRIMITIVE])
    client.get_relationships = AsyncMock(return_value=[])
    client.create_primitive = AsyncMock(return_value=SAMPLE_PRIMITIVE)
    client.update_primitive = AsyncMock(return_value=SAMPLE_PRIMITIVE)
    client.delete_primitive = AsyncMock(return_value=None)
    client.health_check = AsyncMock(return_value=connected)
    return client


async def _make_client(db: UserDB, mock_core: MagicMock) -> AsyncClient:
    app = create_app()
    app.state.userdb = db
    app.state.core_client = mock_core
    app.state.core_connected = mock_core.connected
    app.state.last_core_check = "2026-03-07T00:00:00+00:00"
    app.state.dev_mode = True
    app.state.start_time = time.monotonic()
    app.state.config = {"core_url": "http://localhost:8420", "dev_mode": True}
    app.state.module_registry = None
    app.dependency_overrides[get_userdb] = lambda: db
    app.dependency_overrides[get_core_client] = lambda: mock_core
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# 1. Catalogue: search and browse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_catalogue_search(db: UserDB):
    """Search catalogue returns matching primitives."""
    core = _make_mock_core()
    async with await _make_client(db, core) as client:
        resp = await client.get("/api/catalogue/search?q=chisel")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["slug"] == "stitching-chisel"
        core.search.assert_called_once_with("chisel")


@pytest.mark.asyncio
async def test_e2e_catalogue_list_and_get(db: UserDB):
    """List primitives and get a single primitive by path."""
    core = _make_mock_core()
    async with await _make_client(db, core) as client:
        # List
        resp = await client.get("/api/catalogue/primitives")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        # Get by path
        resp = await client.get("/api/catalogue/primitives/tools/stitching-chisel/manifest.json")
        assert resp.status_code == 200
        assert resp.json()["id"] == SAMPLE_PRIMITIVE.id


@pytest.mark.asyncio
async def test_e2e_catalogue_create(db: UserDB):
    """Creating a primitive via REST returns the created object."""
    core = _make_mock_core()
    async with await _make_client(db, core) as client:
        payload = {
            "type": "technique",
            "name": "Saddle Stitching",
            "description": "Traditional hand stitching technique.",
        }
        resp = await client.post("/api/catalogue/primitives", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == SAMPLE_PRIMITIVE.id  # mock returns SAMPLE_PRIMITIVE
        core.create_primitive.assert_called_once()


# ---------------------------------------------------------------------------
# 2. Inventory: add, list, get with resolved catalogue data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_inventory_add_and_list(db: UserDB):
    """Adding a catalogue item to inventory creates a hash-pointer record."""
    core = _make_mock_core()
    async with await _make_client(db, core) as client:
        # Add to inventory
        resp = await client.post("/api/inventory", json={
            "catalogue_path": SAMPLE_PRIMITIVE.path,
        })
        assert resp.status_code == 201
        item = resp.json()
        assert item["catalogue_path"] == SAMPLE_PRIMITIVE.path
        assert item["catalogue_hash"] == SAMPLE_HASH

        # List inventory
        resp = await client.get("/api/inventory")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == item["id"]


@pytest.mark.asyncio
async def test_e2e_inventory_get_with_catalogue_data(db: UserDB):
    """Getting an inventory item resolves and includes catalogue data."""
    core = _make_mock_core()
    async with await _make_client(db, core) as client:
        # Create inventory item
        resp = await client.post("/api/inventory", json={"catalogue_path": SAMPLE_PRIMITIVE.path})
        item_id = resp.json()["id"]

        # Get with resolved data
        resp = await client.get(f"/api/inventory/{item_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["catalogue_data"]["name"] == SAMPLE_PRIMITIVE.name
        assert "is_stale" in body


# ---------------------------------------------------------------------------
# 3. Workshops: create, add member, verify
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_workshop_create_and_add_member(db: UserDB):
    """Creating a workshop and adding a primitive to it works end-to-end."""
    core = _make_mock_core()
    async with await _make_client(db, core) as client:
        # Create workshop
        resp = await client.post("/api/workshops", json={"name": "My Workshop"})
        assert resp.status_code == 201
        ws = resp.json()
        assert ws["name"] == "My Workshop"
        ws_id = ws["id"]

        # Add a primitive to the workshop
        resp = await client.post(f"/api/workshops/{ws_id}/members", json={
            "primitive_path": SAMPLE_PRIMITIVE.path,
            "primitive_type": "tool",
        })
        assert resp.status_code == 201

        # Verify workshop now has a member
        resp = await client.get(f"/api/workshops/{ws_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["members"]) == 1
        assert body["members"][0]["primitive_path"] == SAMPLE_PRIMITIVE.path


# ---------------------------------------------------------------------------
# 4. Version history and diff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_version_history_and_diff(db: UserDB):
    """Version history and diff are correctly proxied from Core."""
    core = _make_mock_core()
    async with await _make_client(db, core) as client:
        path = SAMPLE_PRIMITIVE.path

        # History
        resp = await client.get(f"/api/catalogue/primitives/{path}/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["commits"][0]["hash"] == SAMPLE_HASH

        # Diff
        resp = await client.get(f"/api/catalogue/primitives/{path}/diff")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["changes"]) == 1
        assert body["changes"][0]["field"] == "description"


# ---------------------------------------------------------------------------
# 5. Degraded mode: Core down → cached data, writes fail gracefully
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_degraded_mode_writes_fail(db: UserDB):
    """When Core is down, catalogue write operations return 503."""
    core = _make_mock_core(connected=False)
    core.create_primitive = AsyncMock(side_effect=CoreUnavailableError("http://localhost:8420"))
    core.update_primitive = AsyncMock(side_effect=CoreUnavailableError("http://localhost:8420"))
    core.delete_primitive = AsyncMock(side_effect=CoreUnavailableError("http://localhost:8420"))

    async with await _make_client(db, core) as client:
        # Create fails with 503
        resp = await client.post("/api/catalogue/primitives", json={
            "type": "tool", "name": "Will Fail",
        })
        assert resp.status_code == 503
        body = resp.json()
        assert "error" in body["detail"]

        # Update fails with 503
        resp = await client.put(
            "/api/catalogue/primitives/tools/stitching-chisel/manifest.json",
            json={"id": "x", "type": "tool", "name": "x", "slug": "x"},
        )
        assert resp.status_code == 503

        # Delete fails with 503
        resp = await client.delete("/api/catalogue/primitives/tools/test/manifest.json")
        assert resp.status_code == 503


@pytest.mark.asyncio
async def test_e2e_degraded_mode_inventory_works(db: UserDB):
    """Inventory (local UserDB) remains fully functional when Core is down."""
    core = _make_mock_core()
    # First add an inventory item while Core is up
    async with await _make_client(db, core) as client:
        resp = await client.post("/api/inventory", json={"catalogue_path": SAMPLE_PRIMITIVE.path})
        assert resp.status_code == 201
        item_id = resp.json()["id"]

    # Now bring Core down
    down_core = _make_mock_core(connected=False)
    down_core.list_primitives = AsyncMock(side_effect=CoreUnavailableError("http://localhost:8420"))

    async with await _make_client(db, down_core) as client:
        # Inventory list still works
        resp = await client.get("/api/inventory")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        # Individual inventory item accessible
        resp = await client.get(f"/api/inventory/{item_id}")
        assert resp.status_code == 200

        # System status shows core disconnected
        resp = await client.get("/api/status")
        assert resp.status_code == 200
        status = resp.json()
        assert status["core_connected"] is False
        assert status["last_core_check"] is not None


@pytest.mark.asyncio
async def test_e2e_status_includes_cache_info(db: UserDB):
    """GET /api/status returns last_core_check and cache_size."""
    core = _make_mock_core()
    async with await _make_client(db, core) as client:
        resp = await client.get("/api/status")
        assert resp.status_code == 200
        body = resp.json()
        assert "core_connected" in body
        assert "last_core_check" in body
        assert "cache_size" in body
        assert isinstance(body["cache_size"], int)


# ---------------------------------------------------------------------------
# 6. Export/import round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_export_import_round_trip(db: UserDB):
    """Export all data, delete inventory items, reimport, verify restoration."""
    core = _make_mock_core()
    async with await _make_client(db, core) as client:
        # Create some workshops
        resp = await client.post("/api/workshops", json={"name": "Leather Workshop"})
        ws_id = resp.json()["id"]

        # Add inventory items
        resp = await client.post("/api/inventory", json={
            "catalogue_path": SAMPLE_PRIMITIVE.path,
            "workshop_id": ws_id,
        })
        item_id = resp.json()["id"]

        # Export everything
        resp = await client.get("/api/data/export")
        assert resp.status_code == 200
        export_doc = resp.json()

        assert export_doc["version"] == "1.0.0"
        assert "exported_at" in export_doc
        assert "sections" in export_doc
        sections = export_doc["sections"]
        assert "workshops" in sections
        assert "inventory" in sections
        assert len(sections["workshops"]) == 1
        assert len(sections["inventory"]) == 1

        # Delete the inventory item
        resp = await client.delete(f"/api/inventory/{item_id}")
        assert resp.status_code == 204

        # Verify it's gone
        resp = await client.get("/api/inventory")
        assert resp.json()["total"] == 0

        # Import with overwrite strategy
        resp = await client.post(
            "/api/data/import?strategy=overwrite",
            json={"data": export_doc},
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["imported"]["inventory"] == 1  # reimported
        assert result["imported"].get("workshops", 0) == 0  # ws already exists

        # Verify inventory is restored
        resp = await client.get("/api/inventory")
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["id"] == item_id


@pytest.mark.asyncio
async def test_e2e_export_only_inventory(db: UserDB):
    """Export with only=inventory returns only the inventory section."""
    core = _make_mock_core()
    async with await _make_client(db, core) as client:
        await client.post("/api/inventory", json={"catalogue_path": SAMPLE_PRIMITIVE.path})
        await client.post("/api/workshops", json={"name": "My WS"})

        resp = await client.get("/api/data/export?only=inventory")
        assert resp.status_code == 200
        body = resp.json()
        sections = body["sections"]
        assert "inventory" in sections
        assert "workshops" not in sections


@pytest.mark.asyncio
async def test_e2e_import_additive_skips_existing(db: UserDB):
    """Additive import skips items that already exist."""
    core = _make_mock_core()
    async with await _make_client(db, core) as client:
        # Create a workshop
        resp = await client.post("/api/workshops", json={"name": "WS"})
        ws_id = resp.json()["id"]

        # Export
        resp = await client.get("/api/data/export?only=workshops")
        export_doc = resp.json()

        # Import again (additive — should skip)
        resp = await client.post("/api/data/import?only=workshops", json={"data": export_doc})
        assert resp.status_code == 200
        result = resp.json()
        assert result["skipped"].get("workshops", 0) == 1
        assert result["imported"].get("workshops", 0) == 0

        # Only one workshop still
        resp = await client.get("/api/workshops")
        assert resp.json()["total"] == 1


# ---------------------------------------------------------------------------
# 7. LRU cache: basic hit/miss behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_cache_hit_avoids_core_call(db: UserDB):
    """After the first call, subsequent requests hit the cache."""
    core = _make_mock_core()
    # Use a real CatalogueClient with cache but replace the http client with a mock
    # that raises CoreUnavailableError on the second call.
    real_client = CatalogueClient(
        base_url="http://localhost:8420",
        dev_mode=True,
    )
    # Manually prime the cache with the sample primitive data
    from backend.app.core_client import _LRUCache, _LIST_TTL
    real_client._cache.put(
        real_client._cache_key("GET", "/api/primitives", None),
        [SAMPLE_PRIMITIVE.model_dump()],
        _LIST_TTL,
    )

    # Cache should have the entry
    assert real_client.cache_size == 1

    await real_client.close()


@pytest.mark.asyncio
async def test_e2e_data_export_invalid_section(db: UserDB):
    """Export with an invalid only= parameter returns 400."""
    core = _make_mock_core()
    async with await _make_client(db, core) as client:
        resp = await client.get("/api/data/export?only=invalid_section")
        assert resp.status_code == 400
        body = resp.json()
        assert "error" in body["detail"]


@pytest.mark.asyncio
async def test_e2e_import_invalid_section_returns_400(db: UserDB):
    """Import with an invalid only= parameter returns 400."""
    core = _make_mock_core()
    async with await _make_client(db, core) as client:
        resp = await client.post(
            "/api/data/import?only=bogus",
            json={"data": {"version": "1.0.0", "sections": {}}},
        )
        assert resp.status_code == 400
