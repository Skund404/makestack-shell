"""SDK surface: Module configuration reader.

Modules can declare config_defaults in their manifest. At runtime, users
can override these by placing a JSON file at .makestack/modules/{name}.config.json
in the data repo. The Shell reads this config from Core and provides it via
ModuleConfig.

For Phase 5, config is loaded from the Shell's app.state.config dictionary.
Full config-from-Core is a Phase 7 feature.

Usage in a module's routes.py:

    from makestack_sdk.config import ModuleConfig, get_module_config_factory
    from fastapi import APIRouter, Depends

    router = APIRouter()

    get_config = get_module_config_factory("inventory-stock", {"show_quantity": True})

    @router.get("/settings")
    async def get_settings(config: ModuleConfig = Depends(get_config)):
        return {"show_quantity": config.get("show_quantity", True)}
"""

from typing import Any

from fastapi import Request


class ModuleConfig:
    """Module configuration — merged defaults and user overrides.

    For Phase 5, always returns defaults (override loading from Core is Phase 7).
    """

    def __init__(self, module_name: str, defaults: dict[str, Any], overrides: dict[str, Any] | None = None) -> None:
        self._module_name = module_name
        self._data: dict[str, Any] = {**defaults, **(overrides or {})}

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by key."""
        return self._data.get(key, default)

    def all(self) -> dict[str, Any]:
        """Return all config key-value pairs."""
        return dict(self._data)

    def __repr__(self) -> str:
        return f"ModuleConfig(module={self._module_name!r}, keys={list(self._data)})"


def get_module_config_factory(module_name: str, defaults: dict[str, Any] | None = None):
    """Return a FastAPI dependency function that provides a ModuleConfig.

    Call this once at module import time:

        get_config = get_module_config_factory("my-module", {"feature_x": True})

        @router.get("/endpoint")
        async def my_endpoint(config: ModuleConfig = Depends(get_config)):
            if config.get("feature_x"):
                ...
    """
    _defaults = defaults or {}

    async def _get_config(request: Request) -> ModuleConfig:
        # Phase 5: always returns defaults.
        # Phase 7+: fetch overrides from Core's .makestack/modules/{name}.config.json
        return ModuleConfig(module_name=module_name, defaults=_defaults)

    return _get_config


__all__ = ["ModuleConfig", "get_module_config_factory"]
