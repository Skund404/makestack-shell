"""Tests for PackageCache — local package repo management.

Tests that require actual git repos use subprocess to create minimal repos
in tmp_path. Git operations that need a remote (clone from URL, pull) are
tested with a local repo as the remote — no network access required.
"""

import subprocess
from pathlib import Path

import pytest
import pytest_asyncio

from backend.app.package_cache import PackageCache, _parse_semver, _latest_tag


# ---------------------------------------------------------------------------
# Pure helper tests (no git)
# ---------------------------------------------------------------------------


def test_parse_semver_v_prefix():
    assert _parse_semver("v1.2.3") == (1, 2, 3)


def test_parse_semver_no_prefix():
    assert _parse_semver("2.0.0") == (2, 0, 0)


def test_parse_semver_invalid():
    assert _parse_semver("latest") is None
    assert _parse_semver("1.0") is None
    assert _parse_semver("abc") is None


def test_latest_tag_returns_highest():
    tags = ["v1.0.0", "v1.2.0", "v0.9.0", "v1.1.0"]
    assert _latest_tag(tags) == "v1.2.0"


def test_latest_tag_mixed_prefix():
    tags = ["1.0.0", "v2.0.0", "1.5.0"]
    assert _latest_tag(tags) == "v2.0.0"


def test_latest_tag_no_semver_tags():
    assert _latest_tag(["feature-branch", "main"]) is None


def test_latest_tag_empty_list():
    assert _latest_tag([]) is None


# ---------------------------------------------------------------------------
# Git-backed tests
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        check=True,
        env={"HOME": str(cwd.parent), "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@t.com",
             "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@t.com",
             "PATH": "/usr/bin:/bin"},
    )


@pytest.fixture
def bare_repo(tmp_path: Path) -> Path:
    """Create a bare git repo with a tagged commit and a makestack-package.json."""
    source = tmp_path / "source"
    source.mkdir()

    _git(["init"], source)
    _git(["config", "user.email", "test@test.com"], source)
    _git(["config", "user.name", "Test"], source)

    # Add a makestack-package.json
    (source / "makestack-package.json").write_text(
        '{"name": "test-pkg", "type": "module", "version": "1.0.0"}',
        encoding="utf-8",
    )
    (source / "manifest.json").write_text(
        '{"name": "test-pkg", "version": "1.0.0"}',
        encoding="utf-8",
    )
    _git(["add", "."], source)
    _git(["commit", "-m", "Initial commit"], source)
    _git(["tag", "v1.0.0"], source)

    # Add a second version
    (source / "makestack-package.json").write_text(
        '{"name": "test-pkg", "type": "module", "version": "2.0.0"}',
        encoding="utf-8",
    )
    _git(["add", "."], source)
    _git(["commit", "-m", "v2.0.0"], source)
    _git(["tag", "v2.0.0"], source)

    return source


@pytest.fixture
def cache(tmp_path: Path) -> PackageCache:
    return PackageCache(packages_dir=tmp_path / "packages")


@pytest.mark.asyncio
async def test_fetch_clones_repo(cache: PackageCache, bare_repo: Path):
    path = await cache.fetch("test-pkg", str(bare_repo), "module")
    assert path.exists()
    assert (path / "makestack-package.json").exists()


@pytest.mark.asyncio
async def test_fetch_resolves_latest_tag(cache: PackageCache, bare_repo: Path):
    path = await cache.fetch("test-pkg", str(bare_repo), "module")
    version = await cache.get_cached_version("test-pkg", "module")
    assert version == "v2.0.0"


@pytest.mark.asyncio
async def test_fetch_pins_to_version(cache: PackageCache, bare_repo: Path):
    path = await cache.fetch("test-pkg", str(bare_repo), "module", version="v1.0.0")
    version = await cache.get_cached_version("test-pkg", "module")
    assert version == "v1.0.0"


@pytest.mark.asyncio
async def test_fetch_returns_existing_without_clone(cache: PackageCache, bare_repo: Path, tmp_path: Path):
    """fetch() on an already-cloned repo does a pull (not re-clone)."""
    path1 = await cache.fetch("test-pkg", str(bare_repo), "module")
    path2 = await cache.fetch("test-pkg", str(bare_repo), "module")
    assert path1 == path2


@pytest.mark.asyncio
async def test_get_cached_path_returns_none_when_absent(cache: PackageCache):
    result = cache.get_cached_path("nonexistent", "module")
    assert result is None


@pytest.mark.asyncio
async def test_get_cached_path_returns_path_when_present(cache: PackageCache, bare_repo: Path):
    await cache.fetch("test-pkg", str(bare_repo), "module")
    result = cache.get_cached_path("test-pkg", "module")
    assert result is not None
    assert result.exists()


@pytest.mark.asyncio
async def test_get_cached_version_returns_none_when_absent(cache: PackageCache):
    result = await cache.get_cached_version("nonexistent", "module")
    assert result is None


@pytest.mark.asyncio
async def test_available_versions(cache: PackageCache, bare_repo: Path):
    await cache.fetch("test-pkg", str(bare_repo), "module", version="v1.0.0")
    versions = await cache.available_versions("test-pkg", "module")
    assert "v1.0.0" in versions
    assert "v2.0.0" in versions


@pytest.mark.asyncio
async def test_available_versions_empty_for_absent(cache: PackageCache):
    versions = await cache.available_versions("nonexistent", "module")
    assert versions == []


def test_list_cached_empty(cache: PackageCache):
    assert cache.list_cached() == []


@pytest.mark.asyncio
async def test_list_cached_returns_packages(cache: PackageCache, bare_repo: Path):
    await cache.fetch("test-pkg", str(bare_repo), "module")
    cached = cache.list_cached()
    assert len(cached) == 1
    assert cached[0].name == "test-pkg"
    assert cached[0].type == "module"


def test_remove_deletes_directory(cache: PackageCache, tmp_path: Path):
    # Manually create a fake package dir to test remove().
    pkg_dir = cache.packages_dir / "modules" / "fake-pkg"
    pkg_dir.mkdir(parents=True)
    assert pkg_dir.exists()
    cache.remove("fake-pkg", "module")
    assert not pkg_dir.exists()


def test_remove_nonexistent_does_not_error(cache: PackageCache):
    cache.remove("nonexistent", "module")  # Should not raise


@pytest.mark.asyncio
async def test_fetch_wrong_git_url_raises(cache: PackageCache):
    with pytest.raises(RuntimeError, match="git clone failed"):
        await cache.fetch("bad-pkg", "https://localhost:9999/nonexistent.git", "module")
