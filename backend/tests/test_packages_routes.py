"""Tests for the /api/packages and /api/registries routes.

Uses the real test_app fixture (in-memory UserDB, mocked Core) and injects
mocked registry_client / package_cache / installer onto app.state.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.installers.base import InstallResult
from backend.app.package_manifest import PackageManifest


# ---------------------------------------------------------------------------
# Helpers for building a test app with injected services
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client(test_app: FastAPI, tmp_path: Path):
    """Extend the shared test_app with mocked package manager services."""
    # Mock registry client
    registry = MagicMock()
    registry.resolve = MagicMock(return_value=None)
    registry.search = MagicMock(return_value=[])
    registry.count_packages = MagicMock(return_value=0)
    registry.registry_is_cloned = MagicMock(return_value=False)
    registry.clone_registry = AsyncMock()
    registry.remove_registry = MagicMock()
    registry.refresh_all = AsyncMock(return_value={})
    test_app.state.registry_client = registry

    # Mock package cache
    cache = MagicMock()
    cache.fetch = AsyncMock(return_value=tmp_path / "packages" / "modules" / "test-pkg")
    cache.get_cached_path = MagicMock(return_value=None)
    cache.remove = MagicMock()
    test_app.state.package_cache = cache

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, test_app


# ---------------------------------------------------------------------------
# GET /api/packages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_packages_empty(client):
    ac, _ = client
    resp = await ac.get("/api/packages")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_packages_shows_modules(client, db):
    ac, _ = client
    # Insert a module directly into the DB
    await db.execute(
        "INSERT INTO installed_modules (name, version, installed_at, enabled) VALUES (?, ?, datetime('now'), 1)",
        ["my-module", "1.0.0"],
    )
    resp = await ac.get("/api/packages")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "my-module"
    assert data["items"][0]["type"] == "module"


@pytest.mark.asyncio
async def test_list_packages_shows_non_module_packages(client, db):
    ac, _ = client
    await db.execute(
        "INSERT INTO installed_packages (name, type, version, installed_at) VALUES (?, ?, ?, datetime('now'))",
        ["timer-widgets", "widget-pack", "1.0.0"],
    )
    resp = await ac.get("/api/packages")
    assert resp.status_code == 200
    data = resp.json()
    assert any(p["name"] == "timer-widgets" for p in data["items"])


# ---------------------------------------------------------------------------
# POST /api/packages/install
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_requires_name_or_source(client):
    ac, _ = client
    resp = await ac.post("/api/packages/install", json={})
    assert resp.status_code == 422
    assert "name" in resp.text or "source" in resp.text


@pytest.mark.asyncio
async def test_install_by_name_not_in_registry_returns_404(client):
    ac, app = client
    app.state.registry_client.resolve = MagicMock(return_value=None)
    resp = await ac.post("/api/packages/install", json={"name": "unknown-pkg"})
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]["error"].lower()


@pytest.mark.asyncio
async def test_install_by_name_resolves_from_registry(client, tmp_path: Path):
    ac, app = client
    # Create a minimal module directory that the installer can inspect.
    pkg_dir = tmp_path / "packages" / "modules" / "my-module"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "makestack-package.json").write_text(
        json.dumps({"name": "my-module", "type": "module", "version": "1.0.0"}),
    )
    (pkg_dir / "manifest.json").write_text(
        json.dumps({"name": "my-module", "version": "1.0.0", "has_backend": False,
                    "has_frontend": False, "keywords": [], "api_endpoints": [],
                    "panels": [], "userdb_tables": [], "dependencies": {"python": [], "node": []},
                    "display_name": "My Module", "description": "", "author": "",
                    "shell_compatibility": "", "license": ""}),
    )

    from backend.app.registry_client import PackageInfo
    app.state.registry_client.resolve = MagicMock(return_value=PackageInfo(
        name="my-module",
        git_url="https://example.com/my-module.git",
        type="module",
        registry_name="official",
    ))
    app.state.package_cache.fetch = AsyncMock(return_value=pkg_dir)

    resp = await ac.post("/api/packages/install", json={"name": "my-module"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["package_name"] == "my-module"
    assert data["success"] is True
    assert data["restart_required"] is True


@pytest.mark.asyncio
async def test_install_from_local_path(client, tmp_path: Path):
    ac, app = client
    # Create a local widget-pack
    pkg_dir = tmp_path / "local-widgets"
    pkg_dir.mkdir()
    (pkg_dir / "makestack-package.json").write_text(
        json.dumps({"name": "local-widgets", "type": "widget-pack", "version": "0.1.0"}),
    )

    resp = await ac.post("/api/packages/install", json={"source": str(pkg_dir)})
    assert resp.status_code == 201
    data = resp.json()
    assert data["package_type"] == "widget-pack"
    assert data["restart_required"] is False


@pytest.mark.asyncio
async def test_install_from_invalid_local_path(client):
    ac, _ = client
    resp = await ac.post("/api/packages/install", json={"source": "/nonexistent/path"})
    assert resp.status_code == 422
    assert "not found" in resp.json()["detail"]["error"].lower()


# ---------------------------------------------------------------------------
# DELETE /api/packages/{name}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_uninstall_not_installed_returns_404(client):
    ac, _ = client
    resp = await ac.delete("/api/packages/ghost-pkg")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_uninstall_module(client, db):
    ac, _ = client
    await db.execute(
        "INSERT INTO installed_modules (name, version, installed_at, enabled) VALUES (?, ?, datetime('now'), 1)",
        ["my-module", "1.0.0"],
    )
    resp = await ac.delete("/api/packages/my-module")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["restart_required"] is True


@pytest.mark.asyncio
async def test_uninstall_widget_pack(client, db):
    ac, _ = client
    await db.execute(
        "INSERT INTO installed_packages (name, type, version, installed_at) VALUES (?, ?, ?, datetime('now'))",
        ["timer-widgets", "widget-pack", "1.0.0"],
    )
    resp = await ac.delete("/api/packages/timer-widgets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["restart_required"] is False


# ---------------------------------------------------------------------------
# GET /api/packages/search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_without_q_lists_all(client):
    ac, _ = client
    resp = await ac.get("/api/packages/search")
    assert resp.status_code == 200
    assert "items" in resp.json()


@pytest.mark.asyncio
async def test_search_returns_results(client):
    ac, app = client
    from backend.app.registry_client import PackageInfo
    app.state.registry_client.search = MagicMock(return_value=[
        PackageInfo(name="inventory-stock", git_url="https://x.com", type="module",
                    description="Stock tracker", registry_name="official"),
    ])
    resp = await ac.get("/api/packages/search", params={"q": "inventory"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "inventory-stock"


@pytest.mark.asyncio
async def test_search_no_results(client):
    ac, _ = client
    resp = await ac.get("/api/packages/search", params={"q": "xyzzy"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# GET /api/registries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_registries_empty(client):
    ac, _ = client
    resp = await ac.get("/api/registries")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_registries_shows_configured(client, db):
    ac, _ = client
    await db.execute(
        "INSERT INTO installed_registries (name, git_url, added_at) VALUES (?, ?, datetime('now'))",
        ["official", "https://github.com/makestack/registry"],
    )
    resp = await ac.get("/api/registries")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "official"


# ---------------------------------------------------------------------------
# POST /api/registries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_registry(client):
    ac, app = client
    app.state.registry_client.clone_registry = AsyncMock()
    app.state.registry_client.count_packages = MagicMock(return_value=5)

    resp = await ac.post("/api/registries", json={
        "name": "official",
        "git_url": "https://github.com/makestack/registry",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "official"
    assert data["package_count"] == 5


@pytest.mark.asyncio
async def test_add_registry_duplicate_returns_409(client, db):
    ac, _ = client
    await db.execute(
        "INSERT INTO installed_registries (name, git_url, added_at) VALUES (?, ?, datetime('now'))",
        ["official", "https://github.com/makestack/registry"],
    )
    resp = await ac.post("/api/registries", json={
        "name": "official",
        "git_url": "https://github.com/makestack/registry",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_add_registry_clone_failure_returns_422(client):
    ac, app = client
    app.state.registry_client.clone_registry = AsyncMock(
        side_effect=RuntimeError("git clone failed")
    )
    resp = await ac.post("/api/registries", json={
        "name": "broken",
        "git_url": "https://invalid.example.com/reg.git",
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/registries/{name}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_registry(client, db):
    ac, _ = client
    await db.execute(
        "INSERT INTO installed_registries (name, git_url, added_at) VALUES (?, ?, datetime('now'))",
        ["official", "https://github.com/makestack/registry"],
    )
    resp = await ac.delete("/api/registries/official")
    assert resp.status_code == 200
    assert resp.json()["removed"] == "official"


@pytest.mark.asyncio
async def test_remove_registry_not_found(client):
    ac, _ = client
    resp = await ac.delete("/api/registries/ghost")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/registries/refresh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_registries_empty(client):
    ac, _ = client
    resp = await ac.post("/api/registries/refresh")
    assert resp.status_code == 200
    data = resp.json()
    assert data["refreshed"] == []
    assert data["errors"] == {}


@pytest.mark.asyncio
async def test_refresh_registries_success(client, db):
    ac, app = client
    await db.execute(
        "INSERT INTO installed_registries (name, git_url, added_at) VALUES (?, ?, datetime('now'))",
        ["official", "https://github.com/makestack/registry"],
    )
    app.state.registry_client.refresh_all = AsyncMock(return_value={"official": None})

    resp = await ac.post("/api/registries/refresh")
    assert resp.status_code == 200
    data = resp.json()
    assert "official" in data["refreshed"]
    assert data["errors"] == {}


@pytest.mark.asyncio
async def test_refresh_registries_with_error(client, db):
    ac, app = client
    await db.execute(
        "INSERT INTO installed_registries (name, git_url, added_at) VALUES (?, ?, datetime('now'))",
        ["broken", "https://broken.example.com"],
    )
    app.state.registry_client.refresh_all = AsyncMock(
        return_value={"broken": "git pull failed"}
    )

    resp = await ac.post("/api/registries/refresh")
    assert resp.status_code == 200
    data = resp.json()
    assert data["refreshed"] == []
    assert "broken" in data["errors"]
