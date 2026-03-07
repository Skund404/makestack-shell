"""MCP tools for module management.

Module tool auto-generation from manifests is implemented in tool_generator.py
and wired in during Phase 5 when the module loader is built.
"""

import json

import httpx
from mcp.server.fastmcp import FastMCP


def register_tools(mcp: FastMCP, api: httpx.AsyncClient) -> None:
    """Register all module management tools on the given FastMCP instance."""

    @mcp.tool()
    async def list_modules() -> str:
        """List all installed modules with their status (enabled/disabled) and version.

        Returns an empty list until Phase 5 (Module System) is implemented.
        Module-specific tools are auto-generated from manifests and appear alongside
        these management tools once modules are installed.
        """
        try:
            resp = await api.get("/api/modules")
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def enable_module(name: str) -> str:
        """Enable an installed module. The module's routes and keyword renderers become active.

        name: the module's registered name (use list_modules to see available modules).
        A Shell restart is required for route changes to take full effect.
        """
        try:
            resp = await api.put(f"/api/modules/{name}/enable")
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def disable_module(name: str) -> str:
        """Disable an installed module. The module's routes and keyword renderers are deactivated.

        name: the module's registered name (use list_modules to see available modules).
        A Shell restart is required for route changes to take full effect.
        """
        try:
            resp = await api.put(f"/api/modules/{name}/disable")
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def call_module(
        module_name: str,
        method: str,
        path: str,
        body: dict | None = None,
    ) -> str:
        """Invoke a module's API endpoint. This is a generic passthrough for any module operation.

        module_name: the module's registered name.
        method: HTTP method — GET, POST, PUT, or DELETE.
        path: relative path within the module's mount point (without the /modules/{name}/ prefix).
        body: optional request body for POST/PUT methods.

        Module endpoints are mounted at /modules/{module_name}/{path}.
        Use list_modules to see installed modules. Module manifests declare their endpoints.
        """
        url = f"/modules/{module_name}/{path.lstrip('/')}"
        method_upper = method.upper()
        try:
            if method_upper == "GET":
                resp = await api.get(url)
            elif method_upper == "POST":
                resp = await api.post(url, json=body)
            elif method_upper == "PUT":
                resp = await api.put(url, json=body)
            elif method_upper == "DELETE":
                resp = await api.delete(url)
            else:
                return json.dumps({"error": f"Unsupported method: {method}", "suggestion": "Use GET, POST, PUT, or DELETE."})
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running and the module is enabled."})
