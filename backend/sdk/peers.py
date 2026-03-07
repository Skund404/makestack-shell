"""SDK surface: Peer module awareness for module authors.

Modules can check if other modules are installed and call their endpoints.
This is the sanctioned inter-module communication mechanism.

Modules MUST NOT:
  - Import other modules' Python packages directly
  - Access other modules' UserDB tables directly
  - Bypass the Shell's routing layer

Usage in a module's routes.py:

    from makestack_sdk.peers import PeerModules, get_peer_modules
    from fastapi import APIRouter, Depends

    router = APIRouter()

    @router.get("/enhanced")
    async def enhanced(peers: PeerModules = Depends(get_peer_modules)):
        if peers.is_installed("cost-tracker"):
            cost_data = await peers.call("cost-tracker", "GET", "/costs/summary")
            return {"cost_data": cost_data}
        return {"message": "Cost tracker not installed"}
"""

from typing import Any

import httpx
from fastapi import Request


class PeerModules:
    """Inter-module communication helper.

    Provides checked access to other installed modules via the Shell's
    own routing layer (HTTP calls to localhost).
    """

    def __init__(self, loaded_module_names: set[str], shell_base_url: str) -> None:
        self._loaded = loaded_module_names
        self._base_url = shell_base_url

    def is_installed(self, module_name: str) -> bool:
        """Return True if the named module is currently loaded and enabled."""
        return module_name in self._loaded

    async def call(
        self,
        module_name: str,
        method: str,
        path: str,
        body: Any = None,
        params: dict | None = None,
    ) -> Any:
        """Call another module's API endpoint via the Shell's routing layer.

        Returns the parsed JSON response or raises httpx.HTTPStatusError on error.

        module_name: the target module's registered name.
        method: HTTP method (GET, POST, PUT, DELETE).
        path: endpoint path relative to /modules/{module_name}/ (e.g., "/stock/item-1").
        body: optional request body for POST/PUT.
        params: optional query parameters.
        """
        if not self.is_installed(module_name):
            raise ValueError(
                f"Peer module '{module_name}' is not installed or not enabled. "
                f"Check peers.is_installed('{module_name}') before calling."
            )

        url = f"{self._base_url}/modules/{module_name}/{path.lstrip('/')}"
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method=method.upper(),
                url=url,
                json=body,
                params=params,
            )
            resp.raise_for_status()
            return resp.json()


async def get_peer_modules(request: Request) -> PeerModules:
    """FastAPI dependency: inject a PeerModules instance.

    Reads loaded module names from app.state.module_registry.
    """
    registry = getattr(request.app.state, "module_registry", None)
    loaded_names: set[str] = set()
    if registry is not None:
        loaded_names = {m.name for m in registry.get_loaded()}

    # Shell's own URL — modules call back into the same process.
    config: dict = getattr(request.app.state, "config", {})
    port = config.get("port", 3000)
    shell_url = f"http://localhost:{port}"

    return PeerModules(loaded_module_names=loaded_names, shell_base_url=shell_url)


__all__ = ["PeerModules", "get_peer_modules"]
