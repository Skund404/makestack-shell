"""Tests for version history and diff proxy routes."""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

from backend.app.core_client import CoreNotFoundError, CoreUnavailableError
from backend.tests.conftest import SAMPLE_DIFF, SAMPLE_HISTORY


# ---------------------------------------------------------------------------
# GET /api/version/{path}/history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_history_returns_commits(client: AsyncClient, mock_core):
    resp = await client.get("/api/version/tools/stitching-chisel/manifest.json/history")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == SAMPLE_HISTORY.total
    assert len(body["commits"]) == len(SAMPLE_HISTORY.commits)
    assert body["commits"][0]["hash"] == SAMPLE_HISTORY.commits[0].hash


@pytest.mark.asyncio
async def test_history_passes_limit_and_offset(client: AsyncClient, mock_core):
    await client.get("/api/version/tools/stitching-chisel/manifest.json/history?limit=10&offset=5")
    mock_core.get_history.assert_called_once_with(
        "tools/stitching-chisel/manifest.json",
        limit=10,
        offset=5,
    )


@pytest.mark.asyncio
async def test_history_503_when_core_unavailable(client: AsyncClient, mock_core):
    mock_core.get_history = AsyncMock(side_effect=CoreUnavailableError("http://localhost:8420"))
    resp = await client.get("/api/version/tools/stitching-chisel/manifest.json/history")
    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert "suggestion" in detail


@pytest.mark.asyncio
async def test_history_404_for_unknown_primitive(client: AsyncClient, mock_core):
    mock_core.get_history = AsyncMock(
        side_effect=CoreNotFoundError("tools/nonexistent/manifest.json")
    )
    resp = await client.get("/api/version/tools/nonexistent/manifest.json/history")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/version/{path}/diff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_diff_returns_changes(client: AsyncClient, mock_core):
    resp = await client.get("/api/version/tools/stitching-chisel/manifest.json/diff")
    assert resp.status_code == 200
    body = resp.json()
    assert "changes" in body
    assert body["from_hash"] == SAMPLE_DIFF.from_hash
    assert body["to_hash"] == SAMPLE_DIFF.to_hash


@pytest.mark.asyncio
async def test_diff_passes_hash_params(client: AsyncClient, mock_core):
    await client.get(
        "/api/version/tools/stitching-chisel/manifest.json/diff",
        params={"from": "aaa", "to": "bbb"},
    )
    mock_core.get_diff.assert_called_once_with(
        "tools/stitching-chisel/manifest.json",
        from_hash="aaa",
        to_hash="bbb",
    )


@pytest.mark.asyncio
async def test_diff_503_when_core_unavailable(client: AsyncClient, mock_core):
    mock_core.get_diff = AsyncMock(side_effect=CoreUnavailableError("http://localhost:8420"))
    resp = await client.get("/api/version/tools/stitching-chisel/manifest.json/diff")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_diff_404_for_unknown_primitive(client: AsyncClient, mock_core):
    mock_core.get_diff = AsyncMock(
        side_effect=CoreNotFoundError("tools/nonexistent/manifest.json")
    )
    resp = await client.get("/api/version/tools/nonexistent/manifest.json/diff")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Confirm catalogue router history/diff also work (via catalogue.py routes)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_catalogue_history_route(client: AsyncClient, mock_core):
    """The catalogue router also exposes history — verify it works identically."""
    resp = await client.get(
        "/api/catalogue/primitives/tools/stitching-chisel/manifest.json/history"
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == SAMPLE_HISTORY.total


@pytest.mark.asyncio
async def test_catalogue_diff_route(client: AsyncClient, mock_core):
    """The catalogue router also exposes diff — verify it works identically."""
    resp = await client.get(
        "/api/catalogue/primitives/tools/stitching-chisel/manifest.json/diff"
    )
    assert resp.status_code == 200
    assert "changes" in resp.json()
