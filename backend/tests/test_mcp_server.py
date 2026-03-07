"""Integration tests for the Makestack MCP server.

These tests create the MCP server with a real in-memory test Shell
(via ASGI transport), then call tools via mcp.call_tool() to verify
the full tool → HTTP → Shell API → response chain.

The test Shell uses the same fixtures as the REST API tests:
  - in-memory UserDB with migrations applied
  - mocked CatalogueClient with sensible default returns
"""

import json
from typing import Any

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from mcp.types import TextContent

from backend.tests.conftest import SAMPLE_HASH, SAMPLE_PRIMITIVE
from mcp_server.server import create_server


# ---------------------------------------------------------------------------
# MCP server fixture backed by the test Shell app
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def mcp_server(test_app):
    """Create an MCP server connected to the in-memory test Shell via ASGI."""
    transport = ASGITransport(app=test_app)
    api_client = httpx.AsyncClient(transport=transport, base_url="http://test")
    server = create_server(api_client=api_client)
    yield server
    await api_client.aclose()


def _text(result: Any) -> str:
    """Extract text from the first content block returned by call_tool.

    mcp 1.26.0 returns a tuple where the first element is a list of ContentBlock,
    so we unwrap one level if needed.
    """
    assert result, "Tool returned empty result"
    first = result[0]
    # Unwrap if call_tool returns (list_of_content,) tuple.
    if isinstance(first, list):
        first = first[0]
    assert isinstance(first, TextContent), f"Expected TextContent, got {type(first)}"
    return first.text


def _json(result: Any) -> Any:
    """Extract and parse JSON from the first content block returned by call_tool."""
    return json.loads(_text(result))


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tools_are_registered(mcp_server):
    """All expected tool names should appear in the tool list."""
    tools = await mcp_server.list_tools()
    names = {t.name for t in tools}

    expected = {
        # Catalogue
        "search_catalogue", "list_primitives", "get_primitive",
        "create_primitive", "update_primitive", "delete_primitive", "get_relationships",
        # Inventory
        "add_to_inventory", "list_inventory", "get_inventory_item",
        "check_inventory_updates", "update_inventory_pointer", "remove_from_inventory",
        # Workshops
        "list_workshops", "get_workshop", "create_workshop", "update_workshop",
        "delete_workshop", "add_to_workshop", "remove_from_workshop", "set_active_workshop",
        # Version
        "get_primitive_history", "compare_versions", "get_primitive_at_version",
        # Settings
        "get_settings", "update_settings", "get_theme", "set_theme",
        # Modules
        "list_modules", "enable_module", "disable_module", "call_module",
        # System
        "get_status", "get_capabilities",
    }
    missing = expected - names
    assert not missing, f"Missing tools: {missing}"


# ---------------------------------------------------------------------------
# Catalogue tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_catalogue(mcp_server):
    """search_catalogue should return a paginated list of primitives."""
    result = await mcp_server.call_tool("search_catalogue", {"query": "stitching"})
    data = _json(result)
    assert "items" in data
    assert data["total"] >= 1
    assert data["items"][0]["name"] == SAMPLE_PRIMITIVE.name


@pytest.mark.asyncio
async def test_search_catalogue_with_type_filter(mcp_server):
    """search_catalogue with type_filter should pass the parameter through."""
    result = await mcp_server.call_tool("search_catalogue", {"query": "tool", "type_filter": "tool"})
    data = _json(result)
    assert "items" in data


@pytest.mark.asyncio
async def test_list_primitives(mcp_server):
    """list_primitives should return a paginated list."""
    result = await mcp_server.call_tool("list_primitives", {})
    data = _json(result)
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_list_primitives_with_type(mcp_server):
    """list_primitives filtered by type should pass the type parameter."""
    result = await mcp_server.call_tool("list_primitives", {"type": "tool"})
    data = _json(result)
    assert "items" in data


@pytest.mark.asyncio
async def test_get_primitive(mcp_server):
    """get_primitive should return the full primitive manifest."""
    result = await mcp_server.call_tool(
        "get_primitive",
        {"path": "tools/stitching-chisel/manifest.json"},
    )
    data = _json(result)
    assert data["name"] == SAMPLE_PRIMITIVE.name
    assert data["type"] == "tool"
    assert data["path"] == SAMPLE_PRIMITIVE.path


@pytest.mark.asyncio
async def test_get_primitive_at_version(mcp_server):
    """get_primitive with version should pass the ?at= param."""
    result = await mcp_server.call_tool(
        "get_primitive",
        {"path": "tools/stitching-chisel/manifest.json", "version": SAMPLE_HASH},
    )
    data = _json(result)
    assert data["name"] == SAMPLE_PRIMITIVE.name


@pytest.mark.asyncio
async def test_create_primitive(mcp_server):
    """create_primitive should POST to /api/catalogue/primitives."""
    result = await mcp_server.call_tool(
        "create_primitive",
        {
            "type": "tool",
            "name": "Wing Divider",
            "description": "A divider for marking parallel lines",
            "tags": ["leather", "marking"],
        },
    )
    data = _json(result)
    assert data["name"] == SAMPLE_PRIMITIVE.name  # mock returns SAMPLE_PRIMITIVE


@pytest.mark.asyncio
async def test_update_primitive(mcp_server):
    """update_primitive should PUT to /api/catalogue/primitives/{path}."""
    result = await mcp_server.call_tool(
        "update_primitive",
        {
            "path": "tools/stitching-chisel/manifest.json",
            "id": SAMPLE_PRIMITIVE.id,
            "type": "tool",
            "name": "Stitching Chisel (6-prong)",
            "slug": "stitching-chisel",
        },
    )
    data = _json(result)
    assert "name" in data


@pytest.mark.asyncio
async def test_delete_primitive(mcp_server):
    """delete_primitive should DELETE and return success."""
    result = await mcp_server.call_tool(
        "delete_primitive",
        {"path": "tools/stitching-chisel/manifest.json"},
    )
    data = _json(result)
    assert data.get("success") is True


@pytest.mark.asyncio
async def test_get_relationships(mcp_server):
    """get_relationships should return the relationship list."""
    result = await mcp_server.call_tool(
        "get_relationships",
        {"path": "techniques/saddle-stitching/manifest.json"},
    )
    data = _json(result)
    assert isinstance(data, list)
    assert data[0]["relationship_type"] == "uses_tool"


# ---------------------------------------------------------------------------
# Inventory tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inventory_round_trip(mcp_server, mock_core):
    """add_to_inventory → list_inventory → get_inventory_item round-trip."""
    # add_to_inventory
    add_result = await mcp_server.call_tool(
        "add_to_inventory",
        {"catalogue_path": "tools/stitching-chisel/manifest.json"},
    )
    added = _json(add_result)
    assert "id" in added
    assert added["catalogue_path"] == "tools/stitching-chisel/manifest.json"
    item_id = added["id"]

    # list_inventory
    list_result = await mcp_server.call_tool("list_inventory", {})
    listed = _json(list_result)
    assert listed["total"] >= 1
    assert any(i["id"] == item_id for i in listed["items"])

    # get_inventory_item
    get_result = await mcp_server.call_tool("get_inventory_item", {"id": item_id})
    got = _json(get_result)
    assert got["id"] == item_id


@pytest.mark.asyncio
async def test_check_inventory_updates(mcp_server):
    """check_inventory_updates should return a paginated list (empty if nothing is stale)."""
    result = await mcp_server.call_tool("check_inventory_updates", {})
    data = _json(result)
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_inventory_item_not_found(mcp_server):
    """get_inventory_item with nonexistent id should return an error with suggestion."""
    result = await mcp_server.call_tool("get_inventory_item", {"id": "nonexistent-id"})
    data = _json(result)
    # FastAPI wraps HTTPException detail in {"detail": {...}}; the nested object has "error".
    assert "detail" in data or "error" in data


# ---------------------------------------------------------------------------
# Workshop tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workshop_round_trip(mcp_server):
    """create_workshop → add_to_workshop → get_workshop → delete_workshop."""
    # create
    create_result = await mcp_server.call_tool(
        "create_workshop",
        {"name": "Leatherwork 2026", "description": "All leatherwork projects"},
    )
    ws = _json(create_result)
    assert ws["name"] == "Leatherwork 2026"
    ws_id = ws["id"]

    # add member
    add_result = await mcp_server.call_tool(
        "add_to_workshop",
        {
            "workshop_id": ws_id,
            "primitive_path": "tools/stitching-chisel/manifest.json",
            "primitive_type": "tool",
        },
    )
    member = _json(add_result)
    assert member["primitive_path"] == "tools/stitching-chisel/manifest.json"

    # get workshop with members
    get_result = await mcp_server.call_tool("get_workshop", {"id": ws_id})
    got = _json(get_result)
    assert got["id"] == ws_id
    assert len(got["members"]) == 1

    # list workshops
    list_result = await mcp_server.call_tool("list_workshops", {})
    listed = _json(list_result)
    assert listed["total"] >= 1

    # remove member
    remove_result = await mcp_server.call_tool(
        "remove_from_workshop",
        {
            "workshop_id": ws_id,
            "primitive_path": "tools/stitching-chisel/manifest.json",
        },
    )
    removed = _json(remove_result)
    assert removed.get("success") is True

    # delete workshop
    del_result = await mcp_server.call_tool("delete_workshop", {"id": ws_id})
    deleted = _json(del_result)
    assert deleted.get("success") is True


@pytest.mark.asyncio
async def test_set_active_workshop(mcp_server):
    """set_active_workshop should update the active context."""
    # Create a workshop first.
    create_result = await mcp_server.call_tool(
        "create_workshop", {"name": "Active Test Workshop"}
    )
    ws = _json(create_result)
    ws_id = ws["id"]

    result = await mcp_server.call_tool("set_active_workshop", {"workshop_id": ws_id})
    data = _json(result)
    assert data.get("active_workshop_id") == ws_id

    # Clear it.
    clear_result = await mcp_server.call_tool("set_active_workshop", {"workshop_id": None})
    cleared = _json(clear_result)
    assert cleared.get("active_workshop_id") is None


# ---------------------------------------------------------------------------
# Version tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_primitive_history(mcp_server):
    """get_primitive_history should return a list of commits."""
    result = await mcp_server.call_tool(
        "get_primitive_history",
        {"path": "tools/stitching-chisel/manifest.json"},
    )
    data = _json(result)
    assert "commits" in data
    assert data["total"] >= 1
    assert "hash" in data["commits"][0]


@pytest.mark.asyncio
async def test_compare_versions(mcp_server):
    """compare_versions should return a structured diff."""
    result = await mcp_server.call_tool(
        "compare_versions",
        {"path": "tools/stitching-chisel/manifest.json"},
    )
    data = _json(result)
    assert "changes" in data
    assert "from_hash" in data
    assert "to_hash" in data


@pytest.mark.asyncio
async def test_get_primitive_at_version_tool(mcp_server):
    """get_primitive_at_version should return the primitive at the specified commit."""
    result = await mcp_server.call_tool(
        "get_primitive_at_version",
        {
            "path": "tools/stitching-chisel/manifest.json",
            "commit_hash": SAMPLE_HASH,
        },
    )
    data = _json(result)
    assert data["name"] == SAMPLE_PRIMITIVE.name


# ---------------------------------------------------------------------------
# Settings tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_settings_round_trip(mcp_server):
    """get_settings → update_settings → get_settings round-trip."""
    get_result = await mcp_server.call_tool("get_settings", {})
    settings = _json(get_result)
    assert "preferences" in settings

    update_result = await mcp_server.call_tool(
        "update_settings",
        {"preferences": {"my_pref": "my_value"}},
    )
    updated = _json(update_result)
    assert updated["preferences"].get("my_pref") == "my_value"


@pytest.mark.asyncio
async def test_theme_round_trip(mcp_server):
    """get_theme → set_theme → get_theme round-trip."""
    get_result = await mcp_server.call_tool("get_theme", {})
    theme = _json(get_result)
    assert "name" in theme

    set_result = await mcp_server.call_tool("set_theme", {"name": "workshop"})
    set_data = _json(set_result)
    assert set_data["name"] == "workshop"

    verify_result = await mcp_server.call_tool("get_theme", {})
    verify = _json(verify_result)
    assert verify["name"] == "workshop"


# ---------------------------------------------------------------------------
# System tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_status(mcp_server):
    """get_status should return Shell runtime info."""
    result = await mcp_server.call_tool("get_status", {})
    data = _json(result)
    assert "shell_version" in data
    assert "core_connected" in data
    assert "uptime_seconds" in data


@pytest.mark.asyncio
async def test_get_capabilities(mcp_server):
    """get_capabilities should return the full operation list."""
    result = await mcp_server.call_tool("get_capabilities", {})
    data = _json(result)
    assert "capabilities" in data
    assert len(data["capabilities"]) > 0
    # Spot-check a few capabilities
    paths = {c["path"] for c in data["capabilities"]}
    assert "/api/catalogue/search" in paths
    assert "/api/inventory" in paths
    assert "/api/workshops" in paths


# ---------------------------------------------------------------------------
# Module tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_modules(mcp_server):
    """list_modules should return an empty list (no modules installed yet)."""
    result = await mcp_server.call_tool("list_modules", {})
    data = _json(result)
    assert "items" in data
    assert data["total"] == 0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_primitive_not_found_returns_error(mcp_server, mock_core):
    """get_primitive for a nonexistent path should return an error with a suggestion."""
    from backend.app.core_client import CoreNotFoundError
    mock_core.get_primitive.side_effect = CoreNotFoundError("tools/nonexistent/manifest.json")

    result = await mcp_server.call_tool(
        "get_primitive",
        {"path": "tools/nonexistent/manifest.json"},
    )
    data = _json(result)
    # FastAPI returns a 404 detail; the MCP tool returns the full JSON
    assert "detail" in data or "error" in data
