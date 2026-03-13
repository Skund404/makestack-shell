"""MCP tools for querying the MCP Action Log."""

import json

import httpx
from mcp.server.fastmcp import FastMCP


def register_tools(mcp: FastMCP, api: httpx.AsyncClient) -> None:
    """Register MCP action log query tools on the given FastMCP instance."""

    @mcp.tool()
    async def list_mcp_actions(
        day: str | None = None,
        tool: str | None = None,
        session: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> str:
        """List logged MCP tool invocations with optional filters.

        day: filter to a specific calendar day (YYYY-MM-DD format).
        tool: filter to a specific tool name (e.g. 'search_catalogue').
        session: filter to a specific MCP session UUID.
        limit / offset: pagination (default: 100 most recent).

        Returns a paginated list of action log entries ordered by timestamp
        descending, each including tool_name, tool_args, result_status,
        result_summary, affected_paths, session_id, and day.
        """
        params: dict = {"limit": limit, "offset": offset}
        if day:
            params["day"] = day
        if tool:
            params["tool"] = tool
        if session:
            params["session"] = session
        try:
            resp = await api.get("/api/mcp-log", params=params)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps(
                {"error": str(exc), "suggestion": "Check that the Shell is running."}
            )

    @mcp.tool()
    async def get_daily_summary(days: int = 7) -> str:
        """Return daily aggregates of MCP tool usage for the last N days.

        days: how many calendar days to include (default 7, max 365).

        Returns a list of daily summary objects, each with:
          - day (YYYY-MM-DD)
          - total_actions: total invocations that day
          - by_tool: dict mapping tool name to invocation count
          - errors: number of invocations that raised an exception

        Use this to understand recent AI agent activity patterns.
        """
        try:
            resp = await api.get("/api/mcp-log/summary", params={"days": days})
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps(
                {"error": str(exc), "suggestion": "Check that the Shell is running."}
            )
