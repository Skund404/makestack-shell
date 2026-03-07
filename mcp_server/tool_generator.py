"""Generates MCP tool definitions from installed module manifests.

When modules are loaded, their manifest.json declares api_endpoints with
method, path, description, and parameter schemas. This generator reads those
declarations from the ModuleRegistry and registers MCP tool functions on the
FastMCP instance so the AI sees module operations alongside Shell tools.

Tool naming convention: {module_name}__{endpoint_slug}
  - module_name: hyphens replaced with underscores (e.g., inventory_stock)
  - endpoint_slug: HTTP method + path with slashes/braces replaced by underscores
  - Example: inventory_stock__get_stock_item_id

The generated tools delegate to call_module (the generic module passthrough)
so all auth, routing, and error handling is inherited from the Shell.
"""

import json
import re

import httpx
from mcp.server.fastmcp import FastMCP


def _make_tool_name(module_name: str, method: str, path: str) -> str:
    """Build an MCP tool name from a module endpoint declaration.

    inventory-stock  GET  /stock/{id}  →  inventory_stock__get_stock_id
    """
    snake_module = module_name.replace("-", "_")
    # Normalise path: drop leading slash, replace {param}, /, - with _
    path_slug = re.sub(r"[{}]", "", path)         # Remove brace wrappers
    path_slug = re.sub(r"[/\-]", "_", path_slug)  # Slashes and hyphens → underscores
    path_slug = re.sub(r"_+", "_", path_slug)     # Collapse consecutive underscores
    path_slug = path_slug.strip("_")
    method_slug = method.lower()
    return f"{snake_module}__{method_slug}_{path_slug}"


async def generate_module_tools(mcp: FastMCP, module_registry) -> int:
    """Register MCP tools for all loaded modules.

    Reads the ModuleRegistry and creates one MCP tool per declared api_endpoint.
    Each tool calls back through the Shell's /modules/{name}/ routing layer.

    Returns the number of tools registered.
    """
    endpoints = module_registry.get_all_endpoints()
    if not endpoints:
        return 0

    registered = 0

    # We need an httpx client to call the Shell for call_module delegation.
    # This client is created locally; in tests it is the ASGI transport client.
    import os
    shell_url = os.getenv("MAKESTACK_SHELL_URL", "http://localhost:3000")
    api = httpx.AsyncClient(base_url=shell_url, timeout=30.0)

    for ep in endpoints:
        module_name: str = ep["module_name"]
        display_name: str = ep["module_display_name"]
        method: str = ep["method"]
        path: str = ep["path"]
        description: str = ep["description"]
        parameters: dict | None = ep.get("parameters")

        tool_name = _make_tool_name(module_name, method, path)

        # Build the tool function dynamically.
        # We capture variables via default arguments to avoid closure issues.
        def _make_handler(mn: str, m: str, p: str, desc: str):
            async def _handler(**kwargs) -> str:
                f"""[{mn}] {desc}

                Invokes {m} /modules/{mn}/{p.lstrip('/')} on the Shell.
                """
                body = kwargs if m.upper() in ("POST", "PUT") else None
                params = kwargs if m.upper() == "GET" else None
                url = f"/modules/{mn}/{p.lstrip('/')}"
                try:
                    if m.upper() == "GET":
                        resp = await api.get(url, params=params)
                    elif m.upper() == "POST":
                        resp = await api.post(url, json=body)
                    elif m.upper() == "PUT":
                        resp = await api.put(url, json=body)
                    elif m.upper() == "DELETE":
                        resp = await api.delete(url)
                    else:
                        return json.dumps({"error": f"Unsupported method: {m}"})
                    return json.dumps(resp.json(), indent=2)
                except Exception as exc:
                    return json.dumps({
                        "error": str(exc),
                        "suggestion": f"Check that module '{mn}' is enabled and the Shell is running.",
                    })
            return _handler

        handler = _make_handler(module_name, method, path, description)
        handler.__name__ = tool_name
        handler.__doc__ = f"[{display_name}] {description}\n\nMethod: {method}  Path: /modules/{module_name}/{path.lstrip('/')}"

        # Use the input schema from the manifest if provided.
        tool_kwargs: dict = {
            "name": tool_name,
            "description": f"[{display_name}] {description}",
        }

        # Register on the FastMCP instance.
        try:
            mcp.add_tool(handler, **tool_kwargs)
            registered += 1
        except Exception as exc:
            # Log but don't crash — other tools can still work.
            import structlog
            structlog.get_logger().bind(component="tool_generator").warning(
                "mcp_tool_register_failed",
                tool=tool_name,
                error=str(exc),
            )

    return registered
