"""CatalogueClient — async httpx wrapper for every Core (makestack-core) endpoint.

All access to the Core catalogue engine goes through this class.
The Shell is the sole client of Core; no router or module talks to Core directly.

Includes an LRU cache that serves stale catalogue data when Core is unavailable.
Cache TTLs: 300s for list/search endpoints, 1800s for individual primitives.
"""

import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass
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
# Cache configuration
# ---------------------------------------------------------------------------

_LIST_TTL = 300.0    # 5 minutes — list and search results
_ITEM_TTL = 1800.0   # 30 minutes — individual primitives, history, diff
_MAX_CACHE_SIZE = 500


# ---------------------------------------------------------------------------
# LRU Cache
# ---------------------------------------------------------------------------


@dataclass
class _CacheEntry:
    """A single cached API response."""

    data: Any
    cached_at: float
    ttl: float

    @property
    def is_expired(self) -> bool:
        """True if the entry is older than its TTL."""
        return (time.monotonic() - self.cached_at) > self.ttl

    @property
    def age_seconds(self) -> float:
        """Seconds since this entry was cached."""
        return time.monotonic() - self.cached_at


class _LRUCache:
    """Simple LRU cache with per-entry TTL support."""

    def __init__(self, max_size: int = _MAX_CACHE_SIZE) -> None:
        self._cache: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._max_size = max_size

    def get(self, key: str) -> _CacheEntry | None:
        """Return the cache entry or None on miss. Moves hit to end (LRU order)."""
        entry = self._cache.get(key)
        if entry is not None:
            self._cache.move_to_end(key)
        return entry

    def put(self, key: str, data: Any, ttl: float) -> None:
        """Store a value. Evicts the oldest entry if over capacity."""
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = _CacheEntry(data=data, cached_at=time.monotonic(), ttl=ttl)
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def invalidate_prefix(self, prefix: str) -> None:
        """Remove all entries whose key starts with prefix."""
        stale = [k for k in self._cache if k.startswith(prefix)]
        for k in stale:
            del self._cache[k]

    def invalidate(self, key: str) -> None:
        """Remove a specific entry."""
        self._cache.pop(key, None)

    @property
    def size(self) -> int:
        return len(self._cache)


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

    GET responses are cached with an LRU cache (max 500 entries).
    When Core is unreachable, cached data is returned with a staleness flag.
    Write operations (POST/PUT/DELETE) are never cached and return 503 if Core is down.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8420",
        api_key: str = "",
        client: httpx.AsyncClient | None = None,
        dev_mode: bool = False,
        cache_max_size: int = _MAX_CACHE_SIZE,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._dev_mode = dev_mode
        self._connected = False
        self._cache = _LRUCache(max_size=cache_max_size)

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

    @property
    def cache_size(self) -> int:
        """Number of entries currently in the cache."""
        return self._cache.size

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Internal request helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cache_key(method: str, url: str, params: dict[str, Any] | None) -> str:
        """Build a stable cache key from method, URL, and sorted params."""
        param_str = ""
        if params:
            param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{method}:{url}?{param_str}"

    @staticmethod
    def _item_ttl(url: str) -> float:
        """Choose TTL based on whether the URL is a list/search or individual item."""
        # List and search endpoints → shorter TTL
        if url.rstrip("/").endswith("/primitives") or "/search" in url:
            return _LIST_TTL
        return _ITEM_TTL

    async def _raw_request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        timeout: float = 10.0,
    ) -> Any:
        """Execute a Core API request and return parsed JSON.

        Does NOT cache. Raises CoreUnavailableError, CoreNotFoundError,
        or CoreValidationError on error.
        """
        start = time.monotonic()
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
            raise CoreNotFoundError(url)
        if resp.status_code == 400:
            body = resp.json() if resp.content else {}
            raise CoreValidationError(body.get("error", resp.text))
        if resp.status_code >= 500:
            raise CoreUnavailableError(self._base_url)
        if resp.status_code == 204:
            return None

        return resp.json()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        timeout: float = 10.0,
    ) -> Any:
        """Execute a Core API request with cache support for GET requests.

        GET semantics:
          - Cache hit within TTL → return immediately (fast path)
          - Cache hit past TTL, Core connected → return immediately, refresh in background
          - Cache hit past TTL, Core down → return stale data (logs warning)
          - Cache miss, Core down → raise CoreUnavailableError
          - Cache miss, Core up → fetch, cache, return

        Write semantics (POST/PUT/DELETE):
          - Invalidate cache entries for affected path prefix
          - Raise CoreUnavailableError if Core is down (writes cannot be cached)
        """
        url = f"/api/{path.lstrip('/')}" if not path.startswith("/") else path

        if method == "GET":
            return await self._get_with_cache(url, params=params, timeout=timeout)

        # --- Write operation: invalidate cache, pass through ---
        # Invalidate all cached entries for this path prefix (e.g. /api/primitives)
        path_prefix = url.split("?")[0].rsplit("/", 1)[0]
        self._cache.invalidate_prefix(f"GET:{path_prefix}")
        # Also invalidate the list endpoint
        self._cache.invalidate_prefix("GET:/api/primitives")

        return await self._raw_request(method, url, params=params, json=json, timeout=timeout)

    async def _get_with_cache(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        timeout: float = 10.0,
    ) -> Any:
        """GET with stale-while-revalidate cache semantics."""
        key = self._cache_key("GET", url, params)
        ttl = self._item_ttl(url)
        entry = self._cache.get(key)

        # Fast path: fresh cache hit
        if entry is not None and not entry.is_expired:
            return entry.data

        # Stale cache hit: entry exists but is expired
        if entry is not None and entry.is_expired:
            if self._connected:
                # Serve stale immediately; schedule background refresh
                asyncio.create_task(self._background_refresh(url, params, key, ttl, timeout))
                log.debug(
                    "cache_stale_revalidate",
                    url=url,
                    age_seconds=round(entry.age_seconds, 1),
                )
                return entry.data
            else:
                # Core is down — serve expired cache with a warning
                log.warning(
                    "cache_stale_core_down",
                    url=url,
                    age_seconds=round(entry.age_seconds, 1),
                )
                return entry.data

        # Cache miss: try to fetch from Core
        try:
            data = await self._raw_request("GET", url, params=params, timeout=timeout)
            self._cache.put(key, data, ttl)
            return data
        except CoreUnavailableError:
            # No cache entry available — propagate
            raise

    async def _background_refresh(
        self,
        url: str,
        params: dict[str, Any] | None,
        key: str,
        ttl: float,
        timeout: float,
    ) -> None:
        """Silently refresh a cache entry in the background."""
        try:
            data = await self._raw_request("GET", url, params=params, timeout=timeout)
            self._cache.put(key, data, ttl)
            log.debug("cache_refreshed", url=url)
        except Exception as exc:
            log.debug("cache_refresh_failed", url=url, error=str(exc))

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

    async def import_primitive(self, raw: dict) -> None:
        """POST a raw primitive dict to Core (used by catalogue package installer).

        Unlike create_primitive(), this accepts an untyped dict so catalogue
        packages can be imported without round-tripping through PrimitiveCreate.
        """
        await self._request("POST", "primitives", json=raw)

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
