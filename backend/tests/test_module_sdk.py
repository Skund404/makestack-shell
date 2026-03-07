"""Tests for the Module SDK classes."""

import pytest
import pytest_asyncio

from makestack_sdk.testing import MockUserDB, MockCatalogueClient, MockShellContext, MockPeerModules
from makestack_sdk.userdb import ModuleUserDB, _extract_table_names
from makestack_sdk.config import ModuleConfig
from makestack_sdk.logger import get_logger


# ---------------------------------------------------------------------------
# _extract_table_names helper
# ---------------------------------------------------------------------------

def test_extract_from_select():
    tables = _extract_table_names("SELECT * FROM my_module_items")
    assert "my_module_items" in tables


def test_extract_from_join():
    tables = _extract_table_names("SELECT a.id FROM my_module_a a JOIN my_module_b b ON a.id = b.a_id")
    assert "my_module_a" in tables
    assert "my_module_b" in tables


def test_extract_from_insert():
    tables = _extract_table_names("INSERT INTO my_module_items (id, name) VALUES (?, ?)")
    assert "my_module_items" in tables


def test_extract_from_update():
    tables = _extract_table_names("UPDATE my_module_config SET value = ? WHERE key = ?")
    assert "my_module_config" in tables


# ---------------------------------------------------------------------------
# ModuleUserDB — scoping
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def raw_db():
    db = MockUserDB()
    await db.setup([
        "CREATE TABLE my_module_items (id TEXT PRIMARY KEY, name TEXT NOT NULL)",
        "CREATE TABLE my_module_config (key TEXT PRIMARY KEY, value TEXT)",
    ])
    yield db
    await db.teardown()


def make_scoped_db(raw_db, tables=None):
    return ModuleUserDB(
        db=raw_db,
        module_name="my-module",
        allowed_tables=tables or ["my_module_items", "my_module_config"],
    )


@pytest.mark.asyncio
async def test_fetch_all_allowed_table(raw_db):
    db = make_scoped_db(raw_db)
    rows = await db.fetch_all("SELECT * FROM my_module_items")
    assert rows == []


@pytest.mark.asyncio
async def test_fetch_one_allowed_table(raw_db):
    db = make_scoped_db(raw_db)
    row = await db.fetch_one("SELECT * FROM my_module_items WHERE id = ?", ["x"])
    assert row is None


@pytest.mark.asyncio
async def test_execute_allowed_table(raw_db):
    db = make_scoped_db(raw_db)
    await db.execute("INSERT INTO my_module_items (id, name) VALUES (?, ?)", ["1", "Test"])
    rows = await db.fetch_all("SELECT * FROM my_module_items")
    assert len(rows) == 1
    assert rows[0]["name"] == "Test"


@pytest.mark.asyncio
async def test_count_allowed_table(raw_db):
    db = make_scoped_db(raw_db)
    count = await db.count("my_module_items")
    assert count == 0


@pytest.mark.asyncio
async def test_execute_disallowed_table_raises(raw_db):
    db = make_scoped_db(raw_db)
    with pytest.raises(PermissionError) as exc_info:
        await db.fetch_all("SELECT * FROM inventory")
    assert "inventory" in str(exc_info.value)
    assert "my-module" in str(exc_info.value)


@pytest.mark.asyncio
async def test_count_disallowed_table_raises(raw_db):
    db = make_scoped_db(raw_db)
    with pytest.raises(PermissionError):
        await db.count("workshops")


@pytest.mark.asyncio
async def test_scoped_to_subset_of_own_tables(raw_db):
    """A scoped DB restricted to a subset of the module's own tables."""
    db = make_scoped_db(raw_db, tables=["my_module_items"])
    rows = await db.fetch_all("SELECT * FROM my_module_items")
    assert rows == []

    with pytest.raises(PermissionError):
        await db.fetch_all("SELECT * FROM my_module_config")


# ---------------------------------------------------------------------------
# ModuleConfig
# ---------------------------------------------------------------------------

def test_config_get_default():
    config = ModuleConfig("my-module", {"show_qty": True, "max_items": 100})
    assert config.get("show_qty") is True
    assert config.get("max_items") == 100
    assert config.get("missing_key") is None
    assert config.get("missing_key", "fallback") == "fallback"


def test_config_all():
    config = ModuleConfig("my-module", {"a": 1, "b": 2})
    assert config.all() == {"a": 1, "b": 2}


def test_config_overrides_merge():
    config = ModuleConfig("my-module", {"a": 1, "b": 2}, overrides={"b": 99, "c": 3})
    assert config.get("a") == 1
    assert config.get("b") == 99   # Override wins
    assert config.get("c") == 3


def test_config_repr():
    config = ModuleConfig("my-module", {"a": 1})
    assert "my-module" in repr(config)


# ---------------------------------------------------------------------------
# MockCatalogueClient
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_catalogue_list_primitives():
    mock = MockCatalogueClient()
    results = await mock.list_primitives()
    assert len(results) == 1
    assert results[0].type == "tool"


@pytest.mark.asyncio
async def test_mock_catalogue_search():
    mock = MockCatalogueClient()
    results = await mock.search("test")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_mock_catalogue_health():
    mock = MockCatalogueClient()
    assert await mock.health_check() is True


# ---------------------------------------------------------------------------
# MockShellContext
# ---------------------------------------------------------------------------

def test_mock_context_defaults():
    ctx = MockShellContext()
    assert ctx.user_id == "default"
    assert ctx.active_workshop_id is None
    assert ctx.dev_mode is True


def test_mock_context_customised():
    ctx = MockShellContext(user_id="alice", active_workshop_id="ws-1", dev_mode=False)
    assert ctx.user_id == "alice"
    assert ctx.active_workshop_id == "ws-1"
    assert ctx.dev_mode is False


# ---------------------------------------------------------------------------
# MockPeerModules
# ---------------------------------------------------------------------------

def test_peer_is_installed():
    peers = MockPeerModules(installed=["cost-tracker"])
    assert peers.is_installed("cost-tracker") is True
    assert peers.is_installed("inventory-stock") is False


@pytest.mark.asyncio
async def test_peer_call_not_installed_raises():
    peers = MockPeerModules()
    with pytest.raises(ValueError, match="not installed"):
        await peers.call("cost-tracker", "GET", "/costs")


@pytest.mark.asyncio
async def test_peer_call_with_registered_response():
    peers = MockPeerModules(installed=["cost-tracker"])
    peers.register_response("cost-tracker", "/costs/summary", {"total": 42.0})
    result = await peers.call("cost-tracker", "GET", "/costs/summary")
    assert result == {"total": 42.0}


@pytest.mark.asyncio
async def test_peer_call_unregistered_path_raises():
    peers = MockPeerModules(installed=["cost-tracker"])
    with pytest.raises(KeyError):
        await peers.call("cost-tracker", "GET", "/missing")


# ---------------------------------------------------------------------------
# get_logger
# ---------------------------------------------------------------------------

def test_get_logger_returns_bound_logger():
    import structlog
    log = get_logger("my-module")
    assert log is not None


def test_get_logger_no_module_name():
    log = get_logger()
    assert log is not None
