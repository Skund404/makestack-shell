"""Generates MCP tool definitions from installed module manifests.

When modules are installed, their manifest.json declares api_endpoints with
method, path, description, and parameter schemas. This generator reads those
declarations and creates MCP Tool objects so the AI sees module operations
alongside Shell tools — no distinction needed.

Tool naming convention: {module_name}__{endpoint_name}
Example: inventory_stock__get_stock

Not implemented until Phase 5 (Module System).
"""

import httpx
from mcp.server.fastmcp import FastMCP


async def generate_module_tools(mcp: FastMCP, api: httpx.AsyncClient) -> int:
    """Fetch installed modules and register MCP tools from their manifests.

    Returns the number of module tools registered.

    Phase 5: For each enabled module, read its manifest's api_endpoints,
    generate tool functions with inputSchema from the endpoint's declared
    parameters, and register them on the mcp instance using the
    {module_name}__{endpoint_name} naming convention.
    """
    # Not yet implemented — module loader is built in Phase 5.
    return 0
