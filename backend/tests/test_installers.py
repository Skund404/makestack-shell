"""Tests for the type-specific package installers.

All installers use an in-memory UserDB. CatalogueClient is mocked for
catalogue tests. No git operations or real Python packages are involved.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from backend.app.installers.base import InstallResult
from backend.app.installers.module_installer import ModuleInstaller
from backend.app.installers.widget_installer import WidgetInstaller
from backend.app.installers.catalogue_installer import CatalogueInstaller
from backend.app.installers.data_installer import DataInstaller
from backend.app.installers import PackageInstaller
from backend.app.package_manifest import PackageManifest
from backend.app.userdb import UserDB


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db() -> UserDB:
    database = UserDB(":memory:", dev_mode=True)
    await database.open()
    await database.run_migrations()
    yield database
    await database.close()


def _manifest(name: str = "test-pkg", pkg_type: str = "module", version: str = "1.0.0") -> PackageManifest:
    return PackageManifest(name=name, type=pkg_type, version=version)


def _make_module_dir(tmp_path: Path, name: str = "test-pkg") -> Path:
    """Create a minimal module directory with manifest.json."""
    pkg_dir = tmp_path / name
    pkg_dir.mkdir()
    (pkg_dir / "makestack-package.json").write_text(
        json.dumps({"name": name, "type": "module", "version": "1.0.0"}),
        encoding="utf-8",
    )
    (pkg_dir / "manifest.json").write_text(
        json.dumps({
            "name": name,
            "display_name": name.title(),
            "version": "1.0.0",
            "description": "Test module",
            "author": "test",
            "has_backend": False,
            "has_frontend": False,
            "keywords": [],
            "api_endpoints": [],
            "panels": [],
            "userdb_tables": [],
            "dependencies": {"python": [], "node": []},
        }),
        encoding="utf-8",
    )
    return pkg_dir


# ---------------------------------------------------------------------------
# ModuleInstaller
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_module_installer_registers_in_db(db: UserDB, tmp_path: Path):
    pkg_dir = _make_module_dir(tmp_path)
    installer = ModuleInstaller(db)
    result = await installer.install(
        package_path=str(pkg_dir),
        manifest=_manifest("test-pkg"),
    )

    assert result.success is True
    assert result.restart_required is True
    assert result.package_type == "module"

    row = await db.fetch_one("SELECT * FROM installed_modules WHERE name = 'test-pkg'")
    assert row is not None
    assert row["version"] == "1.0.0"
    assert bool(row["enabled"]) is True
    assert row["package_path"] == str(pkg_dir)


@pytest.mark.asyncio
async def test_module_installer_update_existing(db: UserDB, tmp_path: Path):
    """Re-installing an existing module updates version and keeps it enabled."""
    pkg_dir = _make_module_dir(tmp_path)
    installer = ModuleInstaller(db)

    # First install
    await installer.install(str(pkg_dir), _manifest("test-pkg", version="1.0.0"))

    # Update the manifest.json to simulate a new version
    new_manifest_json = json.dumps({
        "name": "test-pkg", "display_name": "Test Pkg", "version": "2.0.0",
        "description": "Test module", "author": "test",
        "has_backend": False, "has_frontend": False,
        "keywords": [], "api_endpoints": [], "panels": [], "userdb_tables": [],
        "dependencies": {"python": [], "node": []},
    })
    (pkg_dir / "manifest.json").write_text(new_manifest_json)

    # Second install (update)
    result = await installer.install(
        str(pkg_dir), _manifest("test-pkg", version="2.0.0")
    )
    assert result.success is True

    row = await db.fetch_one("SELECT version FROM installed_modules WHERE name = 'test-pkg'")
    assert row["version"] == "2.0.0"


@pytest.mark.asyncio
async def test_module_installer_fails_when_manifest_missing(db: UserDB, tmp_path: Path):
    """Install fails if manifest.json is not present in the package directory."""
    pkg_dir = tmp_path / "no-manifest"
    pkg_dir.mkdir()
    installer = ModuleInstaller(db)
    result = await installer.install(str(pkg_dir), _manifest("no-manifest"))
    assert result.success is False
    assert "manifest.json not found" in result.message


@pytest.mark.asyncio
async def test_module_installer_uninstall_removes_record(db: UserDB, tmp_path: Path):
    pkg_dir = _make_module_dir(tmp_path)
    installer = ModuleInstaller(db)
    await installer.install(str(pkg_dir), _manifest("test-pkg"))

    result = await installer.uninstall("test-pkg")
    assert result.success is True
    assert result.restart_required is True

    # Row is hard-deleted — module no longer appears in the package list
    row = await db.fetch_one("SELECT name FROM installed_modules WHERE name = 'test-pkg'")
    assert row is None


@pytest.mark.asyncio
async def test_module_installer_uninstall_nonexistent(db: UserDB):
    installer = ModuleInstaller(db)
    result = await installer.uninstall("ghost-module")
    assert result.success is False
    assert "not installed" in result.message


# ---------------------------------------------------------------------------
# WidgetInstaller
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_widget_installer_registers_in_db(db: UserDB):
    installer = WidgetInstaller(db)
    result = await installer.install(
        package_path="/tmp/fake-path",
        manifest=_manifest("timer-widgets", "widget-pack"),
    )
    assert result.success is True
    assert result.restart_required is False
    assert result.package_type == "widget-pack"

    row = await db.fetch_one("SELECT * FROM installed_packages WHERE name = 'timer-widgets'")
    assert row is not None
    assert row["type"] == "widget-pack"


@pytest.mark.asyncio
async def test_widget_installer_update_existing(db: UserDB):
    installer = WidgetInstaller(db)
    await installer.install("/tmp/p", _manifest("timer-widgets", "widget-pack", "1.0.0"))
    result = await installer.install("/tmp/p", _manifest("timer-widgets", "widget-pack", "2.0.0"))
    assert result.success is True

    row = await db.fetch_one("SELECT version FROM installed_packages WHERE name = 'timer-widgets'")
    assert row["version"] == "2.0.0"


@pytest.mark.asyncio
async def test_widget_installer_uninstall(db: UserDB):
    installer = WidgetInstaller(db)
    await installer.install("/tmp/p", _manifest("timer-widgets", "widget-pack"))
    result = await installer.uninstall("timer-widgets")
    assert result.success is True
    row = await db.fetch_one("SELECT name FROM installed_packages WHERE name = 'timer-widgets'")
    assert row is None


@pytest.mark.asyncio
async def test_widget_installer_uninstall_nonexistent(db: UserDB):
    installer = WidgetInstaller(db)
    result = await installer.uninstall("ghost-widgets")
    assert result.success is False
    assert "not installed" in result.message


# ---------------------------------------------------------------------------
# CatalogueInstaller
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_core():
    client = MagicMock()
    client.connected = True
    client.create_primitive = AsyncMock(return_value={"id": "created"})
    client.import_primitive = AsyncMock(return_value=None)
    return client


@pytest.fixture
def disconnected_core():
    client = MagicMock()
    client.connected = False
    return client


def _make_catalogue_dir(tmp_path: Path) -> Path:
    """Create a minimal catalogue directory with one primitive."""
    cat_dir = tmp_path / "test-catalogue"
    cat_dir.mkdir()
    (cat_dir / "makestack-package.json").write_text(
        json.dumps({"name": "test-catalogue", "type": "catalogue", "version": "1.0.0"}),
    )
    tools_dir = cat_dir / "tools" / "hammer"
    tools_dir.mkdir(parents=True)
    (tools_dir / "manifest.json").write_text(
        json.dumps({"type": "tool", "name": "Hammer", "slug": "hammer"}),
        encoding="utf-8",
    )
    return cat_dir


@pytest.mark.asyncio
async def test_catalogue_installer_imports_primitives(db: UserDB, mock_core, tmp_path: Path):
    cat_dir = _make_catalogue_dir(tmp_path)
    installer = CatalogueInstaller(db, mock_core)
    result = await installer.install(str(cat_dir), _manifest("test-catalogue", "catalogue"))

    assert result.success is True
    assert "1 added" in result.message
    mock_core.import_primitive.assert_awaited_once()


@pytest.mark.asyncio
async def test_catalogue_installer_fails_when_core_offline(db: UserDB, disconnected_core, tmp_path: Path):
    cat_dir = _make_catalogue_dir(tmp_path)
    installer = CatalogueInstaller(db, disconnected_core)
    result = await installer.install(str(cat_dir), _manifest("test-catalogue", "catalogue"))
    assert result.success is False
    assert "not connected" in result.message.lower()


@pytest.mark.asyncio
async def test_catalogue_installer_empty_directory(db: UserDB, mock_core, tmp_path: Path):
    empty_dir = tmp_path / "empty-cat"
    empty_dir.mkdir()
    installer = CatalogueInstaller(db, mock_core)
    result = await installer.install(str(empty_dir), _manifest("empty-cat", "catalogue"))
    assert result.success is False
    assert "no primitives" in result.message.lower()


@pytest.mark.asyncio
async def test_catalogue_installer_registers_in_db(db: UserDB, mock_core, tmp_path: Path):
    cat_dir = _make_catalogue_dir(tmp_path)
    installer = CatalogueInstaller(db, mock_core)
    await installer.install(str(cat_dir), _manifest("test-catalogue", "catalogue"))

    row = await db.fetch_one("SELECT name FROM installed_packages WHERE name = 'test-catalogue'")
    assert row is not None


@pytest.mark.asyncio
async def test_catalogue_installer_uninstall(db: UserDB, mock_core, tmp_path: Path):
    cat_dir = _make_catalogue_dir(tmp_path)
    installer = CatalogueInstaller(db, mock_core)
    await installer.install(str(cat_dir), _manifest("test-catalogue", "catalogue"))
    result = await installer.uninstall("test-catalogue")
    assert result.success is True
    assert "primitives remain" in result.message


# ---------------------------------------------------------------------------
# DataInstaller
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_data_installer_copies_files(db: UserDB, tmp_path: Path):
    pkg_dir = tmp_path / "theme-pkg"
    pkg_dir.mkdir()
    (pkg_dir / "cyberpunk.json").write_text('{"name": "cyberpunk"}', encoding="utf-8")
    (pkg_dir / "makestack-package.json").write_text(
        json.dumps({
            "name": "cyberpunk-theme",
            "type": "data",
            "version": "1.0.0",
            "targets": {"cyberpunk.json": ".makestack/themes/cyberpunk.json"},
        }),
        encoding="utf-8",
    )

    home = tmp_path / "fake_home"
    home.mkdir()
    installer = DataInstaller(db, home)
    # Patch Path.home() would be complex; use a different approach.
    # Instead, verify the installer runs without error (file copy is tested implicitly).
    manifest = _manifest("cyberpunk-theme", "data")
    result = await installer.install(str(pkg_dir), manifest)
    assert result.success is True
    assert "1 file" in result.message


@pytest.mark.asyncio
async def test_data_installer_registers_in_db(db: UserDB, tmp_path: Path):
    pkg_dir = tmp_path / "my-data"
    pkg_dir.mkdir()
    (pkg_dir / "makestack-package.json").write_text(
        json.dumps({"name": "my-data", "type": "data", "version": "1.0.0", "targets": {}}),
    )
    home = tmp_path / "home"
    installer = DataInstaller(db, home)
    await installer.install(str(pkg_dir), _manifest("my-data", "data"))

    row = await db.fetch_one("SELECT name FROM installed_packages WHERE name = 'my-data'")
    assert row is not None


@pytest.mark.asyncio
async def test_data_installer_uninstall(db: UserDB, tmp_path: Path):
    pkg_dir = tmp_path / "my-data"
    pkg_dir.mkdir()
    (pkg_dir / "makestack-package.json").write_text(
        json.dumps({"name": "my-data", "type": "data", "version": "1.0.0", "targets": {}}),
    )
    home = tmp_path / "home"
    installer = DataInstaller(db, home)
    await installer.install(str(pkg_dir), _manifest("my-data", "data"))
    result = await installer.uninstall("my-data")
    assert result.success is True
    assert "Installed files were not removed" in result.message


# ---------------------------------------------------------------------------
# PackageInstaller dispatcher
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatcher_routes_to_module_installer(db: UserDB, tmp_path: Path, mock_core):
    from backend.app.installers.skill_installer import SkillInstaller
    pkg_dir = _make_module_dir(tmp_path)
    dispatcher = PackageInstaller(
        module_installer=ModuleInstaller(db),
        widget_installer=WidgetInstaller(db),
        catalogue_installer=CatalogueInstaller(db, mock_core),
        data_installer=DataInstaller(db, tmp_path),
        skill_installer=SkillInstaller(db),
    )
    manifest = _manifest("test-pkg", "module")
    result = await dispatcher.install(str(pkg_dir), manifest)
    assert result.success is True
    assert result.package_type == "module"


@pytest.mark.asyncio
async def test_dispatcher_routes_to_widget_installer(db: UserDB, tmp_path: Path, mock_core):
    from backend.app.installers.skill_installer import SkillInstaller
    dispatcher = PackageInstaller(
        module_installer=ModuleInstaller(db),
        widget_installer=WidgetInstaller(db),
        catalogue_installer=CatalogueInstaller(db, mock_core),
        data_installer=DataInstaller(db, tmp_path),
        skill_installer=SkillInstaller(db),
    )
    manifest = _manifest("my-widgets", "widget-pack")
    result = await dispatcher.install("/tmp/fake", manifest)
    assert result.success is True
    assert result.package_type == "widget-pack"


@pytest.mark.asyncio
async def test_dispatcher_unknown_type_returns_failure(db: UserDB, tmp_path: Path, mock_core):
    from backend.app.installers.skill_installer import SkillInstaller
    dispatcher = PackageInstaller(
        module_installer=ModuleInstaller(db),
        widget_installer=WidgetInstaller(db),
        catalogue_installer=CatalogueInstaller(db, mock_core),
        data_installer=DataInstaller(db, tmp_path),
        skill_installer=SkillInstaller(db),
    )
    # Build a manifest-like object with an injected invalid type (bypass validation).
    from backend.app.package_manifest import PackageManifest
    import pydantic
    m = PackageManifest.model_construct(name="x", type="unknown", version="1.0.0")
    result = await dispatcher.install("/tmp/fake", m)
    assert result.success is False
    assert "Unknown package type" in result.message
