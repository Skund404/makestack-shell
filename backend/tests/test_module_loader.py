"""Tests for the module loader — manifest parsing, migration, router mounting."""

import json
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

from backend.app.module_loader import (
    ModuleRegistry,
    LoadedModule,
    _find_manifest_path,
    _load_manifest,
    _run_module_migrations,
    load_modules,
)
from backend.app.module_manifest import ModuleManifest
from backend.app.userdb import UserDB


# ---------------------------------------------------------------------------
# Fixtures — create a temporary module on disk
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_module(tmp_path: Path) -> Path:
    """Create a minimal valid module directory in a temp location."""
    module_dir = tmp_path / "test-module"
    (module_dir / "backend" / "migrations").mkdir(parents=True)

    # manifest.json
    manifest = {
        "name": "test-module",
        "display_name": "Test Module",
        "version": "0.1.0",
        "description": "A test module for loader tests.",
        "author": "Test Suite",
        "has_backend": True,
        "has_frontend": False,
        "keywords": [
            {"keyword": "TEST_MOD_", "description": "Test keyword", "renderer": "TestWidget"}
        ],
        "api_endpoints": [
            {"method": "GET", "path": "/items", "description": "List items"}
        ],
        "userdb_tables": [
            {"name": "test_module_items", "description": "Test items"}
        ],
    }
    (module_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # backend/__init__.py
    (module_dir / "backend" / "__init__.py").write_text("", encoding="utf-8")

    # backend/routes.py — minimal FastAPI router
    (module_dir / "backend" / "routes.py").write_text(
        'from fastapi import APIRouter\n'
        'router = APIRouter()\n\n'
        '@router.get("/items")\n'
        'async def list_items() -> dict:\n'
        '    return {"items": [], "total": 0}\n',
        encoding="utf-8",
    )

    # backend/migrations/001_create_tables.py
    (module_dir / "backend" / "migrations" / "001_create_tables.py").write_text(
        'ID = "001_create_test_module_tables"\n\n'
        'async def up(conn) -> None:\n'
        '    await conn.execute(\n'
        '        "CREATE TABLE IF NOT EXISTS test_module_items "\n'
        '        "(id TEXT PRIMARY KEY, name TEXT NOT NULL)"\n'
        '    )\n'
        '    await conn.commit()\n',
        encoding="utf-8",
    )

    return module_dir


@pytest_asyncio.fixture
async def db() -> UserDB:
    database = UserDB(":memory:", dev_mode=True)
    await database.open()
    await database.run_migrations()
    yield database
    await database.close()


# ---------------------------------------------------------------------------
# Manifest resolution
# ---------------------------------------------------------------------------


def test_find_manifest_path_local(tmp_module: Path):
    path = _find_manifest_path("test-module", str(tmp_module))
    assert path.name == "manifest.json"
    assert path.exists()


def test_find_manifest_path_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        _find_manifest_path("nonexistent-module", str(tmp_path))


def test_load_manifest_valid(tmp_module: Path):
    manifest = _load_manifest("test-module", str(tmp_module))
    assert manifest.name == "test-module"
    assert manifest.version == "0.1.0"
    assert len(manifest.keywords) == 1
    assert manifest.keywords[0].keyword == "TEST_MOD_"
    assert len(manifest.api_endpoints) == 1
    assert len(manifest.userdb_tables) == 1


def test_load_manifest_invalid_json(tmp_path: Path):
    bad_dir = tmp_path / "bad-module"
    bad_dir.mkdir()
    (bad_dir / "manifest.json").write_text("not valid json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        _load_manifest("bad-module", str(bad_dir))


def test_load_manifest_invalid_schema(tmp_path: Path):
    from pydantic import ValidationError
    bad_dir = tmp_path / "bad-module2"
    bad_dir.mkdir()
    (bad_dir / "manifest.json").write_text('{"name": "Bad Name With Spaces"}', encoding="utf-8")
    with pytest.raises(ValidationError):
        _load_manifest("bad-module2", str(bad_dir))


# ---------------------------------------------------------------------------
# Migration runner
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_module_migrations_creates_table(tmp_module: Path, db: UserDB):
    # Before migration: table does not exist
    tables_before = await db.table_names()
    assert "test_module_items" not in tables_before

    # First, register the module in installed_modules so last_migration can be updated
    await db.execute(
        "INSERT INTO installed_modules (name, version, installed_at, enabled, package_path) "
        "VALUES (?, ?, datetime('now'), 1, ?)",
        ["test-module", "0.1.0", str(tmp_module)],
    )

    await _run_module_migrations("test-module", str(tmp_module), db)

    # After migration: table exists
    tables_after = await db.table_names()
    assert "test_module_items" in tables_after


@pytest.mark.asyncio
async def test_run_module_migrations_idempotent(tmp_module: Path, db: UserDB):
    """Running migrations twice should not fail."""
    await db.execute(
        "INSERT INTO installed_modules (name, version, installed_at, enabled, package_path) "
        "VALUES (?, ?, datetime('now'), 1, ?)",
        ["test-module", "0.1.0", str(tmp_module)],
    )

    await _run_module_migrations("test-module", str(tmp_module), db)
    await _run_module_migrations("test-module", str(tmp_module), db)

    tables = await db.table_names()
    assert "test_module_items" in tables


@pytest.mark.asyncio
async def test_run_module_migrations_records_applied(tmp_module: Path, db: UserDB):
    await db.execute(
        "INSERT INTO installed_modules (name, version, installed_at, enabled, package_path) "
        "VALUES (?, ?, datetime('now'), 1, ?)",
        ["test-module", "0.1.0", str(tmp_module)],
    )
    await _run_module_migrations("test-module", str(tmp_module), db)

    record = await db.fetch_one(
        "SELECT * FROM module_migrations WHERE module_name = 'test-module'"
    )
    assert record is not None
    assert record["migration_id"] == "001_create_test_module_tables"


@pytest.mark.asyncio
async def test_migrations_skipped_when_no_dir(tmp_path: Path, db: UserDB):
    """A module with no migrations/ directory doesn't fail."""
    no_migrations_dir = tmp_path / "no-migrations"
    no_migrations_dir.mkdir()
    (no_migrations_dir / "manifest.json").write_text(
        json.dumps({
            "name": "no-migrations",
            "display_name": "No Migrations",
            "version": "0.1.0",
            "description": "x",
            "author": "x",
        }),
        encoding="utf-8",
    )
    await db.execute(
        "INSERT INTO installed_modules (name, version, installed_at, enabled, package_path) "
        "VALUES (?, ?, datetime('now'), 1, ?)",
        ["no-migrations", "0.1.0", str(no_migrations_dir)],
    )
    # Should not raise
    await _run_module_migrations("no-migrations", str(no_migrations_dir), db)


# ---------------------------------------------------------------------------
# ModuleRegistry
# ---------------------------------------------------------------------------


def test_registry_empty():
    reg = ModuleRegistry()
    assert reg.get_loaded() == []
    assert reg.get_failed() == []
    assert reg.is_loaded("anything") is False
    assert reg.get_module("anything") is None


def test_registry_add_loaded():
    reg = ModuleRegistry()
    manifest = ModuleManifest(
        name="my-module",
        display_name="My Module",
        version="1.0.0",
        description="x",
        author="x",
    )
    loaded = LoadedModule(name="my-module", manifest=manifest, package_path="/tmp/my-module")
    reg._add_loaded(loaded)
    assert reg.is_loaded("my-module") is True
    assert reg.get_module("my-module") is loaded
    assert len(reg.get_loaded()) == 1


def test_registry_add_failed():
    reg = ModuleRegistry()
    reg._add_failed("bad-module", "ImportError: no module named bad_module")
    assert not reg.is_loaded("bad-module")
    assert len(reg.get_failed()) == 1
    assert reg.get_failed()[0].name == "bad-module"


def test_registry_get_all_keywords():
    from backend.app.module_manifest import ModuleKeyword
    reg = ModuleRegistry()
    manifest = ModuleManifest(
        name="my-module",
        display_name="My Module",
        version="1.0.0",
        description="x",
        author="x",
        keywords=[ModuleKeyword(keyword="MY_MOD_", description="x", renderer="Widget")],
    )
    loaded = LoadedModule(name="my-module", manifest=manifest, package_path=None)
    reg._add_loaded(loaded)
    kws = reg.get_all_keywords()
    assert kws == {"MY_MOD_": "my-module"}


def test_registry_get_all_endpoints():
    from backend.app.module_manifest import ModuleEndpoint
    reg = ModuleRegistry()
    manifest = ModuleManifest(
        name="my-module",
        display_name="My Module",
        version="1.0.0",
        description="x",
        author="x",
        api_endpoints=[ModuleEndpoint(method="GET", path="/items", description="List items")],
    )
    loaded = LoadedModule(name="my-module", manifest=manifest, package_path=None)
    reg._add_loaded(loaded)
    endpoints = reg.get_all_endpoints()
    assert len(endpoints) == 1
    assert endpoints[0]["module_name"] == "my-module"
    assert endpoints[0]["method"] == "GET"


# ---------------------------------------------------------------------------
# load_modules — full integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_modules_full_lifecycle(tmp_module: Path, db: UserDB):
    """Full test: register module in DB, run load_modules, verify registry populated."""
    from fastapi import FastAPI

    await db.execute(
        "INSERT INTO installed_modules (name, version, installed_at, enabled, package_path) "
        "VALUES (?, ?, datetime('now'), 1, ?)",
        ["test-module", "0.1.0", str(tmp_module)],
    )

    app = FastAPI()
    registry = await load_modules(app, db)

    assert registry.is_loaded("test-module")
    loaded = registry.get_module("test-module")
    assert loaded is not None
    assert loaded.manifest.name == "test-module"
    assert loaded.router is not None

    # Migration ran
    tables = await db.table_names()
    assert "test_module_items" in tables

    # Router is mounted — check app routes include the module endpoint
    route_paths = [r.path for r in app.routes]  # type: ignore[union-attr]
    assert any("/modules/test-module" in p for p in route_paths)


@pytest.mark.asyncio
async def test_load_modules_failed_module_doesnt_crash(tmp_path: Path, db: UserDB):
    """A module with a broken backend shouldn't crash the Shell startup."""
    from fastapi import FastAPI

    # Create a module with invalid routes.py
    broken_dir = tmp_path / "broken-module"
    (broken_dir / "backend").mkdir(parents=True)
    (broken_dir / "manifest.json").write_text(
        json.dumps({
            "name": "broken-module",
            "display_name": "Broken Module",
            "version": "0.1.0",
            "description": "x",
            "author": "x",
            "has_backend": True,
        }),
        encoding="utf-8",
    )
    (broken_dir / "backend" / "routes.py").write_text(
        "raise RuntimeError('intentional failure')\n",
        encoding="utf-8",
    )

    await db.execute(
        "INSERT INTO installed_modules (name, version, installed_at, enabled, package_path) "
        "VALUES (?, ?, datetime('now'), 1, ?)",
        ["broken-module", "0.1.0", str(broken_dir)],
    )

    app = FastAPI()
    registry = await load_modules(app, db)

    # Shell continued; module is in failed list
    assert not registry.is_loaded("broken-module")
    assert len(registry.get_failed()) == 1
    assert "broken-module" in registry.get_failed()[0].name


@pytest.mark.asyncio
async def test_load_modules_disabled_skipped(tmp_module: Path, db: UserDB):
    """Disabled modules are not loaded."""
    from fastapi import FastAPI

    await db.execute(
        "INSERT INTO installed_modules (name, version, installed_at, enabled, package_path) "
        "VALUES (?, ?, datetime('now'), 0, ?)",  # enabled = 0
        ["test-module", "0.1.0", str(tmp_module)],
    )

    app = FastAPI()
    registry = await load_modules(app, db)

    assert not registry.is_loaded("test-module")
    assert len(registry.get_loaded()) == 0
    assert len(registry.get_failed()) == 0


@pytest.mark.asyncio
async def test_load_modules_no_modules(db: UserDB):
    from fastapi import FastAPI

    app = FastAPI()
    registry = await load_modules(app, db)
    assert len(registry.get_loaded()) == 0
    assert len(registry.get_failed()) == 0
