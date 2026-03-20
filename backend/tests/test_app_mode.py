"""Tests for the standalone app mode feature.

Covers:
- ModuleAppMode manifest schema validation
- GET /api/modules/{name}/views — includes app_mode
- GET /api/workshops/{id}/modules — includes app_mode + display_name
- POST /api/workshops/{id}/add-app — bundled install + assign
- GET /api/packages/{name}/preview — dependency preview
"""

import pytest
from backend.app.module_manifest import (
    ModuleAppMode,
    ModuleAppNavItem,
    ModuleAppTheme,
    ModuleManifest,
)


# ---------------------------------------------------------------------------
# Manifest schema tests
# ---------------------------------------------------------------------------


class TestModuleAppModeSchema:
    """ModuleAppMode and sub-model validation."""

    def test_app_mode_defaults(self):
        mode = ModuleAppMode()
        assert mode.enabled is False
        assert mode.title == ""
        assert mode.nav_items == []
        assert mode.theme is None

    def test_app_mode_full(self):
        mode = ModuleAppMode(
            enabled=True,
            title="Kitchen",
            subtitle="Home module",
            sidebar_width=186,
            home_route="/kitchen",
            nav_items=[
                ModuleAppNavItem(
                    id="kitchen-home",
                    label="Home",
                    icon="Home",
                    route="/kitchen",
                ),
                ModuleAppNavItem(
                    id="kitchen-recipes",
                    label="Recipes",
                    icon="BookOpen",
                    route="/kitchen/recipes",
                    badge_endpoint="/modules/kitchen/recipes/count",
                ),
            ],
            theme=ModuleAppTheme(
                sidebar_bg="#15100b",
                sidebar_text="#eddec8",
                sidebar_active_bg="#271d12",
                accent="#c8935a",
            ),
        )
        assert mode.enabled is True
        assert len(mode.nav_items) == 2
        assert mode.nav_items[1].badge_endpoint == "/modules/kitchen/recipes/count"
        assert mode.theme.sidebar_bg == "#15100b"

    def test_nav_item_defaults(self):
        item = ModuleAppNavItem(id="x", label="X", route="/x")
        assert item.icon == ""
        assert item.badge_endpoint is None

    def test_theme_defaults(self):
        theme = ModuleAppTheme()
        assert theme.sidebar_bg == ""
        assert theme.accent == ""

    def test_manifest_with_app_mode(self):
        manifest = ModuleManifest(
            name="kitchen",
            display_name="Home Kitchen",
            version="0.1.0",
            description="Test",
            author="Test",
            app_mode=ModuleAppMode(
                enabled=True,
                title="Kitchen",
                home_route="/kitchen",
            ),
        )
        assert manifest.app_mode is not None
        assert manifest.app_mode.enabled is True
        assert manifest.app_mode.title == "Kitchen"

    def test_manifest_without_app_mode(self):
        manifest = ModuleManifest(
            name="inventory-stock",
            display_name="Inventory Stock",
            version="0.1.0",
            description="Test",
            author="Test",
        )
        assert manifest.app_mode is None

    def test_app_mode_serialization_round_trip(self):
        mode = ModuleAppMode(
            enabled=True,
            title="Kitchen",
            subtitle="Home module",
            home_route="/kitchen",
            nav_items=[
                ModuleAppNavItem(id="home", label="Home", icon="Home", route="/kitchen"),
            ],
            theme=ModuleAppTheme(sidebar_bg="#15100b"),
        )
        data = mode.model_dump()
        restored = ModuleAppMode.model_validate(data)
        assert restored.enabled is True
        assert restored.nav_items[0].id == "home"
        assert restored.theme.sidebar_bg == "#15100b"


# ---------------------------------------------------------------------------
# Route tests — require ASGI test client
# ---------------------------------------------------------------------------

import httpx
import pytest_asyncio
from httpx import ASGITransport

from backend.app.main import create_app
from backend.app.userdb import UserDB
from backend.app.dependencies import get_userdb


@pytest_asyncio.fixture
async def db():
    db = UserDB(":memory:", dev_mode=True)
    await db.open()
    await db.run_migrations()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def app(db):
    application = create_app()
    application.dependency_overrides[get_userdb] = lambda: db
    application.state.core_connected = True
    application.state.last_core_check = "2026-01-01T00:00:00Z"

    # Mock core client
    from unittest.mock import AsyncMock
    from backend.app.core_client import CatalogueClient

    mock_core = AsyncMock(spec=CatalogueClient)
    mock_core.cache_size = 0
    application.state.core_client = mock_core

    # Mock module registry with a fake kitchen module
    class FakeManifest:
        def __init__(self):
            self.views = []
            self.panels = []
            self.app_mode = ModuleAppMode(
                enabled=True,
                title="Kitchen",
                subtitle="Home module",
                sidebar_width=186,
                home_route="/kitchen",
                nav_items=[
                    ModuleAppNavItem(id="home", label="Home", icon="Home", route="/kitchen"),
                ],
                theme=ModuleAppTheme(sidebar_bg="#15100b", sidebar_text="#eddec8"),
            )
            self.display_name = "Home Kitchen"

        def model_dump(self):
            return {
                "name": "kitchen",
                "display_name": "Home Kitchen",
                "views": [],
                "panels": [],
                "app_mode": self.app_mode.model_dump(),
            }

    class FakeModule:
        def __init__(self):
            self.manifest = FakeManifest()

    class FakeRegistry:
        def get_module(self, name):
            if name == "kitchen":
                return FakeModule()
            return None

        def get_failed(self):
            return []

        def is_loaded(self, name):
            return name == "kitchen"

        def get_module_views(self, name):
            return []

    application.state.module_registry = FakeRegistry()
    return application


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestGetModuleViewsWithAppMode:
    """GET /api/modules/{name}/views includes app_mode when present."""

    @pytest.mark.asyncio
    async def test_views_response_includes_app_mode(self, client, db):
        # Install the module
        await db.execute(
            "INSERT INTO installed_modules (name, version, enabled, installed_at) VALUES (?, ?, 1, datetime('now'))",
            ["kitchen", "0.1.0"],
        )
        resp = await client.get("/api/modules/kitchen/views")
        assert resp.status_code == 200
        data = resp.json()
        assert "app_mode" in data
        assert data["app_mode"]["enabled"] is True
        assert data["app_mode"]["title"] == "Kitchen"
        assert data["app_mode"]["theme"]["sidebar_bg"] == "#15100b"

    @pytest.mark.asyncio
    async def test_views_response_without_app_mode(self, app, client, db):
        """Module without app_mode should not have the key in the response."""
        # Create a module without app_mode
        class PlainManifest:
            views = []
            panels = []
            app_mode = None
            display_name = "Plain Mod"
            def model_dump(self):
                return {"views": [], "panels": []}

        class PlainModule:
            manifest = PlainManifest()

        orig_get = app.state.module_registry.get_module
        def patched_get(name):
            if name == "plain-mod":
                return PlainModule()
            return orig_get(name)

        app.state.module_registry.get_module = patched_get

        await db.execute(
            "INSERT INTO installed_modules (name, version, enabled, installed_at) VALUES (?, ?, 1, datetime('now'))",
            ["plain-mod", "0.1.0"],
        )
        resp = await client.get("/api/modules/plain-mod/views")
        assert resp.status_code == 200
        data = resp.json()
        assert "app_mode" not in data


class TestWorkshopModulesWithAppMode:
    """GET /api/workshops/{id}/modules includes app_mode per module."""

    @pytest.mark.asyncio
    async def test_modules_response_includes_app_mode(self, client, db):
        # Create workshop + associate kitchen
        ws_resp = await client.post("/api/workshops", json={
            "name": "Home",
            "description": "Test workshop",
        })
        assert ws_resp.status_code == 201
        ws_id = ws_resp.json()["id"]

        await db.execute(
            "INSERT INTO installed_modules (name, version, enabled, installed_at) VALUES (?, ?, 1, datetime('now'))",
            ["kitchen", "0.1.0"],
        )
        await client.post(f"/api/workshops/{ws_id}/modules", json={
            "module_name": "kitchen",
            "sort_order": 0,
        })

        resp = await client.get(f"/api/workshops/{ws_id}/modules")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["module_name"] == "kitchen"
        assert "app_mode" in data[0]
        assert data[0]["app_mode"]["enabled"] is True
        assert data[0]["display_name"] == "Home Kitchen"


class TestAddAppEndpoint:
    """POST /api/workshops/{id}/add-app — assign already-installed module."""

    @pytest.mark.asyncio
    async def test_add_already_installed_module(self, client, db):
        # Create workshop
        ws_resp = await client.post("/api/workshops", json={"name": "Home"})
        ws_id = ws_resp.json()["id"]

        # Pre-install module
        await db.execute(
            "INSERT INTO installed_modules (name, version, enabled, installed_at) VALUES (?, ?, 1, datetime('now'))",
            ["kitchen", "0.1.0"],
        )

        # Add via add-app endpoint
        resp = await client.post(f"/api/workshops/{ws_id}/add-app", json={
            "package_name": "kitchen",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["package_name"] == "kitchen"
        assert "kitchen" in data["assigned"]
        assert data["restart_required"] is False

    @pytest.mark.asyncio
    async def test_add_already_assigned_module(self, client, db):
        """Adding an already-assigned module should succeed idempotently."""
        ws_resp = await client.post("/api/workshops", json={"name": "Home"})
        ws_id = ws_resp.json()["id"]

        await db.execute(
            "INSERT INTO installed_modules (name, version, enabled, installed_at) VALUES (?, ?, 1, datetime('now'))",
            ["kitchen", "0.1.0"],
        )

        # First add
        resp1 = await client.post(f"/api/workshops/{ws_id}/add-app", json={
            "package_name": "kitchen",
        })
        assert resp1.status_code == 201
        assert "kitchen" in resp1.json()["assigned"]

        # Second add — should succeed but not reassign
        resp2 = await client.post(f"/api/workshops/{ws_id}/add-app", json={
            "package_name": "kitchen",
        })
        assert resp2.status_code == 201
        assert resp2.json()["assigned"] == []  # Already assigned

    @pytest.mark.asyncio
    async def test_add_app_to_nonexistent_workshop(self, client, db):
        resp = await client.post("/api/workshops/nonexistent/add-app", json={
            "package_name": "kitchen",
        })
        assert resp.status_code == 404
