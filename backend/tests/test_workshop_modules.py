"""Tests for workshop-module association endpoints (Phase 8A + 8B)."""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from unittest.mock import MagicMock

from backend.app.module_manifest import ModuleAppMode, ModuleManifest, ModuleView
from backend.app.module_loader import LoadedModule


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_workshop(client: AsyncClient, name: str = "Test Workshop") -> str:
    resp = await client.post("/api/workshops", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# GET /api/workshops/{id}/modules — list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_workshop_modules_empty(client: AsyncClient):
    ws_id = await _create_workshop(client)
    resp = await client.get(f"/api/workshops/{ws_id}/modules")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_workshop_modules_returns_associated(client: AsyncClient):
    ws_id = await _create_workshop(client)
    await client.post(f"/api/workshops/{ws_id}/modules", json={"module_name": "inventory-stock"})
    await client.post(f"/api/workshops/{ws_id}/modules", json={"module_name": "cost-tracker"})

    resp = await client.get(f"/api/workshops/{ws_id}/modules")
    assert resp.status_code == 200
    names = [m["module_name"] for m in resp.json()]
    assert "inventory-stock" in names
    assert "cost-tracker" in names


@pytest.mark.asyncio
async def test_list_workshop_modules_404_unknown_workshop(client: AsyncClient):
    resp = await client.get("/api/workshops/nonexistent-id/modules")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/workshops/{id}/modules — add association
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_module_to_workshop(client: AsyncClient):
    ws_id = await _create_workshop(client)
    resp = await client.post(
        f"/api/workshops/{ws_id}/modules",
        json={"module_name": "inventory-stock"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["workshop_id"] == ws_id
    assert body["module_name"] == "inventory-stock"
    assert body["sort_order"] == 0
    assert body["enabled"] is True


@pytest.mark.asyncio
async def test_add_module_with_sort_order(client: AsyncClient):
    ws_id = await _create_workshop(client)
    resp = await client.post(
        f"/api/workshops/{ws_id}/modules",
        json={"module_name": "cost-tracker", "sort_order": 5},
    )
    assert resp.status_code == 201
    assert resp.json()["sort_order"] == 5


@pytest.mark.asyncio
async def test_add_module_idempotent(client: AsyncClient):
    """Adding the same module twice returns the existing association without error."""
    ws_id = await _create_workshop(client)
    payload = {"module_name": "inventory-stock"}

    resp1 = await client.post(f"/api/workshops/{ws_id}/modules", json=payload)
    resp2 = await client.post(f"/api/workshops/{ws_id}/modules", json=payload)

    assert resp1.status_code == 201
    assert resp2.status_code == 201
    assert resp1.json()["module_name"] == resp2.json()["module_name"]

    # Confirm only one row in DB
    list_resp = await client.get(f"/api/workshops/{ws_id}/modules")
    assert len(list_resp.json()) == 1


@pytest.mark.asyncio
async def test_add_module_404_unknown_workshop(client: AsyncClient):
    resp = await client.post(
        "/api/workshops/nonexistent-id/modules",
        json={"module_name": "inventory-stock"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/workshops/{id}/modules/{name} — remove association
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_module_from_workshop(client: AsyncClient):
    ws_id = await _create_workshop(client)
    await client.post(f"/api/workshops/{ws_id}/modules", json={"module_name": "inventory-stock"})

    del_resp = await client.delete(f"/api/workshops/{ws_id}/modules/inventory-stock")
    assert del_resp.status_code == 204

    list_resp = await client.get(f"/api/workshops/{ws_id}/modules")
    assert list_resp.json() == []


@pytest.mark.asyncio
async def test_remove_module_404_not_associated(client: AsyncClient):
    ws_id = await _create_workshop(client)
    resp = await client.delete(f"/api/workshops/{ws_id}/modules/nonexistent-module")
    assert resp.status_code == 404
    assert "suggestion" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_remove_module_404_unknown_workshop(client: AsyncClient):
    resp = await client.delete("/api/workshops/nonexistent-id/modules/some-module")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_workshop_cascades_module_associations(client: AsyncClient):
    """Deleting a workshop removes its module associations via CASCADE."""
    ws_id = await _create_workshop(client)
    await client.post(f"/api/workshops/{ws_id}/modules", json={"module_name": "inventory-stock"})

    del_resp = await client.delete(f"/api/workshops/{ws_id}")
    assert del_resp.status_code == 204

    # Workshop is gone — module association should be gone too (CASCADE)
    get_resp = await client.get(f"/api/workshops/{ws_id}")
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/workshops/{id}/nav — intersection rule
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nav_shell_fallbacks_always_present(client: AsyncClient):
    """Shell fallback views appear in nav even with no module associations."""
    ws_id = await _create_workshop(client)
    resp = await client.get(f"/api/workshops/{ws_id}/nav")
    assert resp.status_code == 200

    ids = [item["id"] for item in resp.json()["items"]]
    assert "inventory" in ids
    assert "catalogue" in ids
    assert "workshops" in ids

    sources = {item["id"]: item["source"] for item in resp.json()["items"]}
    assert sources["inventory"] == "shell"
    assert sources["catalogue"] == "shell"
    assert sources["workshops"] == "shell"


@pytest.mark.asyncio
async def test_nav_module_absent_when_not_loaded(client: AsyncClient):
    """Module in DB but not in module_registry is silently absent from nav."""
    ws_id = await _create_workshop(client)
    await client.post(f"/api/workshops/{ws_id}/modules", json={"module_name": "inventory-stock"})

    # Default mock registry returns is_loaded=False for everything
    resp = await client.get(f"/api/workshops/{ws_id}/nav")
    assert resp.status_code == 200

    ids = [item["id"] for item in resp.json()["items"]]
    assert "inventory-stock" not in ids
    # Shell fallbacks still present
    assert "inventory" in ids


@pytest.mark.asyncio
async def test_nav_module_present_when_loaded_and_associated(
    client: AsyncClient, test_app: FastAPI
):
    """Module in DB AND loaded in registry appears in nav."""
    ws_id = await _create_workshop(client)
    await client.post(f"/api/workshops/{ws_id}/modules", json={"module_name": "inventory-stock"})

    # Make the module appear as loaded
    test_app.state.module_registry.is_loaded = lambda name: name == "inventory-stock"

    resp = await client.get(f"/api/workshops/{ws_id}/nav")
    assert resp.status_code == 200

    items = resp.json()["items"]
    module_items = [i for i in items if i["source"] == "module"]
    assert len(module_items) == 1
    assert module_items[0]["id"] == "inventory-stock"
    assert module_items[0]["route"] == "/modules/inventory-stock"


@pytest.mark.asyncio
async def test_nav_module_absent_when_loaded_but_not_associated(
    client: AsyncClient, test_app: FastAPI
):
    """Module loaded in registry but NOT associated with workshop is absent from nav."""
    ws_id = await _create_workshop(client)
    # No module association added

    # Make the module appear as loaded
    test_app.state.module_registry.is_loaded = lambda name: name == "inventory-stock"

    resp = await client.get(f"/api/workshops/{ws_id}/nav")
    assert resp.status_code == 200

    ids = [item["id"] for item in resp.json()["items"]]
    assert "inventory-stock" not in ids


@pytest.mark.asyncio
async def test_nav_association_row_not_deleted_when_module_absent(client: AsyncClient):
    """Nav computation never removes association rows — intersection is read-only."""
    ws_id = await _create_workshop(client)
    await client.post(f"/api/workshops/{ws_id}/modules", json={"module_name": "inventory-stock"})

    # Module not loaded — it will be absent from nav
    await client.get(f"/api/workshops/{ws_id}/nav")

    # The association row must still exist
    list_resp = await client.get(f"/api/workshops/{ws_id}/modules")
    names = [m["module_name"] for m in list_resp.json()]
    assert "inventory-stock" in names


@pytest.mark.asyncio
async def test_nav_disabled_module_excluded(client: AsyncClient, test_app: FastAPI):
    """Disabled module associations (enabled=0) are excluded from nav even if loaded."""
    ws_id = await _create_workshop(client)
    await client.post(f"/api/workshops/{ws_id}/modules", json={"module_name": "inventory-stock"})

    # Manually disable the association in the DB
    from backend.app.dependencies import get_userdb
    db = test_app.dependency_overrides[get_userdb]()
    await db.execute(
        "UPDATE workshop_modules SET enabled = 0 WHERE workshop_id = ? AND module_name = ?",
        [ws_id, "inventory-stock"],
    )

    test_app.state.module_registry.is_loaded = lambda name: name == "inventory-stock"

    resp = await client.get(f"/api/workshops/{ws_id}/nav")
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert "inventory-stock" not in ids


@pytest.mark.asyncio
async def test_nav_404_unknown_workshop(client: AsyncClient):
    resp = await client.get("/api/workshops/nonexistent-id/nav")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Phase 8B — nav uses module views from manifest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nav_uses_module_views_when_declared(client: AsyncClient, test_app: FastAPI):
    """When a loaded module has views, they appear instead of a default entry."""
    ws_id = await _create_workshop(client)
    await client.post(f"/api/workshops/{ws_id}/modules", json={"module_name": "inv-module"})

    views = [
        ModuleView(id="inv-dashboard", label="Inventory Dashboard", route="/modules/inv-module/dash", icon="box"),
    ]
    test_app.state.module_registry.is_loaded = lambda name: name == "inv-module"
    test_app.state.module_registry.get_module_views = lambda name: views if name == "inv-module" else []

    resp = await client.get(f"/api/workshops/{ws_id}/nav")
    assert resp.status_code == 200

    items = resp.json()["items"]
    module_items = [i for i in items if i["source"] == "module"]
    assert len(module_items) == 1
    item = module_items[0]
    assert item["id"] == "inv-dashboard"
    assert item["label"] == "Inventory Dashboard"
    assert item["route"] == "/modules/inv-module/dash"
    assert item["icon"] == "box"
    assert item["replaces_shell_view"] is None


@pytest.mark.asyncio
async def test_nav_view_with_replaces_shell_view(client: AsyncClient, test_app: FastAPI):
    """replaces_shell_view is propagated into the NavItem."""
    ws_id = await _create_workshop(client)
    await client.post(f"/api/workshops/{ws_id}/modules", json={"module_name": "inv-module"})

    views = [
        ModuleView(
            id="my-inv",
            label="My Inventory",
            route="/modules/inv-module/inv",
            replaces_shell_view="inventory",
        ),
    ]
    test_app.state.module_registry.is_loaded = lambda name: name == "inv-module"
    test_app.state.module_registry.get_module_views = lambda name: views if name == "inv-module" else []

    resp = await client.get(f"/api/workshops/{ws_id}/nav")
    assert resp.status_code == 200

    items = resp.json()["items"]
    module_items = [i for i in items if i["source"] == "module"]
    assert module_items[0]["replaces_shell_view"] == "inventory"

    # Shell 'inventory' item still present (never removed)
    ids = [i["id"] for i in items]
    assert "inventory" in ids


@pytest.mark.asyncio
async def test_nav_multiple_views_ordered_by_sort_order(client: AsyncClient, test_app: FastAPI):
    """Multiple views from one module are ordered by sort_order."""
    ws_id = await _create_workshop(client)
    await client.post(f"/api/workshops/{ws_id}/modules", json={"module_name": "multi-mod"})

    views = [
        ModuleView(id="v-last", label="Last", route="/a", sort_order=20),
        ModuleView(id="v-first", label="First", route="/b", sort_order=5),
    ]
    test_app.state.module_registry.is_loaded = lambda name: name == "multi-mod"
    test_app.state.module_registry.get_module_views = lambda name: views if name == "multi-mod" else []

    resp = await client.get(f"/api/workshops/{ws_id}/nav")
    assert resp.status_code == 200

    module_items = [i for i in resp.json()["items"] if i["source"] == "module"]
    assert module_items[0]["id"] == "v-first"
    assert module_items[1]["id"] == "v-last"


@pytest.mark.asyncio
async def test_nav_default_entry_when_no_views_declared(client: AsyncClient, test_app: FastAPI):
    """A loaded module with no views gets a default nav entry (backward compat)."""
    ws_id = await _create_workshop(client)
    await client.post(f"/api/workshops/{ws_id}/modules", json={"module_name": "no-views-mod"})

    test_app.state.module_registry.is_loaded = lambda name: name == "no-views-mod"
    test_app.state.module_registry.get_module_views = lambda name: []  # no views

    resp = await client.get(f"/api/workshops/{ws_id}/nav")
    assert resp.status_code == 200

    module_items = [i for i in resp.json()["items"] if i["source"] == "module"]
    assert len(module_items) == 1
    assert module_items[0]["id"] == "no-views-mod"
    assert module_items[0]["route"] == "/modules/no-views-mod"


@pytest.mark.asyncio
async def test_nav_app_mode_module_excluded_from_shell_nav(client: AsyncClient, test_app: FastAPI):
    """A module with app_mode.enabled=True must NOT appear in the shell sidebar nav.
    App-mode modules have their own branded sidebar and are launched via the
    workshop home launcher card — not via the shell nav."""
    ws_id = await _create_workshop(client)
    await client.post(f"/api/workshops/{ws_id}/modules", json={"module_name": "kitchen"})

    views = [
        ModuleView(id="kitchen-home", label="Home", route="/kitchen", icon="Home"),
        ModuleView(id="kitchen-larder", label="Larder", route="/kitchen/larder", icon="Archive"),
    ]
    app_mode = ModuleAppMode(enabled=True, title="Kitchen", home_route="/kitchen")

    manifest = MagicMock(spec=ModuleManifest)
    manifest.views = views
    manifest.app_mode = app_mode

    loaded = MagicMock(spec=LoadedModule)
    loaded.manifest = manifest

    test_app.state.module_registry.is_loaded = lambda name: name == "kitchen"
    test_app.state.module_registry.get_module = lambda name: loaded if name == "kitchen" else None
    test_app.state.module_registry.get_module_views = lambda name: views if name == "kitchen" else []

    resp = await client.get(f"/api/workshops/{ws_id}/nav")
    assert resp.status_code == 200

    items = resp.json()["items"]
    module_items = [i for i in items if i["source"] == "module"]
    # App-mode module must be completely absent from shell nav
    assert len(module_items) == 0
    kitchen_ids = [i["id"] for i in items if "kitchen" in i.get("id", "")]
    assert kitchen_ids == [], f"Kitchen views leaked into shell nav: {kitchen_ids}"
    # Shell fallbacks still present
    assert any(i["id"] == "inventory" for i in items)


@pytest.mark.asyncio
async def test_nav_non_app_mode_module_still_appears(client: AsyncClient, test_app: FastAPI):
    """A module with app_mode=None (or disabled) still appears in shell nav as normal."""
    ws_id = await _create_workshop(client)
    await client.post(f"/api/workshops/{ws_id}/modules", json={"module_name": "inventory-stock"})

    views = [ModuleView(id="inv-stock", label="Inventory Stock", route="/modules/inventory-stock", icon="Package")]

    manifest = MagicMock(spec=ModuleManifest)
    manifest.views = views
    manifest.app_mode = None  # no app mode

    loaded = MagicMock(spec=LoadedModule)
    loaded.manifest = manifest

    test_app.state.module_registry.is_loaded = lambda name: name == "inventory-stock"
    test_app.state.module_registry.get_module = lambda name: loaded if name == "inventory-stock" else None
    test_app.state.module_registry.get_module_views = lambda name: views if name == "inventory-stock" else []

    resp = await client.get(f"/api/workshops/{ws_id}/nav")
    assert resp.status_code == 200

    module_items = [i for i in resp.json()["items"] if i["source"] == "module"]
    assert len(module_items) == 1
    assert module_items[0]["id"] == "inv-stock"


@pytest.mark.asyncio
async def test_nav_shell_items_always_have_no_replaces_shell_view(client: AsyncClient):
    """Shell items never have replaces_shell_view set."""
    ws_id = await _create_workshop(client)
    resp = await client.get(f"/api/workshops/{ws_id}/nav")
    assert resp.status_code == 200

    for item in resp.json()["items"]:
        if item["source"] == "shell":
            assert item["replaces_shell_view"] is None


# ---------------------------------------------------------------------------
# PATCH /api/workshops/{id}/modules/{name} — update sort_order (Phase 8F)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_module_sort_order(client: AsyncClient):
    """PATCH updates sort_order for an existing module association."""
    ws_id = await _create_workshop(client)
    await client.post(
        f"/api/workshops/{ws_id}/modules",
        json={"module_name": "inventory-stock", "sort_order": 0},
    )

    resp = await client.patch(
        f"/api/workshops/{ws_id}/modules/inventory-stock",
        json={"sort_order": 3},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["module_name"] == "inventory-stock"
    assert body["sort_order"] == 3
    assert body["enabled"] is True


@pytest.mark.asyncio
async def test_patch_module_sort_order_404_not_associated(client: AsyncClient):
    """PATCH returns 404 when the module is not associated with the workshop."""
    ws_id = await _create_workshop(client)
    resp = await client.patch(
        f"/api/workshops/{ws_id}/modules/nonexistent-module",
        json={"sort_order": 1},
    )
    assert resp.status_code == 404
    assert "suggestion" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_patch_module_sort_order_404_unknown_workshop(client: AsyncClient):
    """PATCH returns 404 for an unknown workshop."""
    resp = await client.patch(
        "/api/workshops/nonexistent-id/modules/some-module",
        json={"sort_order": 1},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_module_reorder_affects_list_order(client: AsyncClient):
    """Updating sort_order reorders modules returned by the list endpoint."""
    ws_id = await _create_workshop(client)
    await client.post(f"/api/workshops/{ws_id}/modules", json={"module_name": "mod-a", "sort_order": 0})
    await client.post(f"/api/workshops/{ws_id}/modules", json={"module_name": "mod-b", "sort_order": 1})

    # Move mod-b before mod-a
    await client.patch(f"/api/workshops/{ws_id}/modules/mod-b", json={"sort_order": 0})
    await client.patch(f"/api/workshops/{ws_id}/modules/mod-a", json={"sort_order": 1})

    resp = await client.get(f"/api/workshops/{ws_id}/modules")
    assert resp.status_code == 200
    names = [m["module_name"] for m in resp.json()]
    assert names.index("mod-b") < names.index("mod-a")
