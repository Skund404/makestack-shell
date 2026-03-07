"""makestack_sdk.userdb — re-export from backend.sdk.userdb."""

from backend.sdk.userdb import ModuleUserDB, get_module_userdb_factory, _extract_table_names

__all__ = ["ModuleUserDB", "get_module_userdb_factory", "_extract_table_names"]
