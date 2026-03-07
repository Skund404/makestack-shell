"""SDK surface: Scoped UserDB access for module authors.

Modules can only read/write tables they declared in their manifest
(tables prefixed with their module name). The ModuleUserDB wrapper
enforces this at query time by checking for disallowed table references.

Usage in a module's routes.py:

    from makestack_sdk.userdb import ModuleUserDB, get_module_userdb_factory
    from fastapi import APIRouter, Depends

    router = APIRouter()

    # Create the dependency using the module name and declared table names.
    get_db = get_module_userdb_factory(
        module_name="inventory-stock",
        allowed_tables=["inventory_stock"],  # from manifest userdb_tables
    )

    @router.get("/stock")
    async def list_stock(db: ModuleUserDB = Depends(get_db)):
        rows = await db.fetch_all("SELECT * FROM inventory_stock")
        return rows
"""

import re
from typing import Any

from fastapi import Request

from backend.app.userdb import UserDB


# ---------------------------------------------------------------------------
# Table name extractor (simple — not a full SQL parser)
# ---------------------------------------------------------------------------


def _extract_table_names(sql: str) -> list[str]:
    """Extract table names referenced in a SQL statement.

    Uses simple pattern matching on common SQL keywords. Sufficient for the
    straightforward queries modules write; not a full SQL parser.

    Patterns matched:
      FROM <name>, JOIN <name>, INTO <name>, UPDATE <name>, TABLE <name>
    """
    pattern = r"""
        (?:FROM|JOIN|INTO|UPDATE|TABLE)\s+
        ["']?(\w+)["']?           # table name, optionally quoted
    """
    return re.findall(pattern, sql, re.IGNORECASE | re.VERBOSE)


# ---------------------------------------------------------------------------
# ModuleUserDB — scoped access
# ---------------------------------------------------------------------------


class ModuleUserDB:
    """Scoped database access for a single module.

    Wraps the Shell's UserDB and enforces that all queries reference only
    tables declared by this module (i.e., tables with the module prefix).
    """

    def __init__(self, db: UserDB, module_name: str, allowed_tables: list[str]) -> None:
        self._db = db
        self._module_name = module_name
        self._allowed_tables = set(allowed_tables)

    def _check_tables(self, sql: str) -> None:
        """Raise ValueError if the SQL references any table not in the allowlist."""
        referenced = _extract_table_names(sql)
        for table in referenced:
            if table not in self._allowed_tables:
                raise PermissionError(
                    f"Module '{self._module_name}' attempted to access table '{table}', "
                    f"which is not in its declared tables: {sorted(self._allowed_tables)}. "
                    f"Modules can only access tables they declared in their manifest."
                )

    async def fetch_one(self, sql: str, params: list[Any] | None = None) -> dict | None:
        """Execute a SELECT and return the first row as a dict, or None."""
        self._check_tables(sql)
        return await self._db.fetch_one(sql, params)

    async def fetch_all(self, sql: str, params: list[Any] | None = None) -> list[dict]:
        """Execute a SELECT and return all rows as a list of dicts."""
        self._check_tables(sql)
        return await self._db.fetch_all(sql, params)

    async def execute(self, sql: str, params: list[Any] | None = None) -> None:
        """Execute a DML statement without returning rows."""
        self._check_tables(sql)
        await self._db.execute(sql, params)

    async def execute_returning(self, sql: str, params: list[Any] | None = None) -> dict:
        """Execute an INSERT … RETURNING statement and return the inserted row."""
        self._check_tables(sql)
        return await self._db.execute_returning(sql, params)

    async def count(self, table: str, where: str = "", params: list[Any] | None = None) -> int:
        """Return the row count for a module-owned table."""
        if table not in self._allowed_tables:
            raise PermissionError(
                f"Module '{self._module_name}' cannot count rows in '{table}'. "
                f"Allowed tables: {sorted(self._allowed_tables)}"
            )
        return await self._db.count(table, where, params)


# ---------------------------------------------------------------------------
# Dependency factory
# ---------------------------------------------------------------------------


def get_module_userdb_factory(module_name: str, allowed_tables: list[str]):
    """Return a FastAPI dependency function that provides a scoped ModuleUserDB.

    Call this once at module import time to create the dependency:

        get_db = get_module_userdb_factory("inventory-stock", ["inventory_stock"])

        @router.get("/stock")
        async def list_stock(db: ModuleUserDB = Depends(get_db)):
            ...
    """
    async def _get_module_userdb(request: Request) -> ModuleUserDB:
        db: UserDB = request.app.state.userdb
        return ModuleUserDB(db=db, module_name=module_name, allowed_tables=allowed_tables)

    return _get_module_userdb


__all__ = ["ModuleUserDB", "get_module_userdb_factory"]
