"""Tests for CatalogueClient — verifies all Core API methods parse responses correctly
and handle error conditions (404, 503, connection refused) with typed exceptions.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.app.core_client import (
    CatalogueClient,
    CoreNotFoundError,
    CoreUnavailableError,
    CoreValidationError,
)
from backend.app.models import PrimitiveCreate, PrimitiveUpdate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PRIMITIVE_PAYLOAD = {
    "id": "tool-chisel-001",
    "type": "tool",
    "name": "Chisel",
    "slug": "chisel",
    "path": "tools/chisel/manifest.json",
    "created": "2026-01-01T00:00:00Z",
    "modified": "2026-01-01T00:00:00Z",
    "description": "A chisel",
    "tags": ["leather"],
    "properties": {"width_mm": 10},
    "parent_project": "",
    "manifest": {"id": "tool-chisel-001"},
    "commit_hash": "",
}

_HISTORY_PAYLOAD = {
    "path": "tools/chisel/manifest.json",
    "total": 1,
    "commits": [
        {"hash": "abc123", "message": "init", "author": "Maker", "timestamp": "2026-01-01T00:00:00Z"}
    ],
}

_DIFF_PAYLOAD = {
    "path": "tools/chisel/manifest.json",
    "from_hash": "aaa",
    "to_hash": "bbb",
    "from_timestamp": "2026-01-01T00:00:00Z",
    "to_timestamp": "2026-01-02T00:00:00Z",
    "changes": [
        {"field": "description", "type": "modified", "old_value": "A chisel.", "new_value": "A sharper chisel."}
    ],
}


def _make_response(status: int, body: dict | list | None = None) -> httpx.Response:
    """Build a minimal httpx.Response for mocking."""
    content = json.dumps(body or {}).encode()
    return httpx.Response(status, content=content, headers={"content-type": "application/json"})


def _make_client(response_map: dict) -> CatalogueClient:
    """Build a CatalogueClient backed by a mock httpx transport.

    response_map: {(method, path_fragment): httpx.Response}
    """
    async def handler(request: httpx.Request) -> httpx.Response:
        for (method, fragment), resp in response_map.items():
            if request.method == method and fragment in str(request.url):
                return resp
        return _make_response(404, {"error": "not found"})

    transport = httpx.MockTransport(handler)
    inner = httpx.AsyncClient(base_url="http://localhost:8420", transport=transport)
    return CatalogueClient(client=inner)


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_check_success():
    client = _make_client({("GET", "/health"): _make_response(200, {"status": "ok"})})
    assert await client.health_check() is True
    assert client.connected is True


@pytest.mark.asyncio
async def test_health_check_failure_sets_connected_false():
    async def broken_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    inner = httpx.AsyncClient(base_url="http://localhost:8420", transport=httpx.MockTransport(broken_handler))
    client = CatalogueClient(client=inner)
    assert await client.health_check() is False
    assert client.connected is False


# ---------------------------------------------------------------------------
# list_primitives
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_primitives_returns_models():
    client = _make_client({("GET", "/api/primitives"): _make_response(200, [_PRIMITIVE_PAYLOAD])})
    results = await client.list_primitives()
    assert len(results) == 1
    assert results[0].id == "tool-chisel-001"
    assert results[0].type == "tool"


@pytest.mark.asyncio
async def test_list_primitives_with_type_filter():
    client = _make_client({("GET", "/api/primitives"): _make_response(200, [_PRIMITIVE_PAYLOAD])})
    results = await client.list_primitives(type_filter="tool")
    assert results[0].type == "tool"


# ---------------------------------------------------------------------------
# get_primitive
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_primitive_success():
    client = _make_client({
        ("GET", "/api/primitives/tools/chisel/manifest.json"): _make_response(200, _PRIMITIVE_PAYLOAD)
    })
    primitive = await client.get_primitive("tools/chisel/manifest.json")
    assert primitive.slug == "chisel"


@pytest.mark.asyncio
async def test_get_primitive_404_raises_not_found():
    client = _make_client({})  # All requests → 404
    with pytest.raises(CoreNotFoundError):
        await client.get_primitive("tools/nonexistent/manifest.json")


# ---------------------------------------------------------------------------
# get_primitive_at_version
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_primitive_at_version():
    payload = dict(_PRIMITIVE_PAYLOAD, commit_hash="abc123")
    client = _make_client({
        ("GET", "/api/primitives/tools/chisel/manifest.json"): _make_response(200, payload)
    })
    primitive = await client.get_primitive_at_version("tools/chisel/manifest.json", "abc123")
    assert primitive.commit_hash == "abc123"


# ---------------------------------------------------------------------------
# get_commit_hash
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_commit_hash():
    client = _make_client({
        ("GET", "tools/chisel/manifest.json/hash"): _make_response(200, {"hash": "deadbeef"})
    })
    h = await client.get_commit_hash("tools/chisel/manifest.json")
    assert h == "deadbeef"


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_history_parses_response():
    client = _make_client({
        ("GET", "tools/chisel/manifest.json/history"): _make_response(200, _HISTORY_PAYLOAD)
    })
    history = await client.get_history("tools/chisel/manifest.json")
    assert history.total == 1
    assert history.commits[0].hash == "abc123"


# ---------------------------------------------------------------------------
# get_diff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_diff_parses_changes():
    client = _make_client({
        ("GET", "tools/chisel/manifest.json/diff"): _make_response(200, _DIFF_PAYLOAD)
    })
    diff = await client.get_diff("tools/chisel/manifest.json", from_hash="aaa", to_hash="bbb")
    assert len(diff.changes) == 1
    assert diff.changes[0].field == "description"
    assert diff.changes[0].type == "modified"


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_returns_primitives():
    client = _make_client({("GET", "/api/search"): _make_response(200, [_PRIMITIVE_PAYLOAD])})
    results = await client.search("chisel")
    assert len(results) == 1


# ---------------------------------------------------------------------------
# get_relationships
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_relationships():
    rel = {
        "source_path": "techniques/stitching/manifest.json",
        "source_type": "technique",
        "relationship_type": "uses_tool",
        "target_path": "tools/chisel/manifest.json",
        "target_type": "tool",
        "metadata": None,
    }
    client = _make_client({("GET", "relationships"): _make_response(200, [rel])})
    rels = await client.get_relationships("tools/chisel/manifest.json")
    assert rels[0].relationship_type == "uses_tool"


# ---------------------------------------------------------------------------
# create_primitive
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_primitive():
    client = _make_client({("POST", "/api/primitives"): _make_response(201, _PRIMITIVE_PAYLOAD)})
    payload = PrimitiveCreate(type="tool", name="Chisel")
    result = await client.create_primitive(payload)
    assert result.id == "tool-chisel-001"


# ---------------------------------------------------------------------------
# update_primitive
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_primitive():
    client = _make_client({
        ("PUT", "tools/chisel/manifest.json"): _make_response(200, _PRIMITIVE_PAYLOAD)
    })
    payload = PrimitiveUpdate(id="tool-chisel-001", type="tool", name="Chisel", slug="chisel")
    result = await client.update_primitive("tools/chisel/manifest.json", payload)
    assert result.name == "Chisel"


# ---------------------------------------------------------------------------
# delete_primitive
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_primitive():
    client = _make_client({
        ("DELETE", "tools/chisel/manifest.json"): _make_response(204)
    })
    # Should not raise.
    await client.delete_primitive("tools/chisel/manifest.json")


# ---------------------------------------------------------------------------
# Error handling — Core 400 and 5xx
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_400_raises_validation_error():
    client = _make_client({
        ("POST", "/api/primitives"): _make_response(400, {"error": "description must be string"})
    })
    with pytest.raises(CoreValidationError) as exc_info:
        await client.create_primitive(PrimitiveCreate(type="tool", name="X"))
    assert "description" in str(exc_info.value)


@pytest.mark.asyncio
async def test_503_raises_unavailable_error():
    client = _make_client({
        ("GET", "/api/primitives"): _make_response(503, {"error": "service unavailable"})
    })
    with pytest.raises(CoreUnavailableError):
        await client.list_primitives()


@pytest.mark.asyncio
async def test_connect_error_raises_unavailable():
    async def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    inner = httpx.AsyncClient(base_url="http://localhost:8420", transport=httpx.MockTransport(refuse))
    client = CatalogueClient(client=inner)
    with pytest.raises(CoreUnavailableError):
        await client.list_primitives()
