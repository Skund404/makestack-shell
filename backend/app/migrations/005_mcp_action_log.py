"""Migration 005 — create mcp_action_log table.

Persistent audit log for every MCP tool invocation. Append-only —
rows are never updated or deleted after insertion.
"""

ID = "005_mcp_action_log"


async def up(conn) -> None:
    """Create mcp_action_log table and its indexes."""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mcp_action_log (
            id              TEXT NOT NULL PRIMARY KEY,
            timestamp       TEXT NOT NULL,
            tool_name       TEXT NOT NULL,
            tool_args       TEXT NOT NULL DEFAULT '{}',
            result_status   TEXT NOT NULL,
            result_summary  TEXT,
            affected_paths  TEXT NOT NULL DEFAULT '[]',
            session_id      TEXT,
            day             TEXT NOT NULL
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mcp_log_day  ON mcp_action_log (day)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mcp_log_tool ON mcp_action_log (tool_name)"
    )
    await conn.commit()
