"""Tests for catalogue proxy routes.

Verifies correct response shapes, pagination behaviour, 503 when Core is
unavailable, and 404 pass-through.
"""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

from backend.app.core_client import CoreNotFoundError, CoreUnavailableError
from backend.tests.conftest import SAMPLE_PRIMITIVE, SAMPLE_HASH, SAMPLE_HISTORY, SAMPLE_DIFF, SAMPLE_RELATIONSHIP


# ---------------------------------------------------------------------------
# GET /api/catalogue/primitives
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_primitives_returns_paginated(client: AsyncClient, mock_core):
    resp = await client.get("/api/catalogue/primitives")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert body["total"] == 1
    assert body["items"][0]["id"] == SAMPLE_PRIMITIVE.id


@pytest.mark.asyncio
async def test_list_primitives_passes_type_filter(client: AsyncClient, mock_core):
    resp = await client.get("/api/catalogue/primitives?type=tool")
    assert resp.status_code == 200
    mock_core.list_primitives.assert_called_once_with(type_filter="tool")


@pytest.mark.asyncio
async def test_list_primitives_503_when_core_unavailable(client: AsyncClient, mock_core):
    mock_core.list_primitives = AsyncMock(side_effect=CoreUnavailableError("http://localhost:8420"))
    resp = await client.get("/api/catalogue/primitives")
    assert resp.status_code == 503
    body = resp.json()
    assert "error" in body["detail"]
    assert "suggestion" in body["detail"]


# ---------------------------------------------------------------------------
# GET /api/catalogue/search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_returns_results(client: AsyncClient, mock_core):
    resp = await client.get("/api/catalogue/search?q=chisel")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    mock_core.search.assert_called_once_with("chisel")


@pytest.mark.asyncio
async def test_search_requires_q_param(client: AsyncClient):
    resp = await client.get("/api/catalogue/search")
    assert resp.status_code == 422  # FastAPI validation error


# ---------------------------------------------------------------------------
# GET /api/catalogue/primitives/{path}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_primitive(client: AsyncClient, mock_core):
    resp = await client.get("/api/catalogue/primitives/tools/stitching-chisel/manifest.json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == SAMPLE_PRIMITIVE.slug


@pytest.mark.asyncio
async def test_get_primitive_at_version(client: AsyncClient, mock_core):
    resp = await client.get(
        "/api/catalogue/primitives/tools/stitching-chisel/manifest.json",
        params={"at": SAMPLE_HASH},
    )
    assert resp.status_code == 200
    mock_core.get_primitive_at_version.assert_called_once()


@pytest.mark.asyncio
async def test_get_primitive_404(client: AsyncClient, mock_core):
    mock_core.get_primitive = AsyncMock(side_effect=CoreNotFoundError("tools/nonexistent/manifest.json"))
    resp = await client.get("/api/catalogue/primitives/tools/nonexistent/manifest.json")
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert detail["error"] == "Primitive not found"
    assert "suggestion" in detail


# ---------------------------------------------------------------------------
# GET /api/catalogue/primitives/{path}/hash
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_primitive_hash(client: AsyncClient, mock_core):
    resp = await client.get("/api/catalogue/primitives/tools/stitching-chisel/manifest.json/hash")
    assert resp.status_code == 200
    body = resp.json()
    assert body["hash"] == SAMPLE_HASH


# ---------------------------------------------------------------------------
# GET /api/catalogue/primitives/{path}/history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_history(client: AsyncClient, mock_core):
    resp = await client.get("/api/catalogue/primitives/tools/stitching-chisel/manifest.json/history")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["commits"]) == 2


# ---------------------------------------------------------------------------
# GET /api/catalogue/primitives/{path}/diff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_diff(client: AsyncClient, mock_core):
    resp = await client.get("/api/catalogue/primitives/tools/stitching-chisel/manifest.json/diff")
    assert resp.status_code == 200
    body = resp.json()
    assert "changes" in body
    assert body["changes"][0]["field"] == "description"


# ---------------------------------------------------------------------------
# GET /api/catalogue/relationships/{path}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_relationships(client: AsyncClient, mock_core):
    resp = await client.get("/api/catalogue/relationships/tools/stitching-chisel/manifest.json")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert body[0]["relationship_type"] == SAMPLE_RELATIONSHIP.relationship_type


# ---------------------------------------------------------------------------
# POST /api/catalogue/primitives
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_primitive(client: AsyncClient, mock_core):
    resp = await client.post(
        "/api/catalogue/primitives",
        json={"type": "tool", "name": "New Tool"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["type"] == SAMPLE_PRIMITIVE.type


# ---------------------------------------------------------------------------
# PUT /api/catalogue/primitives/{path}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_primitive(client: AsyncClient, mock_core):
    resp = await client.put(
        "/api/catalogue/primitives/tools/stitching-chisel/manifest.json",
        json={
            "id": SAMPLE_PRIMITIVE.id,
            "type": SAMPLE_PRIMITIVE.type,
            "name": SAMPLE_PRIMITIVE.name,
            "slug": SAMPLE_PRIMITIVE.slug,
        },
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# DELETE /api/catalogue/primitives/{path}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_primitive(client: AsyncClient, mock_core):
    resp = await client.delete("/api/catalogue/primitives/tools/stitching-chisel/manifest.json")
    assert resp.status_code == 204
