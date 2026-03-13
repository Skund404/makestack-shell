"""Tests for ModuleManifest validation."""

import pytest
from pydantic import ValidationError

from backend.app.module_manifest import ModuleManifest, ModuleKeyword, ModulePanel, ModuleTable, ModuleView


# ---------------------------------------------------------------------------
# Valid manifest (minimal)
# ---------------------------------------------------------------------------

VALID_MANIFEST = {
    "name": "test-module",
    "display_name": "Test Module",
    "version": "1.0.0",
    "description": "A test module.",
    "author": "Tester",
}


def test_valid_minimal_manifest():
    m = ModuleManifest.model_validate(VALID_MANIFEST)
    assert m.name == "test-module"
    assert m.display_name == "Test Module"
    assert m.version == "1.0.0"
    assert m.has_backend is True
    assert m.has_frontend is False
    assert m.keywords == []
    assert m.api_endpoints == []
    assert m.userdb_tables == []


def test_snake_name_property():
    m = ModuleManifest.model_validate(VALID_MANIFEST)
    assert m.snake_name == "test_module"


def test_snake_name_multiple_hyphens():
    m = ModuleManifest.model_validate({**VALID_MANIFEST, "name": "cost-track-er"})
    assert m.snake_name == "cost_track_er"


# ---------------------------------------------------------------------------
# Name validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_name", [
    "TestModule",        # uppercase
    "test module",       # space
    "test_module",       # underscore not allowed (hyphens only)
    "-test",             # leading hyphen
    "123test",           # starts with digit
    "",                  # empty
])
def test_invalid_name(bad_name):
    with pytest.raises(ValidationError) as exc_info:
        ModuleManifest.model_validate({**VALID_MANIFEST, "name": bad_name})
    assert "name" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()


@pytest.mark.parametrize("good_name", [
    "inventory-stock",
    "cost-tracker",
    "my-module",
    "module1",
    "a",
])
def test_valid_names(good_name):
    m = ModuleManifest.model_validate({**VALID_MANIFEST, "name": good_name})
    assert m.name == good_name


# ---------------------------------------------------------------------------
# Keyword validation
# ---------------------------------------------------------------------------

def test_valid_keyword():
    m = ModuleManifest.model_validate({
        **VALID_MANIFEST,
        "keywords": [{"keyword": "INVENTORY_STOCK_", "description": "Stock level", "renderer": "StockBadge"}],
    })
    assert m.keywords[0].keyword == "INVENTORY_STOCK_"


@pytest.mark.parametrize("bad_kw", [
    "inventory_stock",      # no trailing underscore
    "inventory_stock_2",    # ends with digit, then no underscore
    "INVENTORY STOCK_",     # space
    "inventory_STOCK_",     # mixed case
    "1NVENTORY_",           # starts with digit
])
def test_invalid_keyword(bad_kw):
    with pytest.raises(ValidationError):
        ModuleManifest.model_validate({
            **VALID_MANIFEST,
            "keywords": [{"keyword": bad_kw, "description": "x", "renderer": "Widget"}],
        })


@pytest.mark.parametrize("good_kw", [
    "INVENTORY_STOCK_",
    "COST_",
    "MY_MODULE_VALUE_",
    "A_",
])
def test_valid_keywords(good_kw):
    m = ModuleManifest.model_validate({
        **VALID_MANIFEST,
        "keywords": [{"keyword": good_kw, "description": "x", "renderer": "Widget"}],
    })
    assert m.keywords[0].keyword == good_kw


# ---------------------------------------------------------------------------
# UserDB table name validation
# ---------------------------------------------------------------------------

def test_valid_table_name():
    m = ModuleManifest.model_validate({
        **VALID_MANIFEST,
        "userdb_tables": [{"name": "test_module_items", "description": "Items table"}],
    })
    assert m.userdb_tables[0].name == "test_module_items"


def test_table_name_without_prefix_fails():
    with pytest.raises(ValidationError) as exc_info:
        ModuleManifest.model_validate({
            **VALID_MANIFEST,
            "userdb_tables": [{"name": "items", "description": "No prefix"}],
        })
    assert "prefix" in str(exc_info.value).lower() or "items" in str(exc_info.value)


def test_table_name_wrong_prefix_fails():
    with pytest.raises(ValidationError):
        ModuleManifest.model_validate({
            **VALID_MANIFEST,
            "userdb_tables": [{"name": "other_module_items", "description": "Wrong prefix"}],
        })


def test_multiple_tables_all_valid():
    m = ModuleManifest.model_validate({
        **VALID_MANIFEST,
        "userdb_tables": [
            {"name": "test_module_items", "description": "Items"},
            {"name": "test_module_config", "description": "Config"},
        ],
    })
    assert len(m.userdb_tables) == 2


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

def test_api_endpoint():
    m = ModuleManifest.model_validate({
        **VALID_MANIFEST,
        "api_endpoints": [
            {"method": "GET", "path": "/items", "description": "List items"}
        ],
    })
    assert m.api_endpoints[0].method == "GET"
    assert m.api_endpoints[0].path == "/items"


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

def test_defaults():
    m = ModuleManifest.model_validate(VALID_MANIFEST)
    assert m.shell_compatibility == ">=0.1.0"
    assert m.license == "proprietary"
    assert m.has_backend is True
    assert m.has_frontend is False
    assert m.dependencies == {}
    assert m.peer_modules == {}
    assert m.config_defaults == {}
    assert m.views == []
    assert m.panels == []


# ---------------------------------------------------------------------------
# ModuleView
# ---------------------------------------------------------------------------


def test_valid_module_view():
    m = ModuleManifest.model_validate({
        **VALID_MANIFEST,
        "views": [{"id": "dashboard", "label": "Dashboard", "route": "/modules/test-module/dashboard"}],
    })
    assert len(m.views) == 1
    assert m.views[0].id == "dashboard"
    assert m.views[0].label == "Dashboard"
    assert m.views[0].route == "/modules/test-module/dashboard"
    assert m.views[0].icon == ""
    assert m.views[0].replaces_shell_view is None
    assert m.views[0].sort_order == 0


def test_module_view_with_replaces_shell_view():
    m = ModuleManifest.model_validate({
        **VALID_MANIFEST,
        "views": [
            {"id": "inv", "label": "My Inventory", "route": "/modules/test-module/inv",
             "replaces_shell_view": "inventory"},
        ],
    })
    assert m.views[0].replaces_shell_view == "inventory"


@pytest.mark.parametrize("shell_view", ["inventory", "workshops", "catalogue"])
def test_valid_replaces_shell_view_values(shell_view):
    m = ModuleManifest.model_validate({
        **VALID_MANIFEST,
        "views": [{"id": "v", "label": "V", "route": "/x", "replaces_shell_view": shell_view}],
    })
    assert m.views[0].replaces_shell_view == shell_view


def test_invalid_replaces_shell_view():
    with pytest.raises(ValidationError):
        ModuleManifest.model_validate({
            **VALID_MANIFEST,
            "views": [{"id": "v", "label": "V", "route": "/x", "replaces_shell_view": "settings"}],
        })


def test_module_view_with_sort_order_and_icon():
    m = ModuleManifest.model_validate({
        **VALID_MANIFEST,
        "views": [
            {"id": "v1", "label": "A", "route": "/a", "sort_order": 10, "icon": "package"},
            {"id": "v2", "label": "B", "route": "/b", "sort_order": 5},
        ],
    })
    assert m.views[0].sort_order == 10
    assert m.views[0].icon == "package"
    assert m.views[1].sort_order == 5


def test_manifest_views_optional():
    """Manifests without views are valid."""
    m = ModuleManifest.model_validate(VALID_MANIFEST)
    assert m.views == []


# ---------------------------------------------------------------------------
# ModulePanel (updated schema)
# ---------------------------------------------------------------------------


def test_valid_module_panel():
    m = ModuleManifest.model_validate({
        **VALID_MANIFEST,
        "panels": [{"id": "stock-summary", "label": "Stock Summary", "size": "half"}],
    })
    assert len(m.panels) == 1
    assert m.panels[0].id == "stock-summary"
    assert m.panels[0].label == "Stock Summary"
    assert m.panels[0].size == "half"


@pytest.mark.parametrize("size", ["full", "half", "third"])
def test_valid_panel_sizes(size):
    m = ModuleManifest.model_validate({
        **VALID_MANIFEST,
        "panels": [{"id": "p", "label": "Panel", "size": size}],
    })
    assert m.panels[0].size == size


def test_invalid_panel_size():
    with pytest.raises(ValidationError):
        ModuleManifest.model_validate({
            **VALID_MANIFEST,
            "panels": [{"id": "p", "label": "Panel", "size": "quarter"}],
        })


def test_panel_default_size():
    m = ModuleManifest.model_validate({
        **VALID_MANIFEST,
        "panels": [{"id": "p", "label": "Panel"}],
    })
    assert m.panels[0].size == "half"


def test_manifest_panels_optional():
    """Manifests without panels are valid."""
    m = ModuleManifest.model_validate(VALID_MANIFEST)
    assert m.panels == []
