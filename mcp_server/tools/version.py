"""MCP tools for version history and diff operations."""

import json

import httpx
from mcp.server.fastmcp import FastMCP


def register_tools(mcp: FastMCP, api: httpx.AsyncClient) -> None:
    """Register all version history tools on the given FastMCP instance."""

    @mcp.tool()
    async def get_primitive_history(
        path: str,
        limit: int = 20,
        offset: int = 0,
    ) -> str:
        """Get the version history of a primitive — every change ever made, newest first.

        path: full primitive path, e.g. techniques/saddle-stitching/manifest.json.
        Returns a paginated list of commit objects with hash, message, author, and timestamp.
        Use the hash values with get_primitive to read the primitive at a specific version,
        or with compare_versions to see what changed between versions.
        """
        try:
            resp = await api.get(
                f"/api/version/{path}/history",
                params={"limit": limit, "offset": offset},
            )
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def compare_versions(
        path: str,
        from_hash: str | None = None,
        to_hash: str | None = None,
    ) -> str:
        """Compare two versions of a primitive. Returns a structured field-level diff.

        path: full primitive path, e.g. techniques/saddle-stitching/manifest.json.
        from_hash: starting commit hash. If omitted, defaults to the parent of to_hash.
        to_hash: ending commit hash. If omitted, defaults to the current HEAD version.

        The diff shows which fields changed, were added, or were removed, using dot notation
        for nested fields (properties.tension) and bracket notation for arrays (steps[3]).
        Use get_primitive_history to browse available commit hashes.
        """
        params: dict = {}
        if from_hash is not None:
            params["from"] = from_hash
        if to_hash is not None:
            params["to"] = to_hash
        try:
            resp = await api.get(f"/api/version/{path}/diff", params=params)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def get_primitive_at_version(path: str, commit_hash: str) -> str:
        """Read a primitive as it existed at a specific point in time.

        Use this to see what a technique or material looked like when a project was created,
        or to review what a primitive contained before a change was made.

        path: full primitive path, e.g. materials/wickett-craig-5oz/manifest.json.
        commit_hash: the exact commit hash from get_primitive_history.
        Returns the full manifest as it was at that commit.
        """
        try:
            resp = await api.get(f"/api/catalogue/primitives/{path}", params={"at": commit_hash})
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})
