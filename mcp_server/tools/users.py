"""MCP tools for user account management.

Thin wrappers over the Shell's /api/users/* REST endpoints.
"""

import json

import httpx
from mcp.server.fastmcp import FastMCP


def register_tools(mcp: FastMCP, api: httpx.AsyncClient) -> None:
    """Register all user-management tools on the MCP server."""

    @mcp.tool()
    async def get_user_profile() -> str:
        """Get the current user's profile (name, avatar, bio, timezone, locale).

        Returns a JSON object with all profile fields and timestamps.
        """
        try:
            resp = await api.get("/api/users/me")
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def update_user_profile(
        name: str | None = None,
        avatar_path: str | None = None,
        bio: str | None = None,
        timezone: str | None = None,
        locale: str | None = None,
    ) -> str:
        """Update the current user's profile.

        All fields are optional — only provided fields are changed.

        Args:
            name: Display name (must not be blank).
            avatar_path: Path or URL to a profile avatar (empty string clears it).
            bio: Short biography or description.
            timezone: IANA timezone string, e.g. "Europe/London" or "UTC".
            locale: Language locale code, e.g. "en", "de", "fr".
        """
        body: dict = {}
        if name is not None:
            body["name"] = name
        if avatar_path is not None:
            body["avatar_path"] = avatar_path
        if bio is not None:
            body["bio"] = bio
        if timezone is not None:
            body["timezone"] = timezone
        if locale is not None:
            body["locale"] = locale

        try:
            resp = await api.put("/api/users/me", json=body)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def get_user_stats() -> str:
        """Get an activity summary for the current user.

        Returns counts of workshops, inventory items (total and updated since
        pinning), installed modules (total and enabled), and the active workshop
        name if one is set.
        """
        try:
            resp = await api.get("/api/users/me/stats")
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})
