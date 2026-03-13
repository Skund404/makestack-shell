"""MCP Action Log routes — persistent audit log for every MCP tool invocation.

All routes are always available (not dev-mode gated) — the log is core
infrastructure, not a debug aid.

Endpoints:
    POST /api/mcp-log            Append a new log entry (called by MCP server layer)
    GET  /api/mcp-log            Query entries (day, tool, session, limit, offset)
    GET  /api/mcp-log/summary    Daily aggregates (days param)
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..dependencies import get_userdb
from ..userdb import UserDB

log = structlog.get_logger().bind(component="mcp_log_router")

router = APIRouter(prefix="/api/mcp-log", tags=["mcp-log"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class McpLogEntry(BaseModel):
    """Inbound log entry posted by the MCP server wrapper."""

    id: str | None = None
    timestamp: str | None = None
    tool_name: str
    tool_args: dict = {}
    result_status: str  # 'success' | 'error'
    result_summary: str | None = None
    affected_paths: list[str] = []
    session_id: str | None = None


class McpLogRecord(BaseModel):
    """A fully-hydrated log record returned from queries."""

    id: str
    timestamp: str
    tool_name: str
    tool_args: dict
    result_status: str
    result_summary: str | None
    affected_paths: list[str]
    session_id: str | None
    day: str


class McpLogSummaryDay(BaseModel):
    """Daily aggregate returned by the summary endpoint."""

    day: str
    total_actions: int
    by_tool: dict[str, int]
    errors: int


def _row_to_record(row: dict) -> McpLogRecord:
    return McpLogRecord(
        id=row["id"],
        timestamp=row["timestamp"],
        tool_name=row["tool_name"],
        tool_args=json.loads(row["tool_args"]),
        result_status=row["result_status"],
        result_summary=row["result_summary"],
        affected_paths=json.loads(row["affected_paths"]),
        session_id=row["session_id"],
        day=row["day"],
    )


# ---------------------------------------------------------------------------
# Endpoints — /summary must be declared before the root GET to avoid any
# potential prefix-match ambiguity in FastAPI's router ordering.
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=list[McpLogSummaryDay])
async def get_summary(
    days: int = Query(default=7, ge=1, le=365),
    db: UserDB = Depends(get_userdb),
) -> list[McpLogSummaryDay]:
    """Return daily action aggregates for the last N days.

    Each entry contains total_actions, per-tool counts (by_tool), and error
    count for that calendar day. Days with zero actions are omitted.
    """
    today = datetime.now(timezone.utc).date()
    start_day = (today - timedelta(days=days - 1)).isoformat()

    rows = await db.fetch_all(
        "SELECT day, tool_name, result_status, COUNT(*) as cnt "
        "FROM mcp_action_log WHERE day >= ? "
        "GROUP BY day, tool_name, result_status "
        "ORDER BY day DESC",
        [start_day],
    )

    # Aggregate rows into per-day buckets.
    by_day: dict[str, dict] = {}
    for row in rows:
        d = row["day"]
        if d not in by_day:
            by_day[d] = {"total": 0, "by_tool": {}, "errors": 0}
        cnt = row["cnt"]
        by_day[d]["total"] += cnt
        by_day[d]["by_tool"][row["tool_name"]] = (
            by_day[d]["by_tool"].get(row["tool_name"], 0) + cnt
        )
        if row["result_status"] == "error":
            by_day[d]["errors"] += cnt

    return [
        McpLogSummaryDay(
            day=d,
            total_actions=v["total"],
            by_tool=v["by_tool"],
            errors=v["errors"],
        )
        for d, v in sorted(by_day.items(), reverse=True)
    ]


@router.get("", response_model=dict)
async def query_log(
    day: str | None = Query(default=None, description="Filter by YYYY-MM-DD"),
    tool: str | None = Query(default=None, description="Filter by tool_name"),
    session: str | None = Query(default=None, description="Filter by session_id"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: UserDB = Depends(get_userdb),
) -> dict:
    """Query the MCP action log with optional filters.

    Returns results ordered by timestamp descending (most recent first).
    """
    where: list[str] = []
    params: list = []

    if day:
        where.append("day = ?")
        params.append(day)
    if tool:
        where.append("tool_name = ?")
        params.append(tool)
    if session:
        where.append("session_id = ?")
        params.append(session)

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    count_row = await db.fetch_one(
        f"SELECT COUNT(*) as total FROM mcp_action_log {where_clause}",
        params,
    )
    total = count_row["total"] if count_row else 0

    rows = await db.fetch_all(
        f"SELECT * FROM mcp_action_log {where_clause} "
        f"ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    )

    return {
        "items": [_row_to_record(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("", status_code=201, response_model=McpLogRecord)
async def append_log_entry(
    entry: McpLogEntry,
    db: UserDB = Depends(get_userdb),
) -> McpLogRecord:
    """Append an MCP tool invocation to the audit log.

    Called by the MCP server wrapper after every tool call (success or failure).
    The log is append-only — entries are never updated or deleted.
    """
    now = datetime.now(timezone.utc)
    entry_id = entry.id or str(uuid.uuid4())
    timestamp = entry.timestamp or now.isoformat()
    day = timestamp[:10]  # YYYY-MM-DD

    row = await db.execute_returning(
        """
        INSERT INTO mcp_action_log
            (id, timestamp, tool_name, tool_args, result_status,
             result_summary, affected_paths, session_id, day)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING *
        """,
        [
            entry_id,
            timestamp,
            entry.tool_name,
            json.dumps(entry.tool_args),
            entry.result_status,
            entry.result_summary,
            json.dumps(entry.affected_paths),
            entry.session_id,
            day,
        ],
    )
    log.info(
        "mcp_action_logged",
        tool=entry.tool_name,
        status=entry.result_status,
        session=entry.session_id,
    )
    return _row_to_record(row)
