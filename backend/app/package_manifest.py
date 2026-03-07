"""Package manifest model — parses makestack-package.json.

Every installable Makestack package declares this manifest at the repo root.
The 'type' field determines which installer handles it.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, field_validator


_VALID_TYPES = frozenset({"module", "widget-pack", "catalogue", "data"})


class PackageManifest(BaseModel):
    """Parsed makestack-package.json at the root of any installable package.

    All four installable types (module, widget-pack, catalogue, data) share
    this manifest. Type-specific fields (e.g. module's keyword declarations)
    live in the separate manifest.json, not here.
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
