"""Registry client — resolves package names through Git-based registries.

Each registry is a cloned Git repository in ~/.makestack/registries/{name}/
containing an index.json with the shape:
{
  "packages": {
    "package-name": {
      "git": "https://github.com/...",
      "type": "module",
      "description": "..."
    }
  }
}

Resolution searches all cloned registries in alphabetical directory order.
First match wins.

Git operations (clone, pull) are run in a thread via asyncio.to_thread so they
do not block the event loop.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger().bind(component="registry_client")


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


@dataclass
class PackageInfo:
    """A package entry found in a registry."""

    name: str
    git_url: str
    type: str
    description: str = ""
    registry_name: str = ""


# ---------------------------------------------------------------------------
# Git helper (shared with package_cache)
# ---------------------------------------------------------------------------


async def run_git(*args: str, cwd: Path | None = None) -> tuple[int, str, str]:
    """Run a git subcommand without blocking the event loop.

    Returns (returncode, stdout, stderr).
    """
    result = await asyncio.to_thread(
        subprocess.run,
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


# ---------------------------------------------------------------------------
# RegistryClient
# ---------------------------------------------------------------------------


class RegistryClient:
    """Reads cloned registry repos and resolves package names to Git URLs.

    The client is filesystem-only — it does not interact with the UserDB.
    DB-level registry metadata (git_url, added_at) is managed by the router.
    """

    def __init__(self, registries_dir: Path) -> None:
        self.registries_dir = registries_dir
        self.registries_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------
    # Index reading
    # -------------------------------------------------------------------

    def _read_index(self, registry_name: str) -> dict[str, Any]:
        """Parse index.json from a cloned registry directory."""
        index_path = self.registries_dir / registry_name / "index.json"
        if not index_path.exists():
            return {"packages": {}}
        try:
            return json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            log.warning("registry_index_unreadable", registry=registry_name)
            return {"packages": {}}

    def _registry_dirs(self) -> list[Path]:
        """Return all registry subdirectories in sorted order."""
        if not self.registries_dir.exists():
            return []
        return sorted(
            d for d in self.registries_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )

    # -------------------------------------------------------------------
    # Resolution and search
    # -------------------------------------------------------------------

    def resolve(self, package_name: str) -> PackageInfo | None:
        """Search all registries for a package name. First match wins."""
        for registry_dir in self._registry_dirs():
            index = self._read_index(registry_dir.name)
            pkg = index.get("packages", {}).get(package_name)
            if pkg and isinstance(pkg, dict) and "git" in pkg:
                return PackageInfo(
                    name=package_name,
                    git_url=pkg["git"],
                    type=pkg.get("type", "module"),
                    description=pkg.get("description", ""),
                    registry_name=registry_dir.name,
                )
        return None

    def search(self, query: str) -> list[PackageInfo]:
        """Search package names and descriptions across all registries.

        First-match deduplication: if two registries declare the same package
        name, only the result from the earlier (alphabetically first) registry
        is returned.
        """
        results: list[PackageInfo] = []
        seen: set[str] = set()
        query_lower = query.lower()

        for registry_dir in self._registry_dirs():
            index = self._read_index(registry_dir.name)
            for pkg_name, pkg in index.get("packages", {}).items():
                if pkg_name in seen or not isinstance(pkg, dict):
                    continue
                desc = pkg.get("description", "")
                if query_lower in pkg_name.lower() or query_lower in desc.lower():
                    results.append(PackageInfo(
                        name=pkg_name,
                        git_url=pkg.get("git", ""),
                        type=pkg.get("type", "module"),
                        description=desc,
                        registry_name=registry_dir.name,
                    ))
                    seen.add(pkg_name)

        return results

    def list_packages_in_registry(self, registry_name: str) -> list[PackageInfo]:
        """List all packages declared in a single registry."""
        index = self._read_index(registry_name)
        results = []
        for pkg_name, pkg in index.get("packages", {}).items():
            if not isinstance(pkg, dict):
                continue
            results.append(PackageInfo(
                name=pkg_name,
                git_url=pkg.get("git", ""),
                type=pkg.get("type", "module"),
                description=pkg.get("description", ""),
                registry_name=registry_name,
            ))
        return results

    def count_packages(self, registry_name: str) -> int:
        """Return the number of packages declared in a registry."""
        index = self._read_index(registry_name)
        return len(index.get("packages", {}))

    def registry_is_cloned(self, name: str) -> bool:
        """Return True if a registry is already cloned locally."""
        return (self.registries_dir / name).is_dir()

    # -------------------------------------------------------------------
    # Git operations
    # -------------------------------------------------------------------

    async def clone_registry(self, name: str, git_url: str) -> None:
        """Clone a registry Git repo into registries_dir/{name}/."""
        target = self.registries_dir / name
        if target.exists():
            raise ValueError(f"Registry '{name}' is already cloned at {target}")

        log.info("registry_clone_start", name=name, url=git_url)
        rc, _, stderr = await run_git("clone", "--depth=1", git_url, str(target))
        if rc != 0:
            raise RuntimeError(
                f"git clone failed for registry '{name}': {stderr}"
            )
        log.info("registry_clone_done", name=name)

    async def refresh_registry(self, name: str) -> None:
        """Fetch + fast-forward a cloned registry."""
        target = self.registries_dir / name
        if not target.exists():
            raise FileNotFoundError(
                f"Registry '{name}' is not cloned at {target}"
            )

        log.info("registry_refresh_start", name=name)
        # Fetch first so we get the latest refs, then fast-forward.
        await run_git("fetch", "--depth=1", "origin", cwd=target)
        rc, _, stderr = await run_git("merge", "--ff-only", "FETCH_HEAD", cwd=target)
        if rc != 0:
            log.warning("registry_refresh_failed", name=name, error=stderr)
            raise RuntimeError(f"git merge failed for registry '{name}': {stderr}")
        log.info("registry_refresh_done", name=name)

    async def refresh_all(self, registry_names: list[str]) -> dict[str, str | None]:
        """Refresh all given registries concurrently.

        Returns {name: error_message_or_None}. Errors do not propagate —
        the caller can report them to the user.
        """
        async def _refresh_one(name: str) -> tuple[str, str | None]:
            try:
                await self.refresh_registry(name)
                return name, None
            except Exception as exc:
                log.warning("registry_refresh_failed", name=name, error=str(exc))
                return name, str(exc)

        pairs = await asyncio.gather(*[_refresh_one(n) for n in registry_names])
        return dict(pairs)

    def remove_registry(self, name: str) -> None:
        """Delete a cloned registry directory."""
        target = self.registries_dir / name
        if target.exists():
            shutil.rmtree(target)
            log.info("registry_removed", name=name)
