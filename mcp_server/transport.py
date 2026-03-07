"""Transport setup for the Makestack MCP server.

Two transports are supported:

SSE (Server-Sent Events):
    For remote access. The Starlette app returned by create_sse_app() is
    mounted in the FastAPI Shell at /mcp. The SSE endpoint is at /mcp/sse.

stdio:
    For local AI tools (Claude Code, etc.). Run via `python -m mcp_server`
    or the `makestack mcp` CLI command.

The singleton MCP instance is exposed via get_mcp_server() so the lifespan
can register module tools after the module loader runs.
"""

from starlette.applications import Starlette

from .server import create_server
from mcp.server.fastmcp import FastMCP

# Module-level singleton — created once at startup, reused for tool registration.
_mcp_instance: FastMCP | None = None


def get_mcp_server() -> FastMCP:
    """Return (or lazily create) the singleton MCP server instance.

    The instance is created once and reused. This allows the lifespan to
    register module tools after the module loader runs.
    """
    global _mcp_instance
    if _mcp_instance is None:
        _mcp_instance = create_server()
    return _mcp_instance


def create_sse_app() -> Starlette:
    """Create a Starlette SSE app for mounting in the FastAPI Shell.

    Mount at /mcp so the SSE endpoint is available at /mcp/sse.

    Example (in backend/app/main.py):
        from mcp_server.transport import create_sse_app
        app.mount("/mcp", create_sse_app())
    """
    return get_mcp_server().sse_app()
