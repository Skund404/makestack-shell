"""MCP tools for system status and capabilities."""

import json

import httpx
from mcp.server.fastmcp import FastMCP


def register_tools(mcp: FastMCP, api: httpx.AsyncClient) -> None:
    """Register all system tools on the given FastMCP instance."""

    @mcp.tool()
    async def get_status() -> str:
        """Get the current system status — Shell health, Core connection, and loaded modules.

        Returns shell_version, core_connected, core_url, modules_loaded, modules_failed,
        userdb_path, and uptime_seconds. Use this to diagnose connectivity issues.
        """
        try:
            resp = await api.get("/api/status")
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running at the configured URL."})

    @mcp.tool()
    async def get_capabilities() -> str:
        """List all available operations in the Shell. Use this to discover what you can do.

        Returns a machine-readable description of every Shell API operation including
        method, path, description, and parameter schemas. Module endpoints are appended
        to this list when modules are loaded.
        """
        try:
            resp = await api.get("/api/capabilities")
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})
