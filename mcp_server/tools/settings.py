"""MCP tools for user settings and theme management."""

import json

import httpx
from mcp.server.fastmcp import FastMCP


def register_tools(mcp: FastMCP, api: httpx.AsyncClient) -> None:
    """Register all settings tools on the given FastMCP instance."""

    @mcp.tool()
    async def get_settings() -> str:
        """Get all current user settings and preferences.

        Returns a flat key-value map of all preferences including the active theme,
        active workshop context, and any other stored preferences.
        """
        try:
            resp = await api.get("/api/settings")
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def update_settings(preferences: dict) -> str:
        """Update user preferences. Merges provided key-value pairs into the stored set.

        Existing keys not present in the preferences dict are unchanged.
        To clear a preference, set its value to null.
        Returns the full updated preferences map.

        Example: {"theme": "workshop", "active_workshop_id": null}
        """
        try:
            resp = await api.put("/api/settings/preferences", json={"preferences": preferences})
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def get_theme() -> str:
        """Get the currently active UI theme name.

        Built-in themes: cyberpunk, workshop, daylight, high-contrast.
        """
        try:
            resp = await api.get("/api/settings/theme")
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def set_theme(name: str) -> str:
        """Switch the active UI theme.

        Built-in themes: cyberpunk, workshop, daylight, high-contrast.
        Additional themes can be installed via the registry.
        Returns the updated theme name.
        """
        try:
            resp = await api.put("/api/settings/theme", json={"name": name})
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})
