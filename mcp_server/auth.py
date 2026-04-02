"""MCP API key authentication middleware.

Provides key-based auth for the static /mcp-http endpoint, enabling remote
access at a stable URL like https://makestack.yourdomain.com/mcp-http?key=your-secret.

The API key can be passed via:
  - Query parameter:  ?key=your-secret-key
  - Authorization header: Authorization: Bearer your-secret-key

Set MAKESTACK_MCP_API_KEY to enable this endpoint. When unset, the endpoint
is not mounted and this middleware is never used.
"""

import hmac

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class MCPKeyAuthMiddleware(BaseHTTPMiddleware):
    """Validate API key on /mcp-http/* requests.

    Uses hmac.compare_digest for constant-time comparison to prevent
    timing attacks.
    """

    def __init__(self, app, api_key: str) -> None:
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request: Request, call_next):
        # Extract key from ?key= query param or Authorization: Bearer header.
        key_from_query = request.query_params.get("key", "")
        auth_header = request.headers.get("Authorization", "")
        key_from_header = ""
        if auth_header.startswith("Bearer "):
            key_from_header = auth_header[len("Bearer "):]

        provided = key_from_query or key_from_header

        # Reject immediately if no key provided or key is empty.
        if not provided or not self._api_key:
            return JSONResponse(
                {"error": "unauthorized", "suggestion": "Provide ?key=your-secret-key or Authorization: Bearer header"},
                status_code=401,
            )

        # Constant-time comparison prevents timing attacks.
        if not hmac.compare_digest(provided, self._api_key):
            return JSONResponse(
                {"error": "unauthorized", "suggestion": "Invalid API key"},
                status_code=401,
            )

        return await call_next(request)
