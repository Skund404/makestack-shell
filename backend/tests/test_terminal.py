"""Tests for Phase 9A: LogBroadcaster, BroadcastLogProcessor, and terminal endpoints."""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.app.log_broadcast import BroadcastLogProcessor, LogBroadcaster, get_broadcaster
from backend.app.routers.terminal import _is_rest_syntax, _translate_cli, _log_stream_generator


# ---------------------------------------------------------------------------
# LogBroadcaster unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcaster_subscribe_and_receive():
    """Subscriber queue receives broadcast events."""
    broadcaster = LogBroadcaster()
    q = broadcaster.subscribe()
    event = {"type": "log", "event": "hello"}

    broadcaster.broadcast(event)

    received = q.get_nowait()
    assert received == event


@pytest.mark.asyncio
async def test_broadcaster_unsubscribe_stops_delivery():
    """Unsubscribed queue no longer receives events."""
    broadcaster = LogBroadcaster()
    q = broadcaster.subscribe()
    broadcaster.unsubscribe(q)
    broadcaster.broadcast({"type": "log", "event": "hello"})

    assert q.empty()


@pytest.mark.asyncio
async def test_broadcaster_unsubscribe_idempotent():
    """Calling unsubscribe on an unknown queue does not raise."""
    broadcaster = LogBroadcaster()
    q: asyncio.Queue = asyncio.Queue()
    broadcaster.unsubscribe(q)  # Should not raise


@pytest.mark.asyncio
async def test_broadcaster_drops_events_for_full_queue():
    """Full subscriber queue causes events to be dropped, not raised."""
    broadcaster = LogBroadcaster()
    q = broadcaster.subscribe()
    # Fill the queue to capacity.
    for i in range(LogBroadcaster.MAX_QUEUE_SIZE):
        q.put_nowait({"i": i})
    # This broadcast should silently drop the event.
    broadcaster.broadcast({"type": "log", "event": "overflow"})
    assert q.full()


@pytest.mark.asyncio
async def test_broadcaster_fans_out_to_multiple_subscribers():
    """A single broadcast reaches all subscribers."""
    broadcaster = LogBroadcaster()
    q1 = broadcaster.subscribe()
    q2 = broadcaster.subscribe()
    event = {"type": "log", "event": "multi"}

    broadcaster.broadcast(event)

    assert q1.get_nowait() == event
    assert q2.get_nowait() == event


# ---------------------------------------------------------------------------
# BroadcastLogProcessor unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_processor_pushes_to_broadcaster():
    """BroadcastLogProcessor calls broadcaster.broadcast with a LogEntry."""
    mock_broadcaster = MagicMock(spec=LogBroadcaster)
    processor = BroadcastLogProcessor()

    event_dict = {
        "event": "shell_started",
        "level": "info",
        "timestamp": "2026-03-13T00:00:00+00:00",
        "component": "startup",
        "version": "0.1.0",
    }

    with patch("backend.app.log_broadcast.get_broadcaster", return_value=mock_broadcaster):
        result = processor(logger=None, method="info", event_dict=event_dict)

    # Must return event_dict unchanged so the chain continues.
    assert result is event_dict

    mock_broadcaster.broadcast.assert_called_once()
    entry = mock_broadcaster.broadcast.call_args[0][0]
    assert entry["type"] == "log"
    assert entry["event"] == "shell_started"
    assert entry["level"] == "info"
    assert entry["component"] == "startup"
    assert entry["timestamp"] == "2026-03-13T00:00:00+00:00"
    assert entry["version"] == "0.1.0"  # Extra fields carried through


@pytest.mark.asyncio
async def test_broadcast_processor_handles_non_serialisable_values():
    """Non-serialisable extra fields are coerced to str, not dropped."""
    processor = BroadcastLogProcessor()

    class Opaque:
        def __str__(self) -> str:
            return "opaque-value"

    event_dict = {
        "event": "test",
        "level": "debug",
        "timestamp": "t",
        "component": "x",
        "opaque_field": Opaque(),
    }

    captured: list[dict] = []
    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast.side_effect = lambda e: captured.append(e)

    with patch("backend.app.log_broadcast.get_broadcaster", return_value=mock_broadcaster):
        processor(logger=None, method="debug", event_dict=event_dict)

    assert captured[0]["opaque_field"] == "opaque-value"


# ---------------------------------------------------------------------------
# Syntax detection and CLI translation unit tests
# ---------------------------------------------------------------------------


def test_is_rest_syntax_detects_verbs():
    assert _is_rest_syntax("GET /api/status") is True
    assert _is_rest_syntax("POST /api/workshops") is True
    assert _is_rest_syntax("DELETE /api/inventory/123") is True
    assert _is_rest_syntax("get /health") is True  # case-insensitive


def test_is_rest_syntax_rejects_cli():
    assert _is_rest_syntax("status") is False
    assert _is_rest_syntax("modules") is False
    assert _is_rest_syntax("catalogue tools") is False


def test_translate_cli_known_commands():
    assert _translate_cli("status") == ("GET", "/api/status")
    assert _translate_cli("health") == ("GET", "/health")
    assert _translate_cli("modules") == ("GET", "/api/modules")
    assert _translate_cli("packages") == ("GET", "/api/packages")
    assert _translate_cli("registries") == ("GET", "/api/registries")
    assert _translate_cli("inventory") == ("GET", "/api/inventory")
    assert _translate_cli("workshops") == ("GET", "/api/workshops")
    assert _translate_cli("settings") == ("GET", "/api/settings")
    assert _translate_cli("capabilities") == ("GET", "/api/capabilities")
    assert _translate_cli("export") == ("GET", "/api/data/export")
    assert _translate_cli("mcp-log") == ("GET", "/api/mcp-log")


def test_translate_cli_catalogue_without_arg():
    assert _translate_cli("catalogue") == ("GET", "/api/catalogue")


def test_translate_cli_catalogue_with_type():
    assert _translate_cli("catalogue tools") == ("GET", "/api/catalogue/tools")
    assert _translate_cli("catalogue materials") == ("GET", "/api/catalogue/materials")


def test_translate_cli_unknown_command():
    assert _translate_cli("foobar") is None
    assert _translate_cli("") is None


# ---------------------------------------------------------------------------
# SSE stream generator unit test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sse_generator_yields_broadcast_event():
    """_log_stream_generator yields SSE-formatted data for each broadcast event."""
    broadcaster = LogBroadcaster()

    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=False)

    async def _feed_and_cancel() -> None:
        await asyncio.sleep(0.01)  # Let generator subscribe first.
        broadcaster.broadcast(
            {
                "type": "log",
                "event": "test_event",
                "level": "info",
                "timestamp": "2026-03-13T00:00:00+00:00",
                "component": "test",
            }
        )

    gen = _log_stream_generator(mock_request, broadcaster)
    asyncio.create_task(_feed_and_cancel())
    chunk = await asyncio.wait_for(gen.__anext__(), timeout=2.0)
    await gen.aclose()

    assert chunk.startswith("data: ")
    assert chunk.endswith("\n\n")
    payload = json.loads(chunk[len("data: "):].strip())
    assert payload["type"] == "log"
    assert payload["event"] == "test_event"


# ---------------------------------------------------------------------------
# SSE endpoint integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sse_stream_routes_registered(client):
    """Both terminal routes appear in the OpenAPI spec."""
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/api/terminal/stream" in paths
    assert "/api/terminal/exec" in paths


@pytest.mark.asyncio
async def test_sse_stream_endpoint_metadata(test_app):
    """SSE endpoint returns 200 with text/event-stream and correct headers.

    httpx's ASGITransport buffers the full response, so we can't test an
    infinite SSE stream through it.  Instead, mock the generator to yield one
    event and exit immediately — this lets the transport complete while still
    verifying the route wiring, content-type, and cache-control headers.
    """
    test_app.state.config = {"core_url": "http://localhost:8420", "port": 3000}

    async def _one_shot_generator(request, broadcaster):  # type: ignore[override]
        yield f'data: {json.dumps({"type": "heartbeat", "timestamp": "t"})}\n\n'

    with patch("backend.app.routers.terminal._log_stream_generator", side_effect=_one_shot_generator):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/terminal/stream")

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    assert resp.headers.get("cache-control") == "no-cache"
    # Body contains the one heartbeat event we injected.
    assert "heartbeat" in resp.text


# ---------------------------------------------------------------------------
# Exec endpoint integration tests
# ---------------------------------------------------------------------------


def _make_mock_http_client(status_code: int = 200, text: str = '{"ok": true}') -> Any:
    """Return a patched httpx.AsyncClient context manager mock."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.text = text

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)
    mock_http.request = AsyncMock(return_value=mock_response)
    return mock_http


@pytest.mark.asyncio
async def test_exec_cli_status_command(client, test_app):
    """CLI 'status' returns command → request → response entries."""
    test_app.state.config = {"core_url": "http://localhost:8420", "port": 3000}
    mock_http = _make_mock_http_client(status_code=200, text='{"shell_version": "0.1.0"}')

    with patch("backend.app.routers.terminal.httpx.AsyncClient", return_value=mock_http):
        resp = await client.post(
            "/api/terminal/exec",
            json={"input": "status", "syntax": "auto"},
        )

    assert resp.status_code == 200
    entries = resp.json()["entries"]
    # Three entries: command, request, response.
    assert len(entries) == 3
    assert entries[0]["type"] == "command"
    assert entries[0]["event"] == "status"
    assert entries[1]["type"] == "request"
    assert entries[1]["method"] == "GET"
    assert entries[1]["path"] == "/api/status"
    assert entries[2]["type"] == "response"
    assert entries[2]["status_code"] == 200
    assert entries[2]["level"] == "info"
    assert "elapsed_ms" in entries[2]

    # Verify the underlying request was made to the right URL.
    mock_http.request.assert_called_once_with("GET", "http://localhost:3000/api/status")


@pytest.mark.asyncio
async def test_exec_rest_syntax(client, test_app):
    """REST syntax 'GET /api/status' is detected and returns command → request → response."""
    test_app.state.config = {"core_url": "http://localhost:8420", "port": 3000}
    mock_http = _make_mock_http_client(status_code=200, text='{"status": "ok"}')

    with patch("backend.app.routers.terminal.httpx.AsyncClient", return_value=mock_http):
        resp = await client.post(
            "/api/terminal/exec",
            json={"input": "GET /api/status", "syntax": "auto"},
        )

    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert len(entries) == 3
    assert entries[0]["type"] == "command"
    assert entries[1]["type"] == "request"
    assert entries[1]["method"] == "GET"
    assert entries[1]["path"] == "/api/status"
    assert entries[2]["type"] == "response"

    mock_http.request.assert_called_once_with("GET", "http://localhost:3000/api/status")


@pytest.mark.asyncio
async def test_exec_explicit_rest_syntax_flag(client, test_app):
    """syntax='rest' forces REST interpretation even for short strings."""
    test_app.state.config = {"core_url": "http://localhost:8420", "port": 3000}
    mock_http = _make_mock_http_client(status_code=200)

    with patch("backend.app.routers.terminal.httpx.AsyncClient", return_value=mock_http):
        resp = await client.post(
            "/api/terminal/exec",
            json={"input": "GET /health", "syntax": "rest"},
        )

    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert entries[1]["path"] == "/health"  # entries[1] = request entry


@pytest.mark.asyncio
async def test_exec_unknown_cli_command(client, test_app):
    """Unknown CLI command returns command + error entries without making an HTTP request."""
    test_app.state.config = {"core_url": "http://localhost:8420", "port": 3000}

    with patch("backend.app.routers.terminal.httpx.AsyncClient") as mock_cls:
        resp = await client.post(
            "/api/terminal/exec",
            json={"input": "foobar", "syntax": "cli"},
        )
        mock_cls.assert_not_called()

    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert len(entries) == 2
    assert entries[0]["type"] == "command"
    assert entries[1]["type"] == "error"
    assert "foobar" in entries[1]["event"]
    assert "suggestion" in entries[1]


@pytest.mark.asyncio
async def test_exec_cli_catalogue_with_type(client, test_app):
    """'catalogue tools' translates to GET /api/catalogue/tools."""
    test_app.state.config = {"core_url": "http://localhost:8420", "port": 3000}
    mock_http = _make_mock_http_client(status_code=200, text='{"items": []}')

    with patch("backend.app.routers.terminal.httpx.AsyncClient", return_value=mock_http):
        resp = await client.post(
            "/api/terminal/exec",
            json={"input": "catalogue tools", "syntax": "cli"},
        )

    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert entries[1]["path"] == "/api/catalogue/tools"  # entries[1] = request entry
    mock_http.request.assert_called_once_with("GET", "http://localhost:3000/api/catalogue/tools")


@pytest.mark.asyncio
async def test_exec_returns_error_entry_on_http_failure(client, test_app):
    """httpx connection error produces command → request → error entries (not a 500)."""
    test_app.state.config = {"core_url": "http://localhost:8420", "port": 3000}

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)
    mock_http.request = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

    with patch("backend.app.routers.terminal.httpx.AsyncClient", return_value=mock_http):
        resp = await client.post(
            "/api/terminal/exec",
            json={"input": "status", "syntax": "cli"},
        )

    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert len(entries) == 3
    assert entries[0]["type"] == "command"
    assert entries[1]["type"] == "request"
    assert entries[2]["type"] == "error"
    assert "Connection refused" in entries[2]["event"]


@pytest.mark.asyncio
async def test_exec_empty_input(client, test_app):
    """Empty input returns a single error entry (no command echo)."""
    test_app.state.config = {"core_url": "http://localhost:8420", "port": 3000}

    resp = await client.post(
        "/api/terminal/exec",
        json={"input": "   ", "syntax": "auto"},
    )

    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["type"] == "error"


# ---------------------------------------------------------------------------
# Docs index tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docs_returns_two_sections(client):
    """GET /api/terminal/docs returns api and commands keys, no widgets."""
    resp = await client.get("/api/terminal/docs")
    assert resp.status_code == 200
    data = resp.json()
    assert "api" in data
    assert "commands" in data
    assert "widgets" not in data


@pytest.mark.asyncio
async def test_docs_api_section_contains_capabilities(client):
    """api section contains the same capabilities as GET /api/capabilities."""
    docs = await client.get("/api/terminal/docs")
    caps = await client.get("/api/capabilities")
    assert len(docs.json()["api"]) == len(caps.json()["capabilities"])


@pytest.mark.asyncio
async def test_docs_commands_contains_all_cli_table_entries(client):
    """commands section exposes every entry in _CLI_TABLE."""
    resp = await client.get("/api/terminal/docs")
    assert resp.status_code == 200
    commands = resp.json()["commands"]
    keywords = {cmd["keyword"] for cmd in commands}
    # All 12 table entries must be present.
    for expected in ["status", "health", "capabilities", "modules", "packages",
                     "registries", "inventory", "workshops", "settings",
                     "export", "mcp-log", "catalogue"]:
        assert expected in keywords, f"Missing CLI command: {expected}"


@pytest.mark.asyncio
async def test_docs_commands_have_required_fields(client):
    """Each command entry has keyword, method, path, description, accepts_arg."""
    resp = await client.get("/api/terminal/docs")
    for cmd in resp.json()["commands"]:
        assert "keyword" in cmd
        assert "method" in cmd
        assert "path" in cmd
        assert "description" in cmd
        assert "accepts_arg" in cmd


@pytest.mark.asyncio
async def test_docs_catalogue_command_accepts_arg(client):
    """The catalogue command is flagged accepts_arg=True."""
    resp = await client.get("/api/terminal/docs")
    cmds = {c["keyword"]: c for c in resp.json()["commands"]}
    assert cmds["catalogue"]["accepts_arg"] is True
    # All others should be False.
    assert cmds["status"]["accepts_arg"] is False
