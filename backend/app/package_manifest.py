"""Package manifest model — parses makestack-package.json.

Every installable Makestack package declares this manifest at the repo root.
The 'type' field determines which installer handles it.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, field_validator, model_validator


_VALID_TYPES = frozenset({"module", "widget-pack", "catalogue", "data", "skill"})


class PackageManifest(BaseModel):
    """Parsed makestack-package.json at the root of any installable package.

    All installable types share this manifest. Type-specific fields live in the
    separate manifest.json, not here.
    """

    name: str
    type: str
    version: str
    description: str = ""
    author: str = ""
    license: str = ""
    shell_compatibility: str = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-z][a-z0-9-]*$", v):
            raise ValueError(
                f"Package name '{v}' is invalid. "
                "Use lowercase letters, digits, and hyphens only (e.g. my-package)."
            )
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in _VALID_TYPES:
            raise ValueError(
                f"Package type '{v}' is not recognised. "
                f"Valid types: {sorted(_VALID_TYPES)}"
            )
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        if not re.match(r"^\d+\.\d+\.\d+", v):
            raise ValueError(
                f"Version '{v}' is not a valid semver string (e.g. 1.0.0)."
            )
        return v

    @model_validator(mode="after")
    def check_shell_compatibility(self) -> "PackageManifest":
        """Reject the manifest if shell_compatibility is set and not satisfied."""
        if not self.shell_compatibility:
            return self
        from packaging.specifiers import InvalidSpecifier, SpecifierSet
        from packaging.version import Version

        from .constants import SHELL_VERSION

        try:
            spec = SpecifierSet(self.shell_compatibility)
        except InvalidSpecifier as exc:
            raise ValueError(
                f"shell_compatibility '{self.shell_compatibility}' is not a valid version specifier: {exc}"
            ) from exc

        if Version(SHELL_VERSION) not in spec:
            raise ValueError(
                f"shell_compatibility '{self.shell_compatibility}' requires a shell version "
                f"that is not satisfied by the current version {SHELL_VERSION!r}. "
                f"Update the Shell or contact the package author."
            )
        return self
