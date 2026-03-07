"""Transport setup for the Makestack MCP server.

Two transports are supported:

SSE (Server-Sent Events):
    For remote access. The Starlette app returned by create_sse_app() is
    mounted in the FastAPI Shell at /mcp. The SSE endpoint is at /mcp/sse.

stdio:
    For local AI tools (Claude Code, etc.). Run via `python -m mcp_server`
    or the `makestack mcp` CLI command.
"""

from starlette.applications import Starlette

from .server import create_server


def create_sse_app() -> Starlette:
    """Create a Starlette SSE app for mounting in the FastAPI Shell.

    Mount at /mcp so the SSE endpoint is available at /mcp/sse.

    Example (in backend/app/main.py):
        from mcp_server.transport import create_sse_app
        app.mount("/mcp", create_sse_app())
    """
    mcp = create_server()
    return mcp.sse_app()
