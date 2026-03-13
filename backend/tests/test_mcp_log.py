"""Tests for the MCP Action Log — REST endpoints and MCP server integration.

REST endpoint tests verify the full log lifecycle: append, query by day/tool/session,
and daily summary aggregation.

The integration test verifies that calling an MCP tool actually creates a log
entry in the UserDB (via the /api/mcp-log endpoint).
"""

from datetime import datetime, timezone

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

from mcp_server.server import create_server


# ---------------------------------------------------------------------------
# MCP server fixture (mirrors the one in test_mcp_server.py)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def mcp_server(test_app):
    """MCP server backed by the in-memory test Shell via ASGI transport."""
    transport = ASGITransport(app=test_app)
    api_client = httpx.AsyncClient(transport=transport, base_url="http://test")
    server = create_server(api_client=api_client)
    yield server
    await api_client.aclose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


async def _post_entry(client, **kwargs) -> dict:
    """POST a log entry with sensible defaults and return the JSON body."""
    payload = {
        "tool_name": kwargs.pop("tool_name", "test_tool"),
        "result_status": kwargs.pop("result_status", "success"),
        **kwargs,
    }
    resp = await client.post("/api/mcp-log", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# POST /api/mcp-log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_append_log_entry_minimal(client):
    """POST with minimal fields creates a valid log entry."""
    resp = await client.post(
        "/api/mcp-log",
        json={"tool_name": "search_catalogue", "result_status": "success"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["tool_name"] == "search_catalogue"
    assert data["result_status"] == "success"
    assert data["day"] == _today()
    assert data["tool_args"] == {}
    assert data["affected_paths"] == []
    assert data["id"]  # UUID was generated


@pytest.mark.asyncio
async def test_append_log_entry_full(client):
    """POST with all fields preserves every value."""
    resp = await client.post(
        "/api/mcp-log",
        json={
            "tool_name": "update_primitive",
            "tool_args": {"path": "tools/chisel/manifest.json", "name": "Chisel"},
            "result_status": "success",
            "result_summary": "Updated successfully",
            "affected_paths": ["tools/chisel/manifest.json"],
            "session_id": "sess-abc-123",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["tool_args"] == {"path": "tools/chisel/manifest.json", "name": "Chisel"}
    assert data["affected_paths"] == ["tools/chisel/manifest.json"]
    assert data["session_id"] == "sess-abc-123"
    assert data["result_summary"] == "Updated successfully"


@pytest.mark.asyncio
async def test_append_log_entry_error_status(client):
    """POST with result_status='error' is accepted."""
    resp = await client.post(
        "/api/mcp-log",
        json={
            "tool_name": "delete_primitive",
            "result_status": "error",
            "result_summary": "Connection refused",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["result_status"] == "error"


# ---------------------------------------------------------------------------
# GET /api/mcp-log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_log_empty(client):
    """No entries → empty paginated result."""
    resp = await client.get("/api/mcp-log")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["limit"] == 100
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_query_log_returns_all_entries(client):
    """GET without filters returns all entries."""
    await _post_entry(client, tool_name="tool_a")
    await _post_entry(client, tool_name="tool_b")
    await _post_entry(client, tool_name="tool_c")

    resp = await client.get("/api/mcp-log")
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


@pytest.mark.asyncio
async def test_query_log_by_day(client):
    """?day= filter returns only entries from that day."""
    today = _today()
    await _post_entry(client, tool_name="t1")
    await _post_entry(client, tool_name="t2")

    resp = await client.get(f"/api/mcp-log?day={today}")
    data = resp.json()
    assert data["total"] == 2

    # A future day has no entries.
    resp2 = await client.get("/api/mcp-log?day=2099-01-01")
    assert resp2.json()["total"] == 0


@pytest.mark.asyncio
async def test_query_log_by_tool(client):
    """?tool= filter returns only entries for that tool."""
    await _post_entry(client, tool_name="search_catalogue")
    await _post_entry(client, tool_name="get_primitive")
    await _post_entry(client, tool_name="search_catalogue")

    resp = await client.get("/api/mcp-log?tool=search_catalogue")
    data = resp.json()
    assert data["total"] == 2
    assert all(i["tool_name"] == "search_catalogue" for i in data["items"])


@pytest.mark.asyncio
async def test_query_log_by_session(client):
    """?session= filter returns only entries for that session."""
    await _post_entry(client, tool_name="t1", session_id="session-aaa")
    await _post_entry(client, tool_name="t2", session_id="session-bbb")
    await _post_entry(client, tool_name="t3", session_id="session-aaa")

    resp = await client.get("/api/mcp-log?session=session-aaa")
    data = resp.json()
    assert data["total"] == 2
    assert all(i["session_id"] == "session-aaa" for i in data["items"])


@pytest.mark.asyncio
async def test_query_log_combined_filters(client):
    """Multiple filters are ANDed together."""
    today = _today()
    await _post_entry(client, tool_name="search_catalogue", session_id="sess-1")
    await _post_entry(client, tool_name="search_catalogue", session_id="sess-2")
    await _post_entry(client, tool_name="get_primitive", session_id="sess-1")

    resp = await client.get(
        f"/api/mcp-log?day={today}&tool=search_catalogue&session=sess-1"
    )
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["tool_name"] == "search_catalogue"
    assert data["items"][0]["session_id"] == "sess-1"


@pytest.mark.asyncio
async def test_query_log_pagination(client):
    """limit and offset paginate the result correctly."""
    for i in range(5):
        await _post_entry(client, tool_name=f"tool_{i}")

    resp = await client.get("/api/mcp-log?limit=2&offset=0")
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2

    resp2 = await client.get("/api/mcp-log?limit=2&offset=4")
    data2 = resp2.json()
    assert len(data2["items"]) == 1


@pytest.mark.asyncio
async def test_query_log_ordered_by_timestamp_desc(client):
    """Entries are returned newest-first."""
    await _post_entry(client, tool_name="first")
    await _post_entry(client, tool_name="second")
    await _post_entry(client, tool_name="third")

    resp = await client.get("/api/mcp-log")
    items = resp.json()["items"]
    # "third" was inserted last → should appear first in DESC order.
    assert items[0]["tool_name"] == "third"
    assert items[-1]["tool_name"] == "first"


# ---------------------------------------------------------------------------
# GET /api/mcp-log/summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summary_empty(client):
    """No entries → empty summary list."""
    resp = await client.get("/api/mcp-log/summary")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_summary_aggregation(client):
    """Summary correctly totals actions, by-tool counts, and error counts."""
    for _ in range(3):
        await _post_entry(client, tool_name="search_catalogue", result_status="success")
    await _post_entry(client, tool_name="get_primitive", result_status="error")

    resp = await client.get("/api/mcp-log/summary?days=7")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)

    today = _today()
    today_entry = next((d for d in data if d["day"] == today), None)
    assert today_entry is not None
    assert today_entry["total_actions"] == 4
    assert today_entry["by_tool"]["search_catalogue"] == 3
    assert today_entry["by_tool"]["get_primitive"] == 1
    assert today_entry["errors"] == 1


@pytest.mark.asyncio
async def test_summary_days_param(client):
    """days=1 returns only today's data."""
    await _post_entry(client, tool_name="t1")
    resp = await client.get("/api/mcp-log/summary?days=1")
    data = resp.json()
    assert len(data) >= 1  # At least today's entry exists.


# ---------------------------------------------------------------------------
# MCP server integration — tool calls are transparently logged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_tool_call_creates_log_entry(mcp_server, client):
    """Calling an MCP tool via call_tool() creates a log entry in /api/mcp-log."""
    # Call a real tool through the logging MCP server.
    result = await mcp_server.call_tool("list_workshops", {})
    assert result  # Tool returned something.

    # Verify the log entry was written.
    resp = await client.get("/api/mcp-log?tool=list_workshops")
    data = resp.json()
    assert data["total"] >= 1
    entry = data["items"][0]
    assert entry["tool_name"] == "list_workshops"
    assert entry["result_status"] == "success"
    # session_id should be a non-empty UUID string.
    assert entry["session_id"] and len(entry["session_id"]) > 0


@pytest.mark.asyncio
async def test_mcp_multiple_tool_calls_all_logged(mcp_server, client):
    """Each tool call creates a separate log entry."""
    await mcp_server.call_tool("list_workshops", {})
    await mcp_server.call_tool("get_status", {})
    await mcp_server.call_tool("list_workshops", {})

    resp = await client.get("/api/mcp-log")
    data = resp.json()
    # At least these 3 entries exist (other tests may add more in the same DB).
    assert data["total"] >= 3


@pytest.mark.asyncio
async def test_mcp_tool_calls_share_session_id(mcp_server, client):
    """All tool calls from the same server instance share one session_id."""
    await mcp_server.call_tool("list_workshops", {})
    await mcp_server.call_tool("get_status", {})

    resp = await client.get("/api/mcp-log")
    items = resp.json()["items"]
    # Filter to just our calls (both tool names were called above).
    our_items = [
        i for i in items
        if i["tool_name"] in ("list_workshops", "get_status")
    ]
    assert len(our_items) >= 2
    # All share the same session_id.
    session_ids = {i["session_id"] for i in our_items}
    assert len(session_ids) == 1


@pytest.mark.asyncio
async def test_mcp_affected_paths_update_primitive(mcp_server, client):
    """update_primitive logs the path in affected_paths."""
    from backend.tests.conftest import SAMPLE_PRIMITIVE

    await mcp_server.call_tool(
        "update_primitive",
        {
            "path": "tools/stitching-chisel/manifest.json",
            "id": SAMPLE_PRIMITIVE.id,
            "type": "tool",
            "name": "Stitching Chisel",
            "slug": "stitching-chisel",
        },
    )

    resp = await client.get("/api/mcp-log?tool=update_primitive")
    data = resp.json()
    assert data["total"] >= 1
    assert "tools/stitching-chisel/manifest.json" in data["items"][0]["affected_paths"]


@pytest.mark.asyncio
async def test_mcp_affected_paths_delete_primitive(mcp_server, client):
    """delete_primitive logs the path in affected_paths."""
    await mcp_server.call_tool(
        "delete_primitive",
        {"path": "tools/stitching-chisel/manifest.json"},
    )

    resp = await client.get("/api/mcp-log?tool=delete_primitive")
    data = resp.json()
    assert data["total"] >= 1
    assert "tools/stitching-chisel/manifest.json" in data["items"][0]["affected_paths"]


# ---------------------------------------------------------------------------
# MCP log query tools (list_mcp_actions, get_daily_summary)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_mcp_actions_tool(mcp_server, client):
    """list_mcp_actions MCP tool returns logged entries."""
    import json as _json
    from mcp.types import TextContent

    await _post_entry(client, tool_name="search_catalogue")
    await _post_entry(client, tool_name="search_catalogue")

    result = await mcp_server.call_tool(
        "list_mcp_actions", {"tool": "search_catalogue"}
    )
    assert result
    first = result[0]
    if isinstance(first, list):
        first = first[0]
    assert isinstance(first, TextContent)
    data = _json.loads(first.text)
    assert data["total"] >= 2


@pytest.mark.asyncio
async def test_get_daily_summary_tool(mcp_server, client):
    """get_daily_summary MCP tool returns day-level aggregates."""
    import json as _json
    from mcp.types import TextContent

    await _post_entry(client, tool_name="get_primitive")

    result = await mcp_server.call_tool("get_daily_summary", {"days": 7})
    assert result
    first = result[0]
    if isinstance(first, list):
        first = first[0]
    assert isinstance(first, TextContent)
    data = _json.loads(first.text)
    assert isinstance(data, list)
    today = _today()
    today_entry = next((d for d in data if d["day"] == today), None)
    assert today_entry is not None
    assert today_entry["total_actions"] >= 1
