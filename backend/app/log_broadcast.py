"""Log broadcaster — asyncio.Queue-based fan-out for structured log events.

LogBroadcaster is a module-level singleton that SSE subscribers attach to.
BroadcastLogProcessor is a structlog processor that feeds it — wired into
_configure_logging() in main.py so every structlog event is broadcast.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Broadcaster
# ---------------------------------------------------------------------------


class LogBroadcaster:
    """Fan-out broadcast of structured log events to all active SSE subscribers.

    Each subscriber gets its own asyncio.Queue (max 500 entries). Slow
    subscribers drop events rather than blocking the logging pipeline.
    """

    MAX_QUEUE_SIZE = 500

    def __init__(self) -> None:
        self._queues: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        """Register a new subscriber and return its queue."""
        q: asyncio.Queue = asyncio.Queue(maxsize=self.MAX_QUEUE_SIZE)
        self._queues.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove a subscriber queue. Safe to call even if already removed."""
        try:
            self._queues.remove(q)
        except ValueError:
            pass

    def broadcast(self, event: dict) -> None:
        """Push event to all subscriber queues. Drops for slow subscribers."""
        for q in self._queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Slow subscriber — drop rather than block


# ---------------------------------------------------------------------------
# structlog processor
# ---------------------------------------------------------------------------


class BroadcastLogProcessor:
    """structlog processor that fans log events to SSE subscribers.

    Insert this into the processor chain BEFORE the final renderer so it
    receives the fully-annotated event dict (with timestamp and level).
    Returns event_dict unchanged so the chain continues normally.
    """

    # Fields already promoted to top-level in LogEntry; rest are extras.
    _TOP_LEVEL = frozenset({"timestamp", "level", "component", "event"})

    def __call__(self, logger: Any, method: str, event_dict: dict) -> dict:
        entry: dict[str, Any] = {
            "type": "log",
            "timestamp": event_dict.get(
                "timestamp", datetime.now(timezone.utc).isoformat()
            ),
            "level": event_dict.get("level", method),
            "component": event_dict.get("component", ""),
            "event": event_dict.get("event", ""),
        }
        # Carry extra fields through, coercing non-serialisable values to str.
        for k, v in event_dict.items():
            if k in self._TOP_LEVEL:
                continue
            if isinstance(v, (str, int, float, bool, type(None))):
                entry[k] = v
            else:
                try:
                    entry[k] = str(v)
                except Exception:
                    pass

        get_broadcaster().broadcast(entry)
        return event_dict  # Must pass through unchanged


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_broadcaster: LogBroadcaster | None = None


def get_broadcaster() -> LogBroadcaster:
    """Return the module-level LogBroadcaster singleton (created on first call)."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = LogBroadcaster()
    return _broadcaster
