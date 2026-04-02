"""MCP tools for catalogue operations — proxied through the Shell REST API."""

import json

import httpx
from mcp.server.fastmcp import FastMCP


def register_tools(mcp: FastMCP, api: httpx.AsyncClient) -> None:
    """Register all catalogue tools on the given FastMCP instance."""

    @mcp.tool()
    async def search_catalogue(query: str, type_filter: str | None = None) -> str:
        """Search the catalogue for techniques, materials, tools, workflows, projects, or events.

        Returns a paginated list of matching primitives with name, type, path, and description.
        Use get_primitive to fetch the full manifest of a specific result.

        type_filter must be one of: tool, material, technique, workflow, project, event.
        """
        params: dict = {"q": query}
        if type_filter:
            params["type_filter"] = type_filter
        try:
            resp = await api.get("/api/catalogue/search", params=params)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def list_primitives(
        type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> str:
        """List all primitives in the catalogue, optionally filtered by type.

        type must be one of: tool, material, technique, workflow, project, event.
        Returns a paginated list. Use offset/limit to page through large catalogues.
        Use get_primitive to fetch the full manifest of a specific result.
        """
        params: dict = {"limit": limit, "offset": offset}
        if type:
            params["type"] = type
        try:
            resp = await api.get("/api/catalogue/primitives", params=params)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def get_primitive(path: str, version: str | None = None) -> str:
        """Get a single primitive by its catalogue path. Returns the full manifest with all fields.

        path format: {type}s/{slug}/manifest.json — for example tools/stitching-chisel/manifest.json.
        version: optional commit hash for a historical read. Omit to get the current version.

        Use get_primitive_history to list available historical versions.
        """
        params = {}
        if version:
            params["at"] = version
        try:
            resp = await api.get(f"/api/catalogue/primitives/{path}", params=params)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def create_primitive(
        type: str,
        name: str,
        description: str | None = None,
        tags: list[str] | None = None,
        steps: list | None = None,
        properties: dict | None = None,
        relationships: list[dict] | None = None,
        parent_project: str | None = None,
    ) -> str:
        """Create a new primitive in the catalogue.

        type must be one of: tool, material, technique, workflow, project, event.
        steps: ordered list of step objects — used for technique and workflow types.
        relationships: list of {type, target} objects linking this primitive to others.
        parent_project: for project type — path to the parent project.

        Returns the created primitive with auto-generated id, slug, created, and modified.
        """
        body: dict = {"type": type, "name": name}
        if description is not None:
            body["description"] = description
        if tags is not None:
            body["tags"] = tags
        if steps is not None:
            body["steps"] = steps
        if properties is not None:
            body["properties"] = properties
        if relationships is not None:
            body["relationships"] = relationships
        if parent_project is not None:
            body["parent_project"] = parent_project
        try:
            resp = await api.post("/api/catalogue/primitives", json=body)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def update_primitive(
        path: str,
        id: str,
        type: str,
        name: str,
        slug: str,
        description: str | None = None,
        tags: list[str] | None = None,
        steps: list | None = None,
        properties: dict | None = None,
        relationships: list[dict] | None = None,
        parent_project: str | None = None,
    ) -> str:
        """Update an existing primitive in the catalogue.

        path: the primitive's full path, e.g. tools/stitching-chisel/manifest.json.
        id, type, name, slug are required — use get_primitive to read these fields first.
        Only provide the fields you want to change; omitted optional fields are cleared.
        Returns the updated primitive with an auto-stamped modified timestamp.
        """
        body: dict = {"id": id, "type": type, "name": name, "slug": slug}
        if description is not None:
            body["description"] = description
        if tags is not None:
            body["tags"] = tags
        if steps is not None:
            body["steps"] = steps
        if properties is not None:
            body["properties"] = properties
        if relationships is not None:
            body["relationships"] = relationships
        if parent_project is not None:
            body["parent_project"] = parent_project
        try:
            resp = await api.put(f"/api/catalogue/primitives/{path}", json=body)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def delete_primitive(path: str) -> str:
        """Delete a primitive from the catalogue. This removes it from Git and cannot be undone.

        path: the primitive's full path, e.g. tools/stitching-chisel/manifest.json.
        Use get_primitive_history to review the history before deleting.
        Returns an empty response on success (204), or an error object.
        """
        try:
            resp = await api.delete(f"/api/catalogue/primitives/{path}")
            if resp.status_code == 204:
                return json.dumps({"success": True, "path": path})
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def get_relationships(path: str) -> str:
        """Get all relationships for a primitive — both what it connects to and what connects to it.

        path: the primitive's full path, e.g. techniques/saddle-stitching/manifest.json.
        Returns a list of relationship objects with source_path, relationship_type, and target_path.
        """
        try:
            resp = await api.get(f"/api/catalogue/relationships/{path}")
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def fork_primitive(
        path: str,
        name: str | None = None,
        description: str | None = None,
    ) -> str:
        """Fork a primitive into a new independent copy with cloned_from provenance tracking.

        The forked primitive gets a new id, a new slug ({original-slug}-fork), and fresh
        timestamps. All other fields (tags, properties, relationships, steps) are copied from
        the source. Optionally override the name and description.

        Use this to create recipe variations, project variants, or any other derivative work
        while preserving the link back to the original via the cloned_from field.

        path: source primitive path, e.g. workflows/sourdough-loaf/manifest.json.
        name: optional name for the fork (defaults to "{original name} (fork)").
        description: optional description override.

        Returns the newly created primitive with 201 status.
        """
        body: dict = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        try:
            resp = await api.post(f"/api/catalogue/primitives/{path}/fork", json=body or None)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})
