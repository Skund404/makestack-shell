"""Package cache — manages locally cloned package Git repos.

Packages are stored under packages_dir organised by type:
  ~/.makestack/packages/modules/{name}/
  ~/.makestack/packages/widgets/{name}/
  ~/.makestack/packages/catalogues/{name}/
  ~/.makestack/packages/data/{name}/

Version pinning uses Git tags (v1.0.0 or 1.0.0 style).
'latest' resolves to the highest semver tag on the repo.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import structlog

from .registry_client import run_git  # shared git helper

log = structlog.get_logger().bind(component="package_cache")


# ---------------------------------------------------------------------------
# Type → subdirectory mapping
# ---------------------------------------------------------------------------

_TYPE_DIRS: dict[str, str] = {
    "module": "modules",
    "widget-pack": "widgets",
    "catalogue": "catalogues",
    "data": "data",
}


def _type_dir(pkg_type: str) -> str:
    return _TYPE_DIRS.get(pkg_type, pkg_type)


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


@dataclass
class CachedPackage:
    """A package currently held in the local cache."""

    name: str
    type: str
    version: str    # Currently checked-out tag, or short commit hash
    path: Path


# ---------------------------------------------------------------------------
# Semver tag helpers
# ---------------------------------------------------------------------------


def _parse_semver(tag: str) -> tuple[int, int, int] | None:
    """Parse 'v1.2.3' or '1.2.3' → (1, 2, 3). Returns None if not semver."""
    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)$", tag.strip())
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None


def _latest_tag(tags: list[str]) -> str | None:
    """Return the highest semver tag from a list, or None."""
    semver_tags = [(t, _parse_semver(t)) for t in tags]
    semver_tags = [(t, v) for t, v in semver_tags if v is not None]  # type: ignore[misc]
    if not semver_tags:
        return None
    return max(semver_tags, key=lambda x: x[1])[0]  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# PackageCache
# ---------------------------------------------------------------------------


class PackageCache:
    """Manages locally cloned package Git repositories.

    Packages are cloned into packages_dir/{type_dir}/{name}/.
    Version switching is done via git checkout <tag>.
    """

    def __init__(self, packages_dir: Path) -> None:
        self.packages_dir = packages_dir
        self.packages_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------
    # Path helpers
    # -------------------------------------------------------------------

    def _pkg_path(self, name: str, pkg_type: str) -> Path:
        return self.packages_dir / _type_dir(pkg_type) / name

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------

    async def fetch(
        self,
        name: str,
        git_url: str,
        pkg_type: str,
        version: str | None = None,
    ) -> Path:
        """Clone (or update) a package repo and return its local path.

        If version is None or 'latest', resolves to the highest semver tag.
        """
        target = self._pkg_path(name, pkg_type)

        if not target.exists():
            await self._clone(name, git_url, target)
        else:
            await self._pull(name, target)

        # Resolve and check out the requested version.
        if version is None or version == "latest":
            tags = await self.available_versions(name, pkg_type)
            resolved = _latest_tag(tags)
        else:
            resolved = version

        if resolved:
            await self._checkout(name, target, resolved)
            log.info("package_cache_checked_out", name=name, version=resolved)

        return target

    def get_cached_path(self, name: str, pkg_type: str) -> Path | None:
        """Return the local path for a cached package, or None if not present."""
        p = self._pkg_path(name, pkg_type)
        return p if p.exists() else None

    async def get_cached_version(self, name: str, pkg_type: str) -> str | None:
        """Return the currently checked-out tag or commit for a cached package."""
        target = self._pkg_path(name, pkg_type)
        if not target.exists():
            return None

        # Try an exact tag match first.
        rc, stdout, _ = await run_git(
            "describe", "--tags", "--exact-match", cwd=target
        )
        if rc == 0 and stdout:
            return stdout

        # Fallback: short commit hash.
        rc, stdout, _ = await run_git("rev-parse", "--short", "HEAD", cwd=target)
        return stdout if rc == 0 else None

    async def available_versions(self, name: str, pkg_type: str) -> list[str]:
        """List all Git tags in the cached repo (unsorted)."""
        target = self._pkg_path(name, pkg_type)
        if not target.exists():
            return []
        rc, stdout, _ = await run_git("tag", "--list", cwd=target)
        if rc != 0 or not stdout:
            return []
        return [t for t in stdout.splitlines() if t.strip()]

    def list_cached(self) -> list[CachedPackage]:
        """List all packages currently in the cache (version field is 'unknown').

        Version is omitted here because resolving it requires async git calls.
        Use get_cached_version() per-package when the version is needed.
        """
        result: list[CachedPackage] = []
        for pkg_type, tdir in _TYPE_DIRS.items():
            type_path = self.packages_dir / tdir
            if not type_path.exists():
                continue
            for pkg_dir in sorted(type_path.iterdir()):
                if pkg_dir.is_dir():
                    result.append(CachedPackage(
                        name=pkg_dir.name,
                        type=pkg_type,
                        version="unknown",
                        path=pkg_dir,
                    ))
        return result

    def remove(self, name: str, pkg_type: str) -> None:
        """Delete a package from the cache."""
        target = self._pkg_path(name, pkg_type)
        if target.exists():
            shutil.rmtree(target)
            log.info("package_cache_removed", name=name, type=pkg_type)

    # -------------------------------------------------------------------
    # Private git helpers
    # -------------------------------------------------------------------

    async def _clone(self, name: str, git_url: str, target: Path) -> None:
        log.info("package_clone_start", name=name, url=git_url)
        target.parent.mkdir(parents=True, exist_ok=True)
        rc, _, stderr = await run_git("clone", git_url, str(target))
        if rc != 0:
            raise RuntimeError(
                f"git clone failed for package '{name}': {stderr}"
            )
        log.info("package_clone_done", name=name)

    async def _pull(self, name: str, target: Path) -> None:
        """Fetch latest tags and fast-forward the working tree."""
        log.debug("package_pull_start", name=name)
        await run_git("fetch", "--tags", cwd=target)
        rc, _, stderr = await run_git("pull", "--ff-only", cwd=target)
        if rc != 0:
            log.warning("package_pull_failed", name=name, error=stderr)

    async def _checkout(self, name: str, target: Path, version: str) -> None:
        rc, _, stderr = await run_git("checkout", version, cwd=target)
        if rc != 0:
            raise RuntimeError(
                f"git checkout '{version}' failed for package '{name}': {stderr}"
            )
