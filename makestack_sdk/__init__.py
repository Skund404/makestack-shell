"""makestack_sdk — re-exports from backend.sdk.

This thin wrapper allows module authors to import the SDK as:
    from makestack_sdk import CatalogueClient, get_logger, ...

The actual implementations live in backend/sdk/.
"""

from backend.sdk import (
    CatalogueClient,
    CoreNotFoundError,
    CoreUnavailableError,
    CoreValidationError,
    get_catalogue_client,
    ModuleUserDB,
    get_module_userdb_factory,
    ModuleConfig,
    get_module_config_factory,
    ShellContext,
    get_shell_context,
    PeerModules,
    get_peer_modules,
    get_logger,
)

__all__ = [
    "CatalogueClient",
    "CoreNotFoundError",
    "CoreUnavailableError",
    "CoreValidationError",
    "get_catalogue_client",
    "ModuleUserDB",
    "get_module_userdb_factory",
    "ModuleConfig",
    "get_module_config_factory",
    "ShellContext",
    "get_shell_context",
    "PeerModules",
    "get_peer_modules",
    "get_logger",
]
