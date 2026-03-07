"""MCP tools for module management and package/registry operations."""

import json

import httpx
from mcp.server.fastmcp import FastMCP


def register_tools(mcp: FastMCP, api: httpx.AsyncClient) -> None:
    """Register all module and package management tools on the given FastMCP instance."""

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

    # --- Package management tools -----------------------------------------

    @mcp.tool()
    async def list_packages() -> str:
        """List all installed packages across all types (modules, widget-packs, catalogues, data).

        Use this to see what is currently installed before deciding to install or uninstall.
        """
        try:
            resp = await api.get("/api/packages")
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def install_package(
        name: str | None = None,
        source: str | None = None,
        version: str | None = None,
    ) -> str:
        """Install a Makestack package.

        Provide either:
          name   — package name resolved via configured registries (e.g. 'inventory-stock')
          source — a direct Git URL (https://...) or local directory path

        version is optional; omitting it installs the latest semver tag.

        Package types: module (requires restart), widget-pack, catalogue, data.
        """
        payload: dict = {}
        if name:
            payload["name"] = name
        if source:
            payload["source"] = source
        if version:
            payload["version"] = version

        try:
            resp = await api.post("/api/packages/install", json=payload)
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def uninstall_package(name: str) -> str:
        """Uninstall an installed package.

        name: the package's registered name (use list_packages to see installed packages).

        For modules: the module is disabled and its DB tables are preserved.
        For other types: the registration is removed.
        """
        try:
            resp = await api.delete(f"/api/packages/{name}")
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def search_packages(query: str) -> str:
        """Search for packages across all configured registries.

        query: search term matched against package names and descriptions.

        Returns matching packages with their type, description, and Git URL.
        Use install_package with the 'name' field to install a result.
        """
        try:
            resp = await api.get("/api/packages/search", params={"q": query})
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})

    @mcp.tool()
    async def list_registries() -> str:
        """List all configured package registries with their package counts.

        Registries are Git repos containing an index.json that maps package names
        to Git URLs. Use add_registry to add new ones.
        """
        try:
            resp = await api.get("/api/registries")
            return json.dumps(resp.json(), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc), "suggestion": "Check that the Shell is running."})
