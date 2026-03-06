"""CatalogueClient — async httpx wrapper for every Core (makestack-core) endpoint.

All access to the Core catalogue engine goes through this class.
The Shell is the sole client of Core; no router or module talks to Core directly.
"""

import time
from typing import Any

import httpx
import structlog

from .models import (
    DiffResponse,
    FieldChange,
    CommitInfo,
    HistoryResponse,
    Primitive,
    PrimitiveCreate,
    PrimitiveUpdate,
    Relationship,
)

log = structlog.get_logger().bind(component="core_client")


# ---------------------------------------------------------------------------
# Typed exceptions — routes catch these and return appropriate HTTP errors
# ---------------------------------------------------------------------------


class CoreUnavailableError(Exception):
    """Core is unreachable or returned a 5xx error."""

    def __init__(self, url: str, cause: Exception | None = None) -> None:
        self.url = url
        self.cause = cause
        super().__init__(f"Core unavailable at {url}: {cause}")


class CoreNotFoundError(Exception):
    """Core returned 404 for the requested resource."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Not found in catalogue: {path}")


class CoreValidationError(Exception):
    """Core returned 400 — invalid request body."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Catalogue validation error: {message}")


# ---------------------------------------------------------------------------
# CatalogueClient
# ---------------------------------------------------------------------------


class CatalogueClient:
    """Async client wrapping every Core REST endpoint.

    Accepts an optional pre-built httpx.AsyncClient for testing (dependency injection).
    In production, a client is created from base_url and api_key.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8420",
        api_key: str = "",
        client: httpx.AsyncClient | None = None,
        dev_mode: bool = False,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._dev_mode = dev_mode
        self._connected = False

        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self._client = client or httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=httpx.Timeout(10.0),
        )

    @property
    def connected(self) -> bool:
        """Whether the last health check succeeded."""
        return self._connected

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Internal request helper
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        timeout: float = 10.0,
    ) -> Any:
        """Execute a Core API request and return parsed JSON.

        Logs every request in dev mode; logs only errors and slow calls (>500 ms)
        in production.
        """
        start = time.monotonic()
        url = f"/api/{path.lstrip('/')}" if not path.startswith("/") else path
        try:
            resp = await self._client.request(
                method,
                url,
                params=params,
                json=json,
                timeout=timeout,
            )
        except httpx.ConnectError as exc:
            log.error("core_connect_error", url=url, error=str(exc))
            raise CoreUnavailableError(self._base_url, exc) from exc
        except httpx.TimeoutException as exc:
            log.error("core_timeout", url=url, error=str(exc))
            raise CoreUnavailableError(self._base_url, exc) from exc
        except httpx.HTTPError as exc:
            log.error("core_http_error", url=url, error=str(exc))
            raise CoreUnavailableError(self._base_url, exc) from exc

        elapsed_ms = (time.monotonic() - start) * 1000

        if self._dev_mode:
            log.debug(
                "core_request",
                method=method,
                url=url,
                status=resp.status_code,
                elapsed_ms=round(elapsed_ms, 1),
            )
        elif resp.status_code >= 400 or elapsed_ms > 500:
            log.warning(
                "core_request_notable",
                method=method,
                url=url,
                status=resp.status_code,
                elapsed_ms=round(elapsed_ms, 1),
            )

        if resp.status_code == 404:
            raise CoreNotFoundError(path)
        if resp.status_code == 400:
            body = resp.json() if resp.content else {}
            raise CoreValidationError(body.get("error", resp.text))
        if resp.status_code >= 500:
            raise CoreUnavailableError(self._base_url)
        if resp.status_code == 204:
            return None

        return resp.json()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Ping Core's health endpoint. Updates and returns connection state."""
        try:
            await self._client.get("/health", timeout=5.0)
            self._connected = True
        except Exception:
            self._connected = False
        return self._connected

    # ------------------------------------------------------------------
    # Primitive CRUD
    # ------------------------------------------------------------------

    async def list_primitives(self, type_filter: str | None = None) -> list[Primitive]:
        """List all primitives, optionally filtered by type."""
        params = {"type": type_filter} if type_filter else None
        data = await self._request("GET", "primitives", params=params)
        return [Primitive(**item) for item in (data or [])]

    async def get_primitive(self, path: str) -> Primitive:
        """Get a primitive at its current version (from the SQLite index)."""
        data = await self._request("GET", f"primitives/{path}")
        return Primitive(**data)

    async def get_primitive_at_version(self, path: str, commit_hash: str) -> Primitive:
        """Get a primitive as it was at a specific Git commit."""
        data = await self._request("GET", f"primitives/{path}", params={"at": commit_hash})
        return Primitive(**data)

    async def get_commit_hash(self, path: str) -> str:
        """Get the last commit hash that touched this specific primitive path."""
        data = await self._request("GET", f"primitives/{path}/hash")
        # Core returns {"hash": "abc123"} or similar
        if isinstance(data, dict):
            return data.get("hash", data.get("commit_hash", ""))
        return str(data)

    async def get_history(
        self,
        path: str,
        limit: int = 50,
        offset: int = 0,
    ) -> HistoryResponse:
        """Get paginated commit history for a primitive."""
        data = await self._request(
            "GET",
            f"primitives/{path}/history",
            params={"limit": limit, "offset": offset},
        )
        commits = [CommitInfo(**c) for c in data.get("commits", [])]
        return HistoryResponse(
            path=data.get("path", path),
            total=data.get("total", len(commits)),
            commits=commits,
        )

    async def get_diff(
        self,
        path: str,
        from_hash: str | None = None,
        to_hash: str | None = None,
    ) -> DiffResponse:
        """Get a structured field-level diff between two versions."""
        params: dict[str, str] = {}
        if from_hash:
            params["from"] = from_hash
        if to_hash:
            params["to"] = to_hash
        data = await self._request("GET", f"primitives/{path}/diff", params=params or None)
        changes = [FieldChange(**c) for c in data.get("changes", [])]
        return DiffResponse(
            path=data.get("path", path),
            from_hash=data.get("from_hash", ""),
            to_hash=data.get("to_hash", ""),
            from_timestamp=data.get("from_timestamp", ""),
            to_timestamp=data.get("to_timestamp", ""),
            changes=changes,
        )

    async def search(self, query: str) -> list[Primitive]:
        """Full-text search across name, description, tags, and properties."""
        data = await self._request("GET", "search", params={"q": query})
        return [Primitive(**item) for item in (data or [])]

    async def get_relationships(self, path: str) -> list[Relationship]:
        """Get bidirectional relationships for a primitive."""
        data = await self._request("GET", f"relationships/{path}")
        return [Relationship(**r) for r in (data or [])]

    async def create_primitive(self, payload: PrimitiveCreate) -> Primitive:
        """Create a new primitive. Core auto-generates id, slug, timestamps."""
        data = await self._request(
            "POST",
            "primitives",
            json=payload.model_dump(exclude_none=True),
        )
        return Primitive(**data)

    async def update_primitive(self, path: str, payload: PrimitiveUpdate) -> Primitive:
        """Update a primitive. id, type, name, slug must be present in payload."""
        data = await self._request(
            "PUT",
            f"primitives/{path}",
            json=payload.model_dump(exclude_none=True),
        )
        return Primitive(**data)

    async def delete_primitive(self, path: str) -> None:
        """Delete a primitive and its parent directory."""
        await self._request("DELETE", f"primitives/{path}")
