"""CLI command: makestack mcp — run the MCP server over stdio.

Usage:
    makestack mcp

Starts the MCP server on stdin/stdout for direct process-level integration
with Claude Code and other local AI tools.

Configure via environment variables:
    MAKESTACK_SHELL_URL    Shell base URL (default: http://localhost:3000)
    MAKESTACK_SHELL_TOKEN  Bearer token if Shell auth is enabled (default: empty)
"""

import asyncio
import sys


def run() -> None:
    """Entry point for `makestack mcp`."""
    # Validate that the mcp package is available before doing anything.
    try:
        from mcp_server.__main__ import main
    except ImportError as exc:
        print(f"Error: Could not import mcp_server — {exc}", file=sys.stderr)
        print("Run: pip install mcp>=1.0.0", file=sys.stderr)
        sys.exit(1)

    asyncio.run(main())


if __name__ == "__main__":
    run()
