"""Tests for Phase 10A — UserDB backup infrastructure.

Coverage:
    - UserDB.backup() creates a valid, readable SQLite file
    - UserDB.restore() round-trips data correctly
    - UserDB.prune_backups() respects daily and pre-install retention rules
    - GET /api/backups returns the backup list
    - POST /api/backups creates a backup (smoke test)
    - POST /api/backups/restore restores data (smoke test)
    - Migration 007 creates install_transactions table
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.app.userdb import UserDB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_db(path: str) -> UserDB:
    """Open a file-based UserDB with all migrations applied."""
    db = UserDB(path, dev_mode=True)
    await db.open()
    await db.run_migrations()
    return db


# ---------------------------------------------------------------------------
# UserDB.backup()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backup_creates_valid_sqlite_file(tmp_path):
    """backup() produces a readable SQLite file containing the correct schema."""
    db = await _make_db(str(tmp_path / "userdb.sqlite"))
    # Add some data to verify it lands in the backup.
    await db.execute(
        "INSERT INTO installed_modules (name, version, installed_at) VALUES ('backup-test-mod', '1.0.0', datetime('now'))"
    )

    dest = str(tmp_path / "backups" / "userdb-backup-test.sqlite")
    await db.backup(dest)
    await db.close()

    assert Path(dest).exists(), "Backup file was not created"
    assert Path(dest).stat().st_size > 0, "Backup file is empty"

    # Independently open the backup and verify the data is there.
    async with aiosqlite.connect(dest) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT version FROM installed_modules WHERE name = 'backup-test-mod'")
        row = await cursor.fetchone()
        assert row is not None, "Backup does not contain the inserted module row"
        assert row["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_backup_creates_parent_directories(tmp_path):
    """backup() creates intermediate directories that do not yet exist."""
    db = await _make_db(str(tmp_path / "userdb.sqlite"))
    dest = str(tmp_path / "deep" / "nested" / "dir" / "backup.sqlite")
    await db.backup(dest)
    await db.close()

    assert Path(dest).exists()


# ---------------------------------------------------------------------------
# UserDB.restore()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_restore_roundtrips_data(tmp_path):
    """restore() brings back data that was present at backup time."""
    db_path = str(tmp_path / "userdb.sqlite")
    db = await _make_db(db_path)
    await db.execute(
        "INSERT INTO installed_modules (name, version, installed_at) VALUES ('restore-mod', '2.0.0', datetime('now'))"
    )

    backup_path = str(tmp_path / "snap.sqlite")
    await db.backup(backup_path)

    # Mutate the live DB after the backup.
    await db.execute("DELETE FROM installed_modules")
    assert await db.count("installed_modules") == 0

    # Restore and confirm the row is back.
    await db.restore(backup_path)
    assert await db.count("installed_modules") == 1
    row = await db.fetch_one("SELECT version FROM installed_modules WHERE name = 'restore-mod'")
    assert row is not None
    assert row["version"] == "2.0.0"
    await db.close()


@pytest.mark.asyncio
async def test_restore_raises_on_missing_backup(tmp_path):
    """restore() raises FileNotFoundError when the backup path does not exist."""
    db = await _make_db(str(tmp_path / "userdb.sqlite"))
    with pytest.raises(FileNotFoundError):
        await db.restore(str(tmp_path / "nonexistent.sqlite"))
    await db.close()


@pytest.mark.asyncio
async def test_restore_raises_on_in_memory_db():
    """restore() raises RuntimeError for in-memory databases (not restorable from file)."""
    db = UserDB(":memory:", dev_mode=True)
    await db.open()
    await db.run_migrations()
    with pytest.raises(RuntimeError, match="in-memory"):
        await db.restore("/tmp/any.sqlite")
    await db.close()


# ---------------------------------------------------------------------------
# UserDB.prune_backups()
# ---------------------------------------------------------------------------


def test_prune_keeps_most_recent_daily(tmp_path):
    """prune_backups() removes daily backups beyond keep_daily, newest first."""
    # Create 10 daily backup files with ascending timestamps in the name.
    for i in range(10):
        f = tmp_path / f"userdb-backup-20260313-{i:06d}.sqlite"
        f.touch()

    deleted = UserDB.prune_backups(tmp_path, keep_daily=7, keep_pre_install_days=30)

    remaining = sorted(tmp_path.glob("userdb-backup-*.sqlite"))
    assert len(remaining) == 7, f"Expected 7, got {len(remaining)}: {remaining}"
    assert len(deleted) == 3
    # The 3 oldest (lowest index) should be deleted.
    for i in range(3):
        assert not (tmp_path / f"userdb-backup-20260313-{i:06d}.sqlite").exists()


def test_prune_keeps_recent_preinstall(tmp_path):
    """prune_backups() deletes pre-install snapshots older than keep_pre_install_days."""
    recent1 = tmp_path / "userdb-preinstall-20260313-000000.sqlite"
    recent2 = tmp_path / "userdb-preinstall-20260312-000000.sqlite"
    old1 = tmp_path / "userdb-preinstall-20260101-000000.sqlite"
    old2 = tmp_path / "userdb-preinstall-20260201-000000.sqlite"

    for f in [recent1, recent2, old1, old2]:
        f.touch()

    # Back-date old files so they appear >30 days old.
    old_ts = (datetime.now(timezone.utc) - timedelta(days=31)).timestamp()
    os.utime(old1, (old_ts, old_ts))
    os.utime(old2, (old_ts, old_ts))

    deleted = UserDB.prune_backups(tmp_path, keep_daily=7, keep_pre_install_days=30)

    remaining = list(tmp_path.glob("userdb-preinstall-*.sqlite"))
    assert len(remaining) == 2, f"Expected 2 recent to survive, got {remaining}"
    assert len(deleted) == 2
    assert not old1.exists()
    assert not old2.exists()
    assert recent1.exists()
    assert recent2.exists()


def test_prune_returns_empty_list_for_missing_dir(tmp_path):
    """prune_backups() returns [] when the backups directory does not exist."""
    result = UserDB.prune_backups(tmp_path / "nonexistent")
    assert result == []


def test_prune_does_not_touch_unrelated_files(tmp_path):
    """prune_backups() ignores files that don't match the naming convention."""
    keep = tmp_path / "notes.txt"
    keep.touch()
    other = tmp_path / "random-file.sqlite"
    other.touch()

    UserDB.prune_backups(tmp_path, keep_daily=0, keep_pre_install_days=0)

    assert keep.exists()
    assert other.exists()


# ---------------------------------------------------------------------------
# Migration 007 — install_transactions table
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_007_creates_install_transactions(db):
    """Migration 007 creates the install_transactions table with the correct columns."""
    tables = await db.table_names()
    assert "install_transactions" in tables

    # Insert a minimal row to verify the schema is correct.
    import uuid
    tx_id = str(uuid.uuid4())
    await db.execute(
        "INSERT INTO install_transactions (id, package_name, package_type) VALUES (?, ?, ?)",
        [tx_id, "test-pkg", "module"],
    )
    row = await db.fetch_one(
        "SELECT * FROM install_transactions WHERE id = ?", [tx_id]
    )
    assert row is not None
    assert row["package_name"] == "test-pkg"
    assert row["status"] == "in_progress"
    assert row["steps_completed"] == "[]"
    assert row["failed_step"] is None


# ---------------------------------------------------------------------------
# API endpoint smoke tests
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def backup_client(tmp_path):
    """Test client backed by a real file-based UserDB so backups can land on disk."""
    from unittest.mock import MagicMock, AsyncMock
    from backend.app.core_client import CatalogueClient
    from backend.app.dependencies import get_core_client, get_userdb
    from backend.app.main import create_app

    db_path = str(tmp_path / "userdb.sqlite")
    db = await _make_db(db_path)

    app = create_app()
    app.state.userdb = db
    app.state.core_client = MagicMock(spec=CatalogueClient)
    app.state.core_client.health_check = AsyncMock(return_value=True)
    app.state.core_connected = True
    app.state.last_core_check = "2026-03-13T00:00:00+00:00"
    app.state.dev_mode = True
    app.state.config = {"core_url": "http://localhost:8420"}

    import time
    app.state.start_time = time.monotonic()

    module_registry = MagicMock()
    module_registry.is_loaded = MagicMock(return_value=False)
    module_registry.get_module = MagicMock(return_value=None)
    module_registry.get_module_views = MagicMock(return_value=[])
    module_registry.get_module_panels = MagicMock(return_value=[])
    app.state.module_registry = module_registry

    app.dependency_overrides[get_userdb] = lambda: db
    app.dependency_overrides[get_core_client] = lambda: app.state.core_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, db

    await db.close()


@pytest.mark.asyncio
async def test_list_backups_empty(backup_client):
    """GET /api/backups returns an empty list when no backups exist."""
    ac, _ = backup_client
    resp = await ac.get("/api/backups")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_backup_via_api(backup_client, tmp_path):
    """POST /api/backups creates a backup file and returns its metadata."""
    ac, _ = backup_client
    resp = await ac.post("/api/backups")
    assert resp.status_code == 201
    data = resp.json()
    assert "path" in data
    assert data["kind"] == "manual"
    assert data["size_bytes"] > 0
    assert Path(data["path"]).exists()


@pytest.mark.asyncio
async def test_list_backups_after_create(backup_client):
    """GET /api/backups lists the backup created via POST."""
    ac, _ = backup_client
    await ac.post("/api/backups")
    resp = await ac.get("/api/backups")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["kind"] == "manual"


@pytest.mark.asyncio
async def test_restore_via_api(backup_client, tmp_path):
    """POST /api/backups/restore restores data from a backup."""
    ac, db = backup_client

    # Insert a module record, take a backup, then delete it.
    await db.execute(
        "INSERT INTO installed_modules (name, version, installed_at) VALUES ('api-restore-mod', '3.0.0', datetime('now'))"
    )
    backup_resp = await ac.post("/api/backups")
    backup_path = backup_resp.json()["path"]

    await db.execute("DELETE FROM installed_modules WHERE name = 'api-restore-mod'")
    assert await db.count("installed_modules", "name = 'api-restore-mod'") == 0

    # Restore via API.
    restore_resp = await ac.post("/api/backups/restore", json={"backup_path": backup_path})
    assert restore_resp.status_code == 200
    assert restore_resp.json()["ok"] is True

    # The row should be back.
    assert await db.count("installed_modules", "name = 'api-restore-mod'") == 1


@pytest.mark.asyncio
async def test_restore_missing_path_returns_404(backup_client):
    """POST /api/backups/restore returns 404 for a path that does not exist."""
    ac, _ = backup_client
    resp = await ac.post("/api/backups/restore", json={"backup_path": "/nonexistent/backup.sqlite"})
    assert resp.status_code == 404
