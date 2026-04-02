"""Transport setup for the Makestack MCP server.

Three transports are supported:

SSE (Server-Sent Events):
    For local/LAN access. The Starlette app returned by create_sse_app() is
    mounted in the FastAPI Shell at /mcp. The SSE endpoint is at /mcp/sse.

Streamable HTTP:
    For internet-facing static URL access with API key auth. When
    MAKESTACK_MCP_API_KEY is set, a separate ASGI app is mounted at
    /mcp-http and wrapped with MCPKeyAuthMiddleware. Access via:
        https://makestack.yourdomain.com/mcp-http?key=your-secret-key

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


def create_streamable_http_app():
    """Create a Streamable HTTP ASGI app for static-URL remote access.

    Returns the raw ASGI app from FastMCP's streamable_http_app(). This is
    intended to be wrapped with MCPKeyAuthMiddleware and mounted at /mcp-http.

    Only call this when MAKESTACK_MCP_API_KEY is set — the endpoint should
    not be reachable without an API key.

    Example (in backend/app/main.py lifespan):
        from mcp_server.transport import create_streamable_http_app
        from mcp_server.auth import MCPKeyAuthMiddleware
        from starlette.middleware import Middleware

        raw_app = create_streamable_http_app()
        authed_app = MCPKeyAuthMiddleware(raw_app, api_key=mcp_api_key)
        app.mount("/mcp-http", authed_app)
    """
    return get_mcp_server().streamable_http_app()
