"""Tests for UserDB — migration runner, schema creation, and query helpers."""

import pytest
import pytest_asyncio

from backend.app.userdb import UserDB


@pytest_asyncio.fixture
async def fresh_db():
    """Provide a fresh in-memory UserDB (migrations NOT yet run)."""
    database = UserDB(":memory:")
    await database.open()
    yield database
    await database.close()


# ---------------------------------------------------------------------------
# Migration runner
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migrations_create_tracking_table(fresh_db):
    await fresh_db.run_migrations()
    tables = await fresh_db.table_names()
    assert "_shell_migrations" in tables


@pytest.mark.asyncio
async def test_migrations_create_all_core_tables(fresh_db):
    await fresh_db.run_migrations()
    tables = await fresh_db.table_names()
    expected = [
        "users",
        "user_preferences",
        "workshops",
        "workshop_members",
        "inventory",
        "installed_modules",
        "module_migrations",
    ]
    for table in expected:
        assert table in tables, f"Expected table '{table}' to exist"


@pytest.mark.asyncio
async def test_migrations_are_idempotent(fresh_db):
    """Running migrations twice should not raise or duplicate data."""
    await fresh_db.run_migrations()
    await fresh_db.run_migrations()
    tables = await fresh_db.table_names()
    assert "users" in tables


@pytest.mark.asyncio
async def test_migration_seeds_default_user(fresh_db):
    await fresh_db.run_migrations()
    row = await fresh_db.fetch_one("SELECT * FROM users WHERE id = 'default'")
    assert row is not None
    assert row["name"] == "Maker"


@pytest.mark.asyncio
async def test_applied_migrations_are_tracked(fresh_db):
    await fresh_db.run_migrations()
    rows = await fresh_db.fetch_all("SELECT id FROM _shell_migrations")
    ids = [r["id"] for r in rows]
    assert "001_initial_schema" in ids


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db():
    """Provide an in-memory UserDB with migrations applied."""
    database = UserDB(":memory:")
    await database.open()
    await database.run_migrations()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_fetch_one_returns_dict(db):
    row = await db.fetch_one("SELECT * FROM users WHERE id = 'default'")
    assert isinstance(row, dict)
    assert row["id"] == "default"


@pytest.mark.asyncio
async def test_fetch_one_returns_none_for_missing(db):
    row = await db.fetch_one("SELECT * FROM users WHERE id = 'nonexistent'")
    assert row is None


@pytest.mark.asyncio
async def test_fetch_all_returns_list(db):
    rows = await db.fetch_all("SELECT * FROM users")
    assert isinstance(rows, list)
    assert len(rows) >= 1


@pytest.mark.asyncio
async def test_execute_inserts_row(db):
    await db.execute(
        "INSERT INTO workshops (id, name, slug, created_at, updated_at) VALUES (?, ?, ?, datetime('now'), datetime('now'))",
        ["ws-1", "My Workshop", "my-workshop"],
    )
    row = await db.fetch_one("SELECT * FROM workshops WHERE id = 'ws-1'")
    assert row is not None
    assert row["name"] == "My Workshop"


@pytest.mark.asyncio
async def test_execute_returning_gives_inserted_row(db):
    row = await db.execute_returning(
        "INSERT INTO workshops (id, name, slug, created_at, updated_at) VALUES (?, ?, ?, datetime('now'), datetime('now')) RETURNING *",
        ["ws-ret", "Returning Workshop", "returning-workshop"],
    )
    assert row["id"] == "ws-ret"
    assert row["name"] == "Returning Workshop"


@pytest.mark.asyncio
async def test_count_returns_integer(db):
    n = await db.count("users")
    assert isinstance(n, int)
    assert n >= 1


@pytest.mark.asyncio
async def test_count_with_where_clause(db):
    n = await db.count("users", "id = ?", ["default"])
    assert n == 1


@pytest.mark.asyncio
async def test_table_names_returns_list(db):
    tables = await db.table_names()
    assert isinstance(tables, list)
    assert "users" in tables


@pytest.mark.asyncio
async def test_foreign_key_constraint_enforced(db):
    """INSERT into workshop_members with a nonexistent workshop_id should fail."""
    with pytest.raises(Exception):
        await db.execute(
            "INSERT INTO workshop_members (workshop_id, primitive_path, primitive_type, added_at) VALUES (?, ?, ?, datetime('now'))",
            ["nonexistent-workshop", "tools/chisel/manifest.json", "tool"],
        )
