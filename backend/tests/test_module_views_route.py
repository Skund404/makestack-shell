"""Tests for GET /api/modules/{name}/views (Phase 8B)."""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from unittest.mock import MagicMock

from backend.app.module_loader import LoadedModule, ModuleRegistry
from backend.app.module_manifest import ModuleManifest, ModulePanel, ModuleView


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_loaded(
    name: str = "my-module",
    views: list[ModuleView] | None = None,
    panels: list[ModulePanel] | None = None,
) -> LoadedModule:
    manifest = ModuleManifest(
        name=name,
        display_name="My Module",
        version="1.0.0",
        description="x",
        author="x",
        views=views or [],
        panels=panels or [],
    )
    return LoadedModule(name=name, manifest=manifest, package_path=None)


# ---------------------------------------------------------------------------
# GET /api/modules/{name}/views
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_module_views_not_loaded_returns_404(client: AsyncClient):
    resp = await client.get("/api/modules/nonexistent-module/views")
    assert resp.status_code == 404
    assert "suggestion" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_module_views_empty_manifest(client: AsyncClient, test_app: FastAPI):
    loaded = _make_loaded("empty-module")
    test_app.state.module_registry.get_module = lambda name: loaded if name == "empty-module" else None

    resp = await client.get("/api/modules/empty-module/views")
    assert resp.status_code == 200
    body = resp.json()
    assert body["views"] == []
    assert body["panels"] == []


@pytest.mark.asyncio
async def test_module_views_returns_declared_views(client: AsyncClient, test_app: FastAPI):
    views = [
        ModuleView(id="dashboard", label="Dashboard", route="/modules/my-module/dashboard", icon="layout"),
        ModuleView(id="reports", label="Reports", route="/modules/my-module/reports", sort_order=10),
    ]
    loaded = _make_loaded("my-module", views=views)
    test_app.state.module_registry.get_module = lambda name: loaded if name == "my-module" else None

    resp = await client.get("/api/modules/my-module/views")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["views"]) == 2

    v = body["views"][0]
    assert v["id"] == "dashboard"
    assert v["label"] == "Dashboard"
    assert v["route"] == "/modules/my-module/dashboard"
    assert v["icon"] == "layout"
    assert v["replaces_shell_view"] is None
    assert v["sort_order"] == 0


@pytest.mark.asyncio
async def test_module_views_includes_replaces_shell_view(client: AsyncClient, test_app: FastAPI):
    views = [
        ModuleView(
            id="inv",
            label="My Inventory",
            route="/modules/my-module/inv",
            replaces_shell_view="inventory",
        ),
    ]
    loaded = _make_loaded("my-module", views=views)
    test_app.state.module_registry.get_module = lambda name: loaded if name == "my-module" else None

    resp = await client.get("/api/modules/my-module/views")
    assert resp.status_code == 200
    assert resp.json()["views"][0]["replaces_shell_view"] == "inventory"


@pytest.mark.asyncio
async def test_module_views_returns_declared_panels(client: AsyncClient, test_app: FastAPI):
    panels = [
        ModulePanel(id="stock-summary", label="Stock Summary", size="half"),
        ModulePanel(id="cost-overview", label="Cost Overview", size="full"),
    ]
    loaded = _make_loaded("my-module", panels=panels)
    test_app.state.module_registry.get_module = lambda name: loaded if name == "my-module" else None

    resp = await client.get("/api/modules/my-module/views")
    assert resp.status_code == 200
    pnls = resp.json()["panels"]
    assert len(pnls) == 2
    assert pnls[0]["id"] == "stock-summary"
    assert pnls[0]["size"] == "half"
    assert pnls[1]["size"] == "full"


# ---------------------------------------------------------------------------
# ModuleRegistry — get_all_views, get_module_views, get_module_panels
# ---------------------------------------------------------------------------


def test_registry_get_all_views_empty():
    reg = ModuleRegistry()
    assert reg.get_all_views() == []


def test_registry_get_module_views_not_loaded():
    reg = ModuleRegistry()
    assert reg.get_module_views("nonexistent") == []


def test_registry_get_module_panels_not_loaded():
    reg = ModuleRegistry()
    assert reg.get_module_panels("nonexistent") == []


def test_registry_get_all_views_with_views():
    reg = ModuleRegistry()
    views = [
        ModuleView(id="v1", label="V1", route="/a", sort_order=5),
        ModuleView(id="v2", label="V2", route="/b", sort_order=1),
    ]
    loaded = _make_loaded("mod-a", views=views)
    reg._add_loaded(loaded)

    all_views = reg.get_all_views()
    assert len(all_views) == 2
    # sorted by sort_order
    assert all_views[0]["id"] == "v2"
    assert all_views[1]["id"] == "v1"
    assert all_views[0]["module"] == "mod-a"


def test_registry_get_module_views_returns_views():
    reg = ModuleRegistry()
    views = [ModuleView(id="dash", label="Dashboard", route="/modules/x/dash")]
    loaded = _make_loaded("my-mod", views=views)
    reg._add_loaded(loaded)

    result = reg.get_module_views("my-mod")
    assert len(result) == 1
    assert result[0].id == "dash"


def test_registry_get_module_panels_returns_panels():
    reg = ModuleRegistry()
    panels = [ModulePanel(id="p1", label="Panel 1", size="third")]
    loaded = _make_loaded("my-mod", panels=panels)
    reg._add_loaded(loaded)

    result = reg.get_module_panels("my-mod")
    assert len(result) == 1
    assert result[0].id == "p1"
    assert result[0].size == "third"


def test_registry_shell_view_conflict_last_wins():
    """When two modules claim the same shell view, last-to-load wins."""
    reg = ModuleRegistry()

    views_a = [ModuleView(id="inv-a", label="Inv A", route="/a", replaces_shell_view="inventory")]
    views_b = [ModuleView(id="inv-b", label="Inv B", route="/b", replaces_shell_view="inventory")]

    reg._add_loaded(_make_loaded("mod-a", views=views_a))
    # Second module claims same shell view — last wins
    reg._add_loaded(_make_loaded("mod-b", views=views_b))

    assert reg._shell_view_claims["inventory"] == "mod-b"
    # Both modules are loaded
    assert reg.is_loaded("mod-a")
    assert reg.is_loaded("mod-b")


def test_registry_no_conflict_different_shell_views():
    reg = ModuleRegistry()
    views_a = [ModuleView(id="inv", label="Inv", route="/a", replaces_shell_view="inventory")]
    views_b = [ModuleView(id="cat", label="Cat", route="/b", replaces_shell_view="catalogue")]

    reg._add_loaded(_make_loaded("mod-a", views=views_a))
    reg._add_loaded(_make_loaded("mod-b", views=views_b))

    assert reg._shell_view_claims["inventory"] == "mod-a"
    assert reg._shell_view_claims["catalogue"] == "mod-b"
