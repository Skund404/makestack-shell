"""MCP tools for personal inventory management."""

import json

import httpx
from mcp.server.fastmcp import FastMCP


def register_tools(mcp: FastMCP, api: httpx.AsyncClient) -> None:
    """Register all inventory tools on the given FastMCP instance."""

    @mcp.tool()
    async def add_to_inventory(
        catalogue_path: str,
        workshop_id: str | None = None,
    ) -> str:
        """Add a catalogue item to your personal inventory.

        Creates an immutable hash-pointer reference to the current version of the
        catalogue entry. Use check_inventory_updates later to see if the catalogue
        has been updated since you added this item.

        catalogue_path: full path to the primitive, e.g. tools/stitching-chisel/manifest.json.
        workshop_id: optional — assign to a specific workshop immediately.
        Returns the created inventory item with its id and pinned catalogue hash.
        """
        body: dict = {"catalogue_path": catalogue_path}
        if workshop_id is not None:
            body["workshop_id"] = workshop_id
        try:
            resp = await api.post("/api/inventory", json=body)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def list_inventory(
        workshop_id: str | None = None,
        type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> str:
        """List items in your personal inventory.

        Optionally filter by workshop or primitive type.
        type must be one of: tool, material, technique, workflow, project, event.
        Returns inventory items with their pinned catalogue hash and workshop assignment.
        Use get_inventory_item to fetch the full item with resolved catalogue data.
        """
        params: dict = {"limit": limit, "offset": offset}
        if workshop_id is not None:
            params["workshop_id"] = workshop_id
        if type is not None:
            params["type"] = type
        try:
            resp = await api.get("/api/inventory", params=params)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def get_inventory_item(id: str) -> str:
        """Get a single inventory item with its resolved catalogue data and staleness status.

        Returns the inventory record merged with the catalogue entry as it was at the
        pinned hash. The is_stale field indicates whether the catalogue has since been
        updated. Use compare_versions to see what changed.
        """
        try:
            resp = await api.get(f"/api/inventory/{id}")
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def check_inventory_updates() -> str:
        """List inventory items where the catalogue entry has been updated since the item was added.

        These items have newer versions available. For each stale item, the response
        includes the current_hash you can update to. Use compare_versions to review
        what changed before calling update_inventory_pointer.
        """
        try:
            resp = await api.get("/api/inventory/stale")
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def update_inventory_pointer(
        id: str,
        catalogue_hash: str | None = None,
        workshop_id: str | None = None,
    ) -> str:
        """Update an inventory item's pinned version or workshop assignment.

        catalogue_hash: pin to a specific commit hash. Use the current_hash from
        check_inventory_updates to update to the latest version. Omit to leave unchanged.
        workshop_id: reassign to a different workshop, or pass empty string to unassign.

        Use get_primitive_history to browse available commit hashes.
        """
        body: dict = {}
        if catalogue_hash is not None:
            body["catalogue_hash"] = catalogue_hash
        if workshop_id is not None:
            body["workshop_id"] = workshop_id
        try:
            resp = await api.put(f"/api/inventory/{id}", json=body)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def remove_from_inventory(id: str) -> str:
        """Remove an item from your personal inventory.

        This removes the inventory record only — the catalogue entry is unaffected.
        Use list_inventory to find the id of the item to remove.
        Returns success confirmation or an error if the item was not found.
        """
        try:
            resp = await api.delete(f"/api/inventory/{id}")
            if resp.status_code == 204:
                return json.dumps({"success": True, "id": id})
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})
