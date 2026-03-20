"""Pydantic schema for module manifest.json files.

Every module ships a manifest.json that declares its capabilities:
keyword renderers, API endpoints, UserDB tables, panels, and dependencies.
The Shell validates this at load time before mounting anything.
"""

import re
from typing import Literal

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class ModuleKeyword(BaseModel):
    """A keyword renderer declared by a module."""

    keyword: str                # e.g., "INVENTORY_STOCK_"
    description: str
    renderer: str               # Component name in the frontend


class ModuleEndpoint(BaseModel):
    """A backend API endpoint declared by a module (for MCP auto-generation)."""

    method: str                 # GET | POST | PUT | DELETE
    path: str                   # Relative to /modules/{name}/
    description: str
    name: str | None = None     # Semantic tool name suffix; used instead of method+path slug when present
    parameters: dict | None = None  # JSON Schema for input parameters


_VALID_SHELL_VIEWS = frozenset({"inventory", "workshops", "catalogue"})


class ModuleView(BaseModel):
    """A nav entry declared by a module for workshop sidebars.

    Each view registers one entry in the workshop nav when both conditions hold:
      1. The module is loaded in the registry.
      2. The module is associated with the workshop (workshop_modules table, enabled=1).

    replaces_shell_view: if set, signals the frontend to demote the named shell view
    to the secondary shell layer. Shell views are never removed — only demoted.
    At most one loaded module may claim each shell view; last-to-load wins.
    """

    id: str
    label: str
    route: str
    icon: str = ""              # Lucide icon name (empty = default module icon)
    replaces_shell_view: str | None = None  # 'inventory' | 'workshops' | 'catalogue'
    sort_order: int = 0

    @field_validator("replaces_shell_view")
    @classmethod
    def validate_replaces_shell_view(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_SHELL_VIEWS:
            raise ValueError(
                f"replaces_shell_view '{v}' is invalid — must be one of: "
                f"{', '.join(sorted(_VALID_SHELL_VIEWS))}"
            )
        return v


class ModulePanel(BaseModel):
    """A frontend panel registered by a module for the workshop home.

    The component is resolved frontend-side via PanelRegistry (panelId → React component).
    No component path is stored here — that is a build-time concern.
    Unresolved panel ids render as <UnknownPanel> — they never throw.
    """

    id: str
    label: str
    size: Literal["full", "half", "third"] = "half"


class ModuleTable(BaseModel):
    """A UserDB table declared by a module."""

    name: str                   # Must be prefixed with the module's snake_case name
    description: str


class PeerDependency(BaseModel):
    """A dependency on another installed module."""

    name: str
    min_version: str | None = None
    description: str = ""


# ---------------------------------------------------------------------------
# Top-level manifest
# ---------------------------------------------------------------------------


class ModuleManifest(BaseModel):
    """Complete manifest.json for an installable module.

    Lives at the root of the module directory. Validated by the Shell loader
    before any backend routes or migrations are run.
    """

    name: str                       # Unique, lowercase, hyphens only
    display_name: str
    version: str                    # Semver (e.g., "1.0.0")
    description: str
    author: str
    license: str = "proprietary"
    shell_compatibility: str = ">=0.1.0"   # Semver range
    has_backend: bool = True
    has_frontend: bool = False
    keywords: list[ModuleKeyword] = []
    api_endpoints: list[ModuleEndpoint] = []
    views: list[ModuleView] = []
    panels: list[ModulePanel] = []
    userdb_tables: list[ModuleTable] = []
    dependencies: dict = {}             # {"python": [...], "node": [...]}
    peer_modules: dict = {}             # {"optional": [...], "required": [...]}
    core_api_permissions: list[str] = []
    config_defaults: dict = {}

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Module name must be lowercase with hyphens only."""
        if not re.match(r"^[a-z][a-z0-9-]*$", v):
            raise ValueError(
                f"Module name '{v}' is invalid — must be lowercase letters, digits, and hyphens only "
                f"(e.g., 'inventory-stock', 'cost-tracker')"
            )
        return v

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, keywords: list[ModuleKeyword], info) -> list[ModuleKeyword]:
        """Keyword names must be UPPERCASE with trailing underscore."""
        for kw in keywords:
            if not re.match(r"^[A-Z][A-Z0-9_]*_$", kw.keyword):
                raise ValueError(
                    f"Keyword '{kw.keyword}' is invalid — must be uppercase letters/digits/underscores "
                    f"with a trailing underscore (e.g., 'INVENTORY_STOCK_')"
                )
        return keywords

    @field_validator("userdb_tables")
    @classmethod
    def validate_table_names(cls, tables: list[ModuleTable], info) -> list[ModuleTable]:
        """Table names must start with the module's snake_case prefix."""
        # We validate the prefix against info.data['name'] after that field is parsed.
        # Pydantic v2: 'info.data' contains already-validated fields.
        module_name = info.data.get("name", "")
        if not module_name:
            return tables  # Can't validate without name — will fail name validation
        prefix = module_name.replace("-", "_")
        for table in tables:
            if not table.name.startswith(prefix):
                raise ValueError(
                    f"Table '{table.name}' must be prefixed with '{prefix}_' "
                    f"(derived from module name '{module_name}')"
                )
        return tables

    @property
    def snake_name(self) -> str:
        """Module name with hyphens replaced by underscores (Python-safe)."""
        return self.name.replace("-", "_")
