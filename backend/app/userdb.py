"""UserDB — async SQLite manager for personal state.

Wraps aiosqlite with a migration runner, row-dict factory, and typed query helpers.
The database lives at ~/.makestack/userdb.sqlite (configurable).
"""

import importlib.util
import os
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiosqlite
import structlog

log = structlog.get_logger().bind(component="userdb")

# Directory containing migration modules (001_initial_schema.py, etc.)
_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _row_factory(cursor: aiosqlite.Cursor, row: tuple) -> dict:
    """Convert a sqlite3 Row into a plain dict."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


class UserDB:
    """Async SQLite manager for all Shell personal state.

    Usage:
        db = UserDB("~/.makestack/userdb.sqlite")
        await db.open()
        await db.run_migrations()
        # ... use db ...
        await db.close()
    """

    def __init__(self, path: str = "~/.makestack/userdb.sqlite", dev_mode: bool = False) -> None:
        resolved = Path(path).expanduser()
        self._path = str(resolved)
        self._dev_mode = dev_mode
        self._conn: aiosqlite.Connection | None = None

    @property
    def path(self) -> str:
        return self._path

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def open(self) -> None:
        """Open the database connection, creating the file and parent dirs if needed."""
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = _row_factory  # type: ignore[assignment]

        # Enable WAL mode for better concurrent read performance.
        await self._conn.execute("PRAGMA journal_mode=WAL")
        # Enforce foreign key constraints.
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.commit()
        log.info("userdb_opened", path=self._path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            log.info("userdb_closed", path=self._path)

    def _require_connection(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("UserDB connection is not open. Call await db.open() first.")
        return self._conn

    # ------------------------------------------------------------------
    # Migration runner
    # ------------------------------------------------------------------

    async def run_migrations(self) -> None:
        """Discover and apply any pending Shell core migrations.

        Tracks applied migrations in the ``_shell_migrations`` table, which is
        created here on first run before any other migration can touch it.
        """
        conn = self._require_connection()

        # Bootstrap the tracking table before anything else.
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS _shell_migrations (
                id      TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        await conn.commit()

        # Collect already-applied migration IDs.
        cursor = await conn.execute("SELECT id FROM _shell_migrations")
        applied: set[str] = {row["id"] async for row in cursor}

        # Find migration modules sorted by filename (numerical order assumed).
        migration_files = sorted(_MIGRATIONS_DIR.glob("[0-9]*.py"))

        for migration_file in migration_files:
            # Dynamically import the migration module.
            spec = importlib.util.spec_from_file_location(
                f"makestack.migrations.{migration_file.stem}",
                migration_file,
            )
            if spec is None or spec.loader is None:
                log.error("migration_load_failed", file=str(migration_file))
                continue

            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module  # type: ignore[index]
            spec.loader.exec_module(module)  # type: ignore[union-attr]

            migration_id: str = getattr(module, "ID", migration_file.stem)

            if migration_id in applied:
                log.debug("migration_already_applied", id=migration_id)
                continue

            log.info("migration_applying", id=migration_id)
            start = time.monotonic()

            await module.up(conn)
            await conn.execute(
                "INSERT INTO _shell_migrations (id) VALUES (?)",
                (migration_id,),
            )
            await conn.commit()

            elapsed_ms = (time.monotonic() - start) * 1000
            log.info("migration_applied", id=migration_id, elapsed_ms=round(elapsed_ms, 1))

    # ------------------------------------------------------------------
    # Generic query helpers
    # ------------------------------------------------------------------

    async def fetch_one(self, sql: str, params: list[Any] | None = None) -> dict | None:
        """Execute a SELECT and return the first row as a dict, or None."""
        conn = self._require_connection()
        start = time.monotonic()
        cursor = await conn.execute(sql, params or [])
        row = await cursor.fetchone()
        if self._dev_mode:
            log.debug("db_fetch_one", sql=sql[:120], elapsed_ms=round((time.monotonic() - start) * 1000, 1))
        return row  # type: ignore[return-value]  — row_factory returns dict

    async def fetch_all(self, sql: str, params: list[Any] | None = None) -> list[dict]:
        """Execute a SELECT and return all rows as a list of dicts."""
        conn = self._require_connection()
        start = time.monotonic()
        cursor = await conn.execute(sql, params or [])
        rows = await cursor.fetchall()
        if self._dev_mode:
            log.debug("db_fetch_all", sql=sql[:120], rows=len(rows), elapsed_ms=round((time.monotonic() - start) * 1000, 1))
        return rows  # type: ignore[return-value]

    async def execute(self, sql: str, params: list[Any] | None = None) -> None:
        """Execute a DML statement (INSERT/UPDATE/DELETE) without returning rows."""
        conn = self._require_connection()
        start = time.monotonic()
        await conn.execute(sql, params or [])
        await conn.commit()
        if self._dev_mode:
            log.debug("db_execute", sql=sql[:120], elapsed_ms=round((time.monotonic() - start) * 1000, 1))

    async def execute_returning(self, sql: str, params: list[Any] | None = None) -> dict:
        """Execute an INSERT … RETURNING statement and return the inserted row."""
        conn = self._require_connection()
        start = time.monotonic()
        cursor = await conn.execute(sql, params or [])
        row = await cursor.fetchone()
        await conn.commit()
        if self._dev_mode:
            log.debug("db_execute_returning", sql=sql[:120], elapsed_ms=round((time.monotonic() - start) * 1000, 1))
        if row is None:
            raise RuntimeError("INSERT … RETURNING returned no row")
        return row  # type: ignore[return-value]

    async def count(self, table: str, where: str = "", params: list[Any] | None = None) -> int:
        """Return the row count for a table, with an optional WHERE clause."""
        sql = f"SELECT COUNT(*) as n FROM {table}"  # noqa: S608 — table name is internal
        if where:
            sql += f" WHERE {where}"
        row = await self.fetch_one(sql, params)
        return int(row["n"]) if row else 0

    async def table_names(self) -> list[str]:
        """Return all table names in the database."""
        rows = await self.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [r["name"] for r in rows]

    # ------------------------------------------------------------------
    # Backup and restore
    # ------------------------------------------------------------------

    async def backup(self, dest_path: str) -> None:
        """Backup the database to dest_path using aiosqlite's native backup API.

        Creates the destination directory if it does not exist. The backup is
        a fully valid SQLite file usable independently of the running shell.
        """
        conn = self._require_connection()
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(str(dest)) as dest_conn:
            await conn.backup(dest_conn)
        log.info("userdb_backed_up", dest=dest_path)

    async def restore(self, src_path: str) -> None:
        """Restore the database from src_path.

        Closes the current connection, copies src_path over the live database
        file, then reopens the connection. The restored database is immediately
        active for subsequent queries.
        """
        if self._path == ":memory:":
            raise RuntimeError("Cannot restore an in-memory database from a file backup.")
        src = Path(src_path)
        if not src.exists():
            raise FileNotFoundError(f"Backup file not found: {src_path}")
        await self.close()
        shutil.copy2(str(src), self._path)
        await self.open()
        log.info("userdb_restored", src=src_path, dest=self._path)

    @staticmethod
    def prune_backups(
        backups_dir: str | Path,
        keep_daily: int = 7,
        keep_pre_install_days: int = 30,
    ) -> list[str]:
        """Remove old backups, returning a list of deleted file paths.

        Retention rules:
        - Manual/daily backups (``userdb-backup-*.sqlite``): keep the most
          recent ``keep_daily`` files, delete the rest.
        - Pre-install snapshots (``userdb-preinstall-*.sqlite``): keep any
          file whose mtime is within the last ``keep_pre_install_days`` days.
        """
        backups_dir = Path(backups_dir)
        if not backups_dir.exists():
            return []

        deleted: list[str] = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=keep_pre_install_days)

        # Daily/manual backups — keep most recent N by filename sort (timestamps in name).
        daily = sorted(backups_dir.glob("userdb-backup-*.sqlite"), reverse=True)
        for f in daily[keep_daily:]:
            f.unlink()
            deleted.append(str(f))
            log.info("backup_pruned", path=str(f), reason="daily_retention")

        # Pre-install snapshots — keep anything newer than cutoff.
        for f in backups_dir.glob("userdb-preinstall-*.sqlite"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                f.unlink()
                deleted.append(str(f))
                log.info("backup_pruned", path=str(f), reason="preinstall_retention")

        return deleted
