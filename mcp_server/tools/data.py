"""MCP tools for exporting and importing personal UserDB data."""

import json

import httpx
from mcp.server.fastmcp import FastMCP


def register_tools(mcp: FastMCP, api: httpx.AsyncClient) -> None:
    """Register export/import tools on the given FastMCP instance."""

    @mcp.tool()
    async def export_data(
        only: str | None = None,
    ) -> str:
        """Export personal data (inventory, workshops, preferences) as portable JSON.

        Returns a complete export document that can be re-imported with import_data.
        Catalogue data is not exported — it lives in the Git-based catalogue.

        only: optional section to export — workshops, inventory, preferences, or module:<name>.
              If omitted, all sections are exported.

        Returns the export document as a JSON string.
        """
        params: dict = {}
        if only is not None:
            params["only"] = only
        try:
            resp = await api.get("/api/data/export", params=params)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def import_data(
        data: dict,
        only: str | None = None,
        strategy: str = "additive",
    ) -> str:
        """Import personal data from an export document.

        data: the export document produced by export_data (must contain a 'sections' key).
        only: optional section to import — workshops, inventory, or preferences.
        strategy: conflict resolution —
            additive (default): add new items, skip existing.
            overwrite: add new items, replace existing.
            skip_conflicts: same as additive.

        Returns an import summary with counts of imported, skipped, and replaced items.
        """
        params: dict = {"strategy": strategy}
        if only is not None:
            params["only"] = only
        try:
            resp = await api.post("/api/data/import", json={"data": data}, params=params)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})
