"""Tests for inventory routes — full flow with a real in-memory UserDB and mock Core."""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

from backend.app.core_client import CoreNotFoundError, CoreUnavailableError
from backend.tests.conftest import SAMPLE_PRIMITIVE, SAMPLE_HASH


# ---------------------------------------------------------------------------
# POST /api/inventory — add to inventory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_to_inventory_creates_record(client: AsyncClient, mock_core):
    resp = await client.post(
        "/api/inventory",
        json={"catalogue_path": "tools/stitching-chisel/manifest.json"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["catalogue_path"] == "tools/stitching-chisel/manifest.json"
    assert body["catalogue_hash"] == SAMPLE_HASH
    assert body["primitive_type"] == SAMPLE_PRIMITIVE.type
    assert "id" in body


@pytest.mark.asyncio
async def test_add_to_inventory_with_workshop(client: AsyncClient, mock_core, db):
    # Create a workshop first.
    import uuid
    ws_id = str(uuid.uuid4())
    await db.execute(
        "INSERT INTO workshops (id, name, slug, created_at, updated_at) VALUES (?, ?, ?, datetime('now'), datetime('now'))",
        [ws_id, "Test WS", "test-ws"],
    )

    resp = await client.post(
        "/api/inventory",
        json={"catalogue_path": "tools/stitching-chisel/manifest.json", "workshop_id": ws_id},
    )
    assert resp.status_code == 201
    assert resp.json()["workshop_id"] == ws_id


@pytest.mark.asyncio
async def test_add_to_inventory_404_when_catalogue_missing(client: AsyncClient, mock_core):
    mock_core.get_primitive = AsyncMock(side_effect=CoreNotFoundError("tools/nonexistent/manifest.json"))
    resp = await client.post(
        "/api/inventory",
        json={"catalogue_path": "tools/nonexistent/manifest.json"},
    )
    assert resp.status_code == 404
    assert "suggestion" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_add_to_inventory_503_when_core_down(client: AsyncClient, mock_core):
    mock_core.get_primitive = AsyncMock(side_effect=CoreUnavailableError("http://localhost:8420"))
    resp = await client.post(
        "/api/inventory",
        json={"catalogue_path": "tools/stitching-chisel/manifest.json"},
    )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_add_to_inventory_404_nonexistent_workshop(client: AsyncClient, mock_core):
    resp = await client.post(
        "/api/inventory",
        json={
            "catalogue_path": "tools/stitching-chisel/manifest.json",
            "workshop_id": "nonexistent-workshop",
        },
    )
    assert resp.status_code == 404
    assert "Workshop not found" in resp.json()["detail"]["error"]


# ---------------------------------------------------------------------------
# GET /api/inventory — list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_inventory_empty(client: AsyncClient):
    resp = await client.get("/api/inventory")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_list_inventory_returns_items(client: AsyncClient, mock_core):
    await client.post(
        "/api/inventory",
        json={"catalogue_path": "tools/stitching-chisel/manifest.json"},
    )
    resp = await client.get("/api/inventory")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["catalogue_path"] == "tools/stitching-chisel/manifest.json"


@pytest.mark.asyncio
async def test_list_inventory_filter_by_type(client: AsyncClient, mock_core):
    await client.post("/api/inventory", json={"catalogue_path": "tools/stitching-chisel/manifest.json"})
    resp = await client.get("/api/inventory?type=tool")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    resp2 = await client.get("/api/inventory?type=material")
    assert resp2.json()["total"] == 0


# ---------------------------------------------------------------------------
# GET /api/inventory/{id} — single item with catalogue data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_inventory_item_with_catalogue_data(client: AsyncClient, mock_core):
    add_resp = await client.post(
        "/api/inventory",
        json={"catalogue_path": "tools/stitching-chisel/manifest.json"},
    )
    item_id = add_resp.json()["id"]

    resp = await client.get(f"/api/inventory/{item_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == item_id
    assert body["catalogue_data"] is not None
    assert body["is_stale"] is False  # same hash returned by mock


@pytest.mark.asyncio
async def test_get_inventory_item_marks_stale_when_hash_differs(client: AsyncClient, mock_core):
    add_resp = await client.post(
        "/api/inventory",
        json={"catalogue_path": "tools/stitching-chisel/manifest.json"},
    )
    item_id = add_resp.json()["id"]

    # Now return a different hash for the current version.
    mock_core.get_commit_hash = AsyncMock(return_value="new_hash_different")

    resp = await client.get(f"/api/inventory/{item_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_stale"] is True
    assert body["current_hash"] == "new_hash_different"


@pytest.mark.asyncio
async def test_get_inventory_item_404(client: AsyncClient):
    resp = await client.get("/api/inventory/nonexistent-id")
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert "suggestion" in detail


# ---------------------------------------------------------------------------
# PUT /api/inventory/{id} — update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_inventory_workshop(client: AsyncClient, mock_core, db):
    import uuid
    ws_id = str(uuid.uuid4())
    await db.execute(
        "INSERT INTO workshops (id, name, slug, created_at, updated_at) VALUES (?, ?, ?, datetime('now'), datetime('now'))",
        [ws_id, "New WS", "new-ws"],
    )

    add_resp = await client.post(
        "/api/inventory",
        json={"catalogue_path": "tools/stitching-chisel/manifest.json"},
    )
    item_id = add_resp.json()["id"]

    resp = await client.put(f"/api/inventory/{item_id}", json={"workshop_id": ws_id})
    assert resp.status_code == 200
    assert resp.json()["workshop_id"] == ws_id


@pytest.mark.asyncio
async def test_update_inventory_hash_pointer(client: AsyncClient, mock_core):
    add_resp = await client.post(
        "/api/inventory",
        json={"catalogue_path": "tools/stitching-chisel/manifest.json"},
    )
    item_id = add_resp.json()["id"]
    new_hash = "new_validated_hash"
    mock_core.get_primitive_at_version = AsyncMock(return_value=SAMPLE_PRIMITIVE)

    resp = await client.put(f"/api/inventory/{item_id}", json={"catalogue_hash": new_hash})
    assert resp.status_code == 200
    assert resp.json()["catalogue_hash"] == new_hash


@pytest.mark.asyncio
async def test_update_inventory_404(client: AsyncClient):
    resp = await client.put("/api/inventory/nonexistent-id", json={"workshop_id": None})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/inventory/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_inventory_item(client: AsyncClient, mock_core):
    add_resp = await client.post(
        "/api/inventory",
        json={"catalogue_path": "tools/stitching-chisel/manifest.json"},
    )
    item_id = add_resp.json()["id"]

    del_resp = await client.delete(f"/api/inventory/{item_id}")
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/inventory/{item_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_inventory_item_404(client: AsyncClient):
    resp = await client.delete("/api/inventory/nonexistent-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/inventory/stale
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stale_endpoint_returns_empty_when_all_current(client: AsyncClient, mock_core):
    await client.post("/api/inventory", json={"catalogue_path": "tools/stitching-chisel/manifest.json"})
    # Mock returns same hash → not stale.
    resp = await client.get("/api/inventory/stale")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_stale_endpoint_detects_stale_items(client: AsyncClient, mock_core):
    await client.post("/api/inventory", json={"catalogue_path": "tools/stitching-chisel/manifest.json"})
    mock_core.get_commit_hash = AsyncMock(return_value="completely_different_hash")

    resp = await client.get("/api/inventory/stale")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["is_stale"] is True
