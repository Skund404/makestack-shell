"""Makestack MCP Server — thin translation layer over the Shell REST API.

The MCP server exposes every Shell operation as an MCP tool. It is a pure
translation layer: tool call → HTTP request to Shell REST API → return JSON.
It does NOT access UserDB directly, talk to Core directly, or contain business logic.

Configuration via environment variables:
    MAKESTACK_SHELL_URL    Shell base URL (default: http://localhost:3000)
    MAKESTACK_SHELL_TOKEN  Bearer token if Shell auth is enabled (default: empty)

Usage:
    # SSE transport (mounted in FastAPI at /mcp):
    from mcp_server.server import create_server
    mcp = create_server()
    app.mount("/mcp", mcp.sse_app())

    # stdio transport (for Claude Code and local AI tools):
    python -m mcp_server
"""

import os

import httpx
from mcp.server.fastmcp import FastMCP

from .tools import catalogue, inventory, modules, settings, system, version, workshops


def create_server(api_client: httpx.AsyncClient | None = None) -> FastMCP:
    """Create and configure the Makestack MCP server.

    Args:
        api_client: Optional pre-configured httpx client. If not provided, one is
            created from environment variables. Pass a custom client in tests to
            use an ASGI transport against the test FastAPI app.

    Returns:
        A configured FastMCP instance with all tools registered.
    """
    if api_client is None:
        shell_url = os.getenv("MAKESTACK_SHELL_URL", "http://localhost:3000")
        shell_token = os.getenv("MAKESTACK_SHELL_TOKEN", "")
        headers: dict = {}
        if shell_token:
            headers["Authorization"] = f"Bearer {shell_token}"
        api_client = httpx.AsyncClient(
            base_url=shell_url,
            headers=headers,
            timeout=30.0,
        )

    mcp = FastMCP(
        name="makestack",
        instructions=(
            "You are connected to a Makestack Shell — a modular project management toolkit "
            "for makers (leatherworkers, cosplayers, woodworkers, 3D printers, etc.).\n\n"
            "The catalogue holds impersonal documented knowledge: techniques, materials, tools, "
            "workflows, projects, and events. Your personal inventory holds hash-pointer references "
            "to catalogue entries — what you own and when you added it.\n\n"
            "Workshops are schema-free organisational containers you can use however you like.\n\n"
            "Use get_capabilities to discover all available operations, or get_status to check "
            "system health."
        ),
    )

    # Register tool groups — order doesn't matter for MCP but keep it logical.
    catalogue.register_tools(mcp, api_client)
    inventory.register_tools(mcp, api_client)
    workshops.register_tools(mcp, api_client)
    version.register_tools(mcp, api_client)
    settings.register_tools(mcp, api_client)
    modules.register_tools(mcp, api_client)
    system.register_tools(mcp, api_client)

    return mcp
