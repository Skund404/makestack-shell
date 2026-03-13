"""Terminal routes — interactive exec, SSE log stream.

GET  /api/terminal/stream — SSE stream of all structlog events + heartbeats.
POST /api/terminal/exec   — Execute a CLI or REST command via httpx.

Both endpoints are always available (no dev-mode guard).

CLI translation table lives here and nowhere else. Frontend has NO table.
Syntax detection via _is_rest_syntax() — used for HTTP hint label only.
"""

import asyncio
import json
import re
import time
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
import structlog
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..log_broadcast import LogBroadcaster, get_broadcaster
from ..models import Capability

log = structlog.get_logger().bind(component="terminal")

router = APIRouter(prefix="/api/terminal", tags=["terminal"])

# ---------------------------------------------------------------------------
# CLI translation table  (12 commands, backend-only)
# ---------------------------------------------------------------------------

# Maps CLI keyword → (HTTP method, path template).
# Path templates that end with /{arg} require one positional argument.
_CLI_TABLE: dict[str, tuple[str, str]] = {
    "status":       ("GET",  "/api/status"),
    "health":       ("GET",  "/health"),
    "capabilities": ("GET",  "/api/capabilities"),
    "modules":      ("GET",  "/api/modules"),
    "packages":     ("GET",  "/api/packages"),
    "registries":   ("GET",  "/api/registries"),
    "inventory":    ("GET",  "/api/inventory"),
    "workshops":    ("GET",  "/api/workshops"),
    "settings":     ("GET",  "/api/settings"),
    "export":       ("GET",  "/api/data/export"),
    "mcp-log":      ("GET",  "/api/mcp-log"),
    # catalogue requires a type argument: "catalogue tools" → GET /api/catalogue/tools
    "catalogue":    ("GET",  "/api/catalogue"),
}

# Human-readable description for each CLI command (used by the docs index).
_CLI_DESCRIPTIONS: dict[str, str] = {
    "status":       "Shell runtime status — version, core connection, uptime",
    "health":       "Minimal health check — returns {status: ok}",
    "capabilities": "Machine-readable list of all Shell API operations",
    "modules":      "List installed modules with load state",
    "packages":     "List all installed packages",
    "registries":   "List configured package registries",
    "inventory":    "List personal inventory items",
    "workshops":    "List all workshops",
    "settings":     "Read user preferences and active theme",
    "export":       "Export personal data as portable JSON",
    "mcp-log":      "Query the MCP action audit log",
    "catalogue":    "List catalogue primitives — optionally supply a type: catalogue tools",
}

# REST syntax: starts with an HTTP verb followed by a space and a path.
_REST_RE = re.compile(r"^(GET|POST|PUT|DELETE|PATCH)\s+/", re.IGNORECASE)


def _is_rest_syntax(text: str) -> bool:
    """Return True if text looks like a REST command (e.g. 'GET /api/status')."""
    return bool(_REST_RE.match(text.strip()))


def _translate_cli(text: str) -> tuple[str, str] | None:
    """Translate a CLI command string to (method, path).

    Returns None if the command is not in the translation table.
    Handles one optional positional argument (e.g. 'catalogue tools').
    """
    parts = text.strip().split()
    if not parts:
        return None
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd not in _CLI_TABLE:
        return None

    method, path = _CLI_TABLE[cmd]

    # Commands that accept a positional argument appended to the path.
    if cmd == "catalogue" and args:
        return method, f"{path}/{args[0]}"

    return method, path


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ExecRequest(BaseModel):
    input: str
    syntax: Literal["auto", "cli", "rest"] = "auto"


class ExecResponse(BaseModel):
    entries: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Helpers for building LogEntry dicts
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _command_entry(input_text: str) -> dict[str, Any]:
    return {
        "type": "command",
        "timestamp": _now(),
        "component": "terminal",
        "event": input_text,
    }


def _request_entry(method: str, path: str, body: Any = None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "type": "request",
        "timestamp": _now(),
        "component": "terminal",
        "event": f"{method} {path}",
        "method": method,
        "path": path,
    }
    if body is not None:
        entry["body"] = body
    return entry


def _response_entry(
    method: str,
    path: str,
    status_code: int,
    body: str,
    elapsed_ms: int,
) -> dict[str, Any]:
    return {
        "type": "response",
        "timestamp": _now(),
        "level": "info" if status_code < 400 else "warning",
        "component": "terminal",
        "event": f"HTTP {status_code}",
        "method": method,
        "path": path,
        "status_code": status_code,
        "elapsed_ms": elapsed_ms,
        "body": body,
    }


def _error_entry(message: str, **extra: Any) -> dict[str, Any]:
    return {
        "type": "error",
        "timestamp": _now(),
        "level": "error",
        "component": "terminal",
        "event": message,
        **extra,
    }


# ---------------------------------------------------------------------------
# SSE log stream
# ---------------------------------------------------------------------------


async def _log_stream_generator(
    request: Request,
    broadcaster: LogBroadcaster,
) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE-formatted log events.

    Subscribes to the LogBroadcaster. Sends a heartbeat if no event arrives
    within 15 seconds. Cleans up the subscriber queue on disconnect.
    """
    q = broadcaster.subscribe()
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(q.get(), timeout=15.0)
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                heartbeat = {
                    "type": "heartbeat",
                    "timestamp": _now(),
                }
                yield f"data: {json.dumps(heartbeat)}\n\n"
    except (asyncio.CancelledError, GeneratorExit):
        pass
    finally:
        broadcaster.unsubscribe(q)


@router.get("/stream", summary="SSE log stream")
async def stream_logs(request: Request) -> StreamingResponse:
    """Server-Sent Events stream of all structlog events.

    Broadcasts every log entry produced by the Shell backend in real time.
    Sends a heartbeat event every 15 seconds to keep the connection alive.
    Filtering is client-side — all events are broadcast.
    """
    return StreamingResponse(
        _log_stream_generator(request, get_broadcaster()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Terminal exec
# ---------------------------------------------------------------------------


@router.post("/exec", response_model=ExecResponse, summary="Execute a terminal command")
async def exec_command(body: ExecRequest, request: Request) -> ExecResponse:
    """Execute a CLI or REST command via httpx against localhost.

    Uses the same code path as the React frontend — no direct DB or Core access.
    Syntax detection: 'auto' sniffs for HTTP verb prefix; falls back to CLI.
    CLI commands are translated via the built-in table (backend-only).
    """
    port: int = getattr(request.app.state, "config", {}).get("port", 3000)
    base_url = f"http://localhost:{port}"
    input_text = body.input.strip()

    if not input_text:
        return ExecResponse(entries=[_error_entry("Empty input")])

    # Determine whether this is REST or CLI syntax.
    use_rest = body.syntax == "rest" or (
        body.syntax == "auto" and _is_rest_syntax(input_text)
    )

    if use_rest:
        # Parse: "METHOD /path [json-body]"
        parts = input_text.split(None, 2)
        method = parts[0].upper()
        path = parts[1] if len(parts) > 1 else "/"
        raw_body = parts[2] if len(parts) > 2 else None
    else:
        # CLI mode — translate via table.
        result = _translate_cli(input_text)
        if result is None:
            cmd_name = input_text.split()[0]
            return ExecResponse(
                entries=[
                    _command_entry(input_text),
                    _error_entry(
                        f"Unknown command: {cmd_name}",
                        suggestion=(
                            "Use 'capabilities' to list available commands, "
                            "or use REST syntax: GET /api/status"
                        ),
                    ),
                ]
            )
        method, path = result
        raw_body = None

    # Parse optional request body.
    parsed_body: Any = None
    kwargs: dict[str, Any] = {}
    if raw_body:
        try:
            parsed_body = json.loads(raw_body)
            kwargs["json"] = parsed_body
        except ValueError:
            kwargs["content"] = raw_body.encode()

    # Execute via httpx — same code path as the frontend.
    url = f"{base_url}{path}"
    try:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=30.0) as http:
            response = await http.request(method, url, **kwargs)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        log.info(
            "terminal_exec",
            method=method,
            path=path,
            status=response.status_code,
            elapsed_ms=elapsed_ms,
        )
        return ExecResponse(
            entries=[
                _command_entry(input_text),
                _request_entry(method, path, parsed_body),
                _response_entry(method, path, response.status_code, response.text, elapsed_ms),
            ]
        )
    except Exception as exc:
        log.error("terminal_exec_failed", method=method, path=path, error=str(exc))
        return ExecResponse(
            entries=[
                _command_entry(input_text),
                _request_entry(method, path, parsed_body),
                _error_entry(f"Request failed: {exc}", method=method, path=path),
            ]
        )


# ---------------------------------------------------------------------------
# Docs index
# ---------------------------------------------------------------------------


class CliCommand(BaseModel):
    """A single entry from the CLI translation table."""

    keyword: str
    method: str
    path: str
    description: str
    accepts_arg: bool = False  # True when a positional argument extends the path.


class DocsResponse(BaseModel):
    """Response for GET /api/terminal/docs.

    api      — full Capability list from the Shell capabilities registry.
    commands — CLI translation table (backend-only; frontend has no copy).

    Widgets are NOT included — widget metadata is frontend-owned (KeywordRegistry).
    """

    api: list[Capability]
    commands: list[CliCommand]


@router.get("/docs", response_model=DocsResponse, summary="Terminal docs index")
async def get_docs() -> DocsResponse:
    """Return the docs index used by the DocsPanel (9E) and autocomplete.

    Two sections only:
      api      — every Shell API operation (same list as GET /api/capabilities).
      commands — the CLI keyword → HTTP translation table.

    Widget entries are frontend-owned and composed client-side from KeywordRegistry.
    No dev-mode guard — always available.
    """
    from .system import _CAPABILITIES  # Import here to avoid circular imports at module load.

    commands = [
        CliCommand(
            keyword=keyword,
            method=method,
            path=path,
            description=_CLI_DESCRIPTIONS.get(keyword, ""),
            accepts_arg=(keyword == "catalogue"),
        )
        for keyword, (method, path) in _CLI_TABLE.items()
    ]

    return DocsResponse(api=_CAPABILITIES, commands=commands)
