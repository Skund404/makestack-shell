"""Tests for RegistryClient — package registry resolution and search.

These tests create real (minimal) git repos in tmp_path to exercise the
filesystem reading logic without network access. Git operations (clone, pull)
are not exercised here — those are integration concerns. We test resolution
and search against pre-built index.json files in existing directories.
"""

import json
from pathlib import Path

import pytest

from backend.app.registry_client import RegistryClient, PackageInfo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_registry(registries_dir: Path, name: str, packages: dict) -> Path:
    """Create a minimal registry directory with an index.json."""
    reg_dir = registries_dir / name
    reg_dir.mkdir(parents=True)
    (reg_dir / "index.json").write_text(
        json.dumps({"packages": packages}),
        encoding="utf-8",
    )
    return reg_dir


@pytest.fixture
def registries_dir(tmp_path: Path) -> Path:
    return tmp_path / "registries"


@pytest.fixture
def client(registries_dir: Path) -> RegistryClient:
    return RegistryClient(registries_dir)


# ---------------------------------------------------------------------------
# resolve()
# ---------------------------------------------------------------------------


def test_resolve_finds_package(registries_dir: Path, client: RegistryClient):
    _make_registry(registries_dir, "official", {
        "inventory-stock": {
            "git": "https://github.com/makestack/inventory",
            "type": "module",
            "description": "Track stock",
        }
    })
    info = client.resolve("inventory-stock")
    assert info is not None
    assert info.name == "inventory-stock"
    assert info.git_url == "https://github.com/makestack/inventory"
    assert info.type == "module"
    assert info.registry_name == "official"


def test_resolve_returns_none_for_unknown_package(registries_dir: Path, client: RegistryClient):
    _make_registry(registries_dir, "official", {"pkg-a": {"git": "https://example.com/a", "type": "module"}})
    assert client.resolve("nonexistent") is None


def test_resolve_returns_none_with_empty_registries(client: RegistryClient):
    assert client.resolve("anything") is None


def test_resolve_first_match_wins(registries_dir: Path, client: RegistryClient):
    """When two registries declare the same package, the alphabetically first wins."""
    _make_registry(registries_dir, "aaa-registry", {
        "shared-pkg": {"git": "https://aaa.com/pkg", "type": "module"}
    })
    _make_registry(registries_dir, "zzz-registry", {
        "shared-pkg": {"git": "https://zzz.com/pkg", "type": "module"}
    })
    info = client.resolve("shared-pkg")
    assert info is not None
    assert info.git_url == "https://aaa.com/pkg"
    assert info.registry_name == "aaa-registry"


def test_resolve_searches_multiple_registries(registries_dir: Path, client: RegistryClient):
    _make_registry(registries_dir, "reg-a", {"pkg-a": {"git": "https://a.com", "type": "module"}})
    _make_registry(registries_dir, "reg-b", {"pkg-b": {"git": "https://b.com", "type": "widget-pack"}})
    assert client.resolve("pkg-a") is not None
    assert client.resolve("pkg-b") is not None


def test_resolve_skips_malformed_entry(registries_dir: Path, client: RegistryClient):
    """Entries missing 'git' field are skipped gracefully."""
    _make_registry(registries_dir, "official", {
        "bad-pkg": {"type": "module"},  # missing 'git'
        "good-pkg": {"git": "https://example.com", "type": "module"},
    })
    assert client.resolve("bad-pkg") is None
    assert client.resolve("good-pkg") is not None


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


def test_search_matches_package_name(registries_dir: Path, client: RegistryClient):
    _make_registry(registries_dir, "official", {
        "inventory-stock": {"git": "https://x.com", "type": "module", "description": "Track things"},
    })
    results = client.search("inventory")
    assert len(results) == 1
    assert results[0].name == "inventory-stock"


def test_search_matches_description(registries_dir: Path, client: RegistryClient):
    _make_registry(registries_dir, "official", {
        "leather-pkg": {"git": "https://x.com", "type": "catalogue", "description": "Leatherwork catalogue"},
    })
    results = client.search("leatherwork")
    assert len(results) == 1
    assert results[0].name == "leather-pkg"


def test_search_is_case_insensitive(registries_dir: Path, client: RegistryClient):
    _make_registry(registries_dir, "official", {
        "timer-widgets": {"git": "https://x.com", "type": "widget-pack", "description": ""},
    })
    assert len(client.search("TIMER")) == 1
    assert len(client.search("Timer")) == 1


def test_search_deduplicates_across_registries(registries_dir: Path, client: RegistryClient):
    _make_registry(registries_dir, "aaa", {"shared": {"git": "https://aaa.com", "type": "module", "description": "shared pkg"}})
    _make_registry(registries_dir, "zzz", {"shared": {"git": "https://zzz.com", "type": "module", "description": "shared pkg"}})
    results = client.search("shared")
    assert len(results) == 1
    assert results[0].git_url == "https://aaa.com"


def test_search_returns_empty_for_no_match(registries_dir: Path, client: RegistryClient):
    _make_registry(registries_dir, "official", {
        "inventory-stock": {"git": "https://x.com", "type": "module", "description": "stock"},
    })
    assert client.search("xxxxxxxx") == []


def test_search_no_registries_returns_empty(client: RegistryClient):
    assert client.search("anything") == []


# ---------------------------------------------------------------------------
# count_packages() / list_packages_in_registry()
# ---------------------------------------------------------------------------


def test_count_packages(registries_dir: Path, client: RegistryClient):
    _make_registry(registries_dir, "official", {
        "pkg-a": {"git": "https://a.com", "type": "module"},
        "pkg-b": {"git": "https://b.com", "type": "widget-pack"},
    })
    assert client.count_packages("official") == 2


def test_count_packages_missing_registry(client: RegistryClient):
    assert client.count_packages("nonexistent") == 0


def test_list_packages_in_registry(registries_dir: Path, client: RegistryClient):
    _make_registry(registries_dir, "official", {
        "pkg-a": {"git": "https://a.com", "type": "module", "description": "Module A"},
    })
    packages = client.list_packages_in_registry("official")
    assert len(packages) == 1
    assert packages[0].name == "pkg-a"
    assert packages[0].registry_name == "official"


# ---------------------------------------------------------------------------
# registry_is_cloned()
# ---------------------------------------------------------------------------


def test_registry_is_cloned_true(registries_dir: Path, client: RegistryClient):
    _make_registry(registries_dir, "official", {})
    assert client.registry_is_cloned("official") is True


def test_registry_is_cloned_false(client: RegistryClient):
    assert client.registry_is_cloned("nonexistent") is False


# ---------------------------------------------------------------------------
# Resilience
# ---------------------------------------------------------------------------


def test_malformed_index_json_returns_empty(registries_dir: Path, client: RegistryClient):
    reg_dir = registries_dir / "broken"
    reg_dir.mkdir(parents=True)
    (reg_dir / "index.json").write_text("not valid json", encoding="utf-8")
    assert client.resolve("anything") is None
    assert client.search("anything") == []
