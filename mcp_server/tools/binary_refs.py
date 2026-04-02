"""MCP tools for binary file reference operations."""

import json

import httpx
from mcp.server.fastmcp import FastMCP


def register_tools(mcp: FastMCP, api: httpx.AsyncClient) -> None:
    """Register all binary-ref tools on the given FastMCP instance."""

    @mcp.tool()
    async def list_binary_refs(
        asset_type: str | None = None,
        primitive_ref: str | None = None,
    ) -> str:
        """List binary file references tracked in the catalogue.

        Binary refs are git-backed pointer records that describe binary assets
        (photos, videos, 3D models, documents, etc.) stored outside of Git.
        They record the local path, backup location, checksum, and optionally
        link to a catalogue primitive.

        asset_type: filter by type (e.g. 'photo', 'video', 'model', 'document').
        primitive_ref: filter by linked primitive path (e.g. workflows/my-recipe/manifest.json).

        Returns a list of binary ref objects.
        """
        params: dict = {}
        if asset_type:
            params["asset_type"] = asset_type
        if primitive_ref:
            params["primitive_ref"] = primitive_ref
        try:
            resp = await api.get("/api/binary-refs", params=params or None)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def get_binary_ref(slug: str) -> str:
        """Get a single binary file reference by its slug.

        Returns the full binary ref record including local path, backup location,
        sha256 checksum, and all metadata.
        """
        try:
            resp = await api.get(f"/api/binary-refs/{slug}")
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def create_binary_ref(
        filename: str,
        local_path: str | None = None,
        backup_location: str | None = None,
        asset_type: str | None = None,
        mime_type: str | None = None,
        size_bytes: int | None = None,
        sha256: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        primitive_ref: str | None = None,
    ) -> str:
        """Create a new binary file reference in the catalogue.

        Binary refs track where a file lives without storing the file in Git.
        Use this to attach photos, videos, 3D models, or documents to a project
        or recipe without LFS.

        filename: the original filename (e.g. 'project-photo.jpg').
        local_path: absolute path to the file on the local machine.
        backup_location: path or URL to the backup copy (e.g. 's3://bucket/photo.jpg' or '/mnt/nas/photo.jpg').
        asset_type: classification — 'photo', 'video', 'model', 'document', 'audio', etc.
        mime_type: MIME type (e.g. 'image/jpeg').
        size_bytes: file size in bytes.
        sha256: SHA-256 checksum for integrity verification.
        description: free-text description.
        tags: list of tags.
        primitive_ref: catalogue path of the linked primitive (e.g. 'workflows/sourdough-loaf/manifest.json').

        Returns the created binary ref with auto-generated id and slug.
        """
        body: dict = {"filename": filename}
        if local_path is not None:
            body["local_path"] = local_path
        if backup_location is not None:
            body["backup_location"] = backup_location
        if asset_type is not None:
            body["asset_type"] = asset_type
        if mime_type is not None:
            body["mime_type"] = mime_type
        if size_bytes is not None:
            body["size_bytes"] = size_bytes
        if sha256 is not None:
            body["sha256"] = sha256
        if description is not None:
            body["description"] = description
        if tags is not None:
            body["tags"] = tags
        if primitive_ref is not None:
            body["primitive_ref"] = primitive_ref
        try:
            resp = await api.post("/api/binary-refs", json=body)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def update_binary_ref(
        slug: str,
        filename: str | None = None,
        local_path: str | None = None,
        backup_location: str | None = None,
        asset_type: str | None = None,
        mime_type: str | None = None,
        size_bytes: int | None = None,
        sha256: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        primitive_ref: str | None = None,
    ) -> str:
        """Update an existing binary file reference.

        slug: the binary ref's slug (from list_binary_refs or create_binary_ref).
        Only provide the fields you want to update.

        Returns the updated binary ref.
        """
        body: dict = {}
        if filename is not None:
            body["filename"] = filename
        if local_path is not None:
            body["local_path"] = local_path
        if backup_location is not None:
            body["backup_location"] = backup_location
        if asset_type is not None:
            body["asset_type"] = asset_type
        if mime_type is not None:
            body["mime_type"] = mime_type
        if size_bytes is not None:
            body["size_bytes"] = size_bytes
        if sha256 is not None:
            body["sha256"] = sha256
        if description is not None:
            body["description"] = description
        if tags is not None:
            body["tags"] = tags
        if primitive_ref is not None:
            body["primitive_ref"] = primitive_ref
        try:
            resp = await api.put(f"/api/binary-refs/{slug}", json=body)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def delete_binary_ref(slug: str) -> str:
        """Delete a binary file reference from the catalogue.

        This only removes the pointer record — the actual binary file is NOT deleted.
        slug: the binary ref's slug.

        Returns success confirmation or an error object.
        """
        try:
            resp = await api.delete(f"/api/binary-refs/{slug}")
            if resp.status_code == 204:
                return json.dumps({"success": True, "slug": slug})
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})
