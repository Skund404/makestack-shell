"""MCP tools for workshop management."""

import json

import httpx
from mcp.server.fastmcp import FastMCP


def register_tools(mcp: FastMCP, api: httpx.AsyncClient) -> None:
    """Register all workshop tools on the given FastMCP instance."""

    @mcp.tool()
    async def list_workshops(limit: int = 50, offset: int = 0) -> str:
        """List all workshops ordered by sort order then name.

        Workshops are schema-free organisational containers — you decide what they mean.
        Use get_workshop to see the full member list for a specific workshop.
        """
        try:
            resp = await api.get("/api/workshops", params={"limit": limit, "offset": offset})
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def get_workshop(id: str) -> str:
        """Get a single workshop with its full list of primitive members.

        Returns the workshop metadata plus every primitive path assigned to it.
        """
        try:
            resp = await api.get(f"/api/workshops/{id}")
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def create_workshop(
        name: str,
        description: str | None = None,
        icon: str | None = None,
        color: str | None = None,
    ) -> str:
        """Create a new workshop. A slug is auto-generated from the name.

        Workshops are schema-free — you can use them for domain scope (Leatherwork),
        time scope (2024 Projects), project scope (Messenger Bag Build), or anything else.
        Returns the created workshop with its auto-generated id and slug.
        """
        body: dict = {"name": name}
        if description is not None:
            body["description"] = description
        if icon is not None:
            body["icon"] = icon
        if color is not None:
            body["color"] = color
        try:
            resp = await api.post("/api/workshops", json=body)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def update_workshop(
        id: str,
        name: str | None = None,
        description: str | None = None,
        icon: str | None = None,
        color: str | None = None,
        sort_order: int | None = None,
    ) -> str:
        """Update workshop metadata. Only provided fields are changed.

        Returns the updated workshop.
        """
        body: dict = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if icon is not None:
            body["icon"] = icon
        if color is not None:
            body["color"] = color
        if sort_order is not None:
            body["sort_order"] = sort_order
        try:
            resp = await api.put(f"/api/workshops/{id}", json=body)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def delete_workshop(id: str) -> str:
        """Delete a workshop. All member assignments are removed; primitives are unaffected.

        Use list_workshops to find the workshop id.
        Returns success confirmation or an error if the workshop was not found.
        """
        try:
            resp = await api.delete(f"/api/workshops/{id}")
            if resp.status_code == 204:
                return json.dumps({"success": True, "id": id})
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def add_to_workshop(
        workshop_id: str,
        primitive_path: str,
        primitive_type: str,
    ) -> str:
        """Add a catalogue primitive to a workshop. This creates a reference, not a copy.

        Idempotent — if the primitive is already a member, returns the existing record.
        primitive_path: full path, e.g. tools/stitching-chisel/manifest.json.
        primitive_type: one of tool, material, technique, workflow, project, event.
        A primitive can belong to multiple workshops simultaneously.
        """
        body = {"primitive_path": primitive_path, "primitive_type": primitive_type}
        try:
            resp = await api.post(f"/api/workshops/{workshop_id}/members", json=body)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def remove_from_workshop(workshop_id: str, primitive_path: str) -> str:
        """Remove a primitive reference from a workshop. The primitive still exists in the catalogue.

        primitive_path: full path, e.g. tools/stitching-chisel/manifest.json.
        Use get_workshop to see the current member list before removing.
        Returns success confirmation or an error if the member was not found.
        """
        try:
            resp = await api.delete(f"/api/workshops/{workshop_id}/members/{primitive_path}")
            if resp.status_code == 204:
                return json.dumps({"success": True, "workshop_id": workshop_id, "primitive_path": primitive_path})
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def set_active_workshop(workshop_id: str | None = None) -> str:
        """Set the active workshop context. Pass null/empty to clear the active context.

        The active workshop filters what you see in list views. Use list_workshops
        to find the workshop id. Changes take effect immediately.
        Returns the new active_workshop_id.
        """
        body: dict = {"workshop_id": workshop_id}
        try:
            resp = await api.put("/api/workshops/active", json=body)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})
