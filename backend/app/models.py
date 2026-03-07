"""Shared Pydantic models for the Makestack Shell API.

These models are used by all routers and are the contract between
the Shell backend and its two consumers: the React frontend and the MCP server.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Generic pagination wrapper — all list endpoints use this shape
# ---------------------------------------------------------------------------

T = TypeVar("T")


class PaginatedList(BaseModel, Generic[T]):
    """Standard paginated list response for all list endpoints."""

    items: list[T]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Catalogue / Core primitive models
# ---------------------------------------------------------------------------


class Primitive(BaseModel):
    """A single primitive as returned by Core (or proxied by the Shell)."""

    id: str
    type: str
    name: str
    slug: str
    path: str
    created: str = ""
    modified: str = ""
    description: str = ""
    tags: list[Any] = Field(default_factory=list)
    properties: dict[str, Any] | None = None
    parent_project: str = ""
    manifest: dict[str, Any] = Field(default_factory=dict)
    commit_hash: str = ""


class PrimitiveCreate(BaseModel):
    """Request body for creating a new primitive."""

    type: str  # tool | material | technique | workflow | project | event
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    properties: dict[str, Any] | None = None
    steps: list[Any] | None = None          # technique, workflow
    parent_project: str | None = None       # project
    relationships: list[dict[str, Any]] = Field(default_factory=list)


class PrimitiveUpdate(BaseModel):
    """Request body for updating a primitive. Identity fields are required by Core."""

    id: str
    type: str
    name: str
    slug: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    properties: dict[str, Any] | None = None
    steps: list[Any] | None = None
    parent_project: str | None = None
    relationships: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Relationship models
# ---------------------------------------------------------------------------


class Relationship(BaseModel):
    """A directional relationship between two primitives."""

    source_path: str
    source_type: str
    relationship_type: str
    target_path: str
    target_type: str = ""
    metadata: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Inventory models
# ---------------------------------------------------------------------------


class InventoryItem(BaseModel):
    """A personal inventory record — a hash-pointer to a catalogue entry."""

    id: str
    catalogue_path: str
    catalogue_hash: str
    primitive_type: str
    workshop_id: str | None = None
    added_at: str
    updated_at: str


class InventoryItemWithCatalogue(InventoryItem):
    """Inventory item enriched with resolved catalogue data and staleness state."""

    catalogue_data: Primitive | None = None
    is_stale: bool = False          # True when the catalogue entry has been updated
    current_hash: str | None = None  # Current catalogue hash (for UI diff link)


class InventoryCreate(BaseModel):
    """Request body for adding a catalogue item to inventory."""

    catalogue_path: str
    workshop_id: str | None = None


class InventoryUpdate(BaseModel):
    """Request body for updating an inventory item."""

    workshop_id: str | None = None
    catalogue_hash: str | None = None  # Update the pinned version hash


# ---------------------------------------------------------------------------
# Workshop models
# ---------------------------------------------------------------------------


class WorkshopMember(BaseModel):
    """A primitive reference that belongs to a workshop."""

    primitive_path: str
    primitive_type: str
    added_at: str


class Workshop(BaseModel):
    """A user-defined organizational container."""

    id: str
    name: str
    slug: str
    description: str = ""
    icon: str = ""
    color: str = ""
    sort_order: int = 0
    created_at: str
    updated_at: str


class WorkshopWithMembers(Workshop):
    """Workshop with its full member list."""

    members: list[WorkshopMember] = Field(default_factory=list)


class WorkshopCreate(BaseModel):
    """Request body for creating a workshop."""

    name: str
    description: str = ""
    icon: str = ""
    color: str = ""


class WorkshopUpdate(BaseModel):
    """Request body for updating a workshop."""

    name: str | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    sort_order: int | None = None


class WorkshopMemberAdd(BaseModel):
    """Request body for adding a primitive to a workshop."""

    primitive_path: str
    primitive_type: str


class ActiveWorkshopSet(BaseModel):
    """Request body for setting the active workshop context."""

    workshop_id: str | None = None  # None = clear active workshop


# ---------------------------------------------------------------------------
# Version history and diff models
# ---------------------------------------------------------------------------


class CommitInfo(BaseModel):
    """Metadata for a single Git commit."""

    hash: str
    message: str
    author: str
    timestamp: str


class HistoryResponse(BaseModel):
    """Paginated version history for a primitive."""

    path: str
    total: int
    commits: list[CommitInfo]


class FieldChange(BaseModel):
    """A single field-level change between two versions."""

    field: str
    type: str           # added | removed | modified
    old_value: Any | None = None
    new_value: Any | None = None


class DiffResponse(BaseModel):
    """Structured diff between two versions of a primitive."""

    path: str
    from_hash: str
    to_hash: str
    from_timestamp: str
    to_timestamp: str
    changes: list[FieldChange]


# ---------------------------------------------------------------------------
# Settings models
# ---------------------------------------------------------------------------


class UserPreferences(BaseModel):
    """All user preferences as a flat key-value map."""

    preferences: dict[str, Any]


class ThemeInfo(BaseModel):
    """Active theme information."""

    name: str


class ThemeSet(BaseModel):
    """Request body for switching themes."""

    name: str


class ThemeData(BaseModel):
    """Full theme CSS variable map, used by the frontend theme loader."""

    name: str
    variables: dict[str, str]  # CSS variable name → value


# ---------------------------------------------------------------------------
# Module models
# ---------------------------------------------------------------------------


class InstalledModule(BaseModel):
    """A registered module and its current state."""

    name: str
    version: str
    installed_at: str
    enabled: bool
    last_migration: str | None = None
    package_path: str | None = None
    # Runtime fields — populated when the module is loaded:
    loaded: bool = False
    load_error: str | None = None
    manifest: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# System models
# ---------------------------------------------------------------------------


class SystemStatus(BaseModel):
    """Shell health and runtime state."""

    shell_version: str
    core_connected: bool
    core_url: str
    last_core_check: str | None = None   # ISO 8601 timestamp of last health check
    modules_loaded: int
    modules_failed: int
    userdb_path: str
    uptime_seconds: float
    cache_size: int = 0                  # Number of cached catalogue entries


class CapabilityParam(BaseModel):
    """A single parameter for a capability endpoint."""

    name: str
    type: str
    required: bool
    description: str = ""


class Capability(BaseModel):
    """Machine-readable description of a single Shell API operation."""

    method: str
    path: str
    description: str
    tags: list[str] = Field(default_factory=list)
    params: list[CapabilityParam] = Field(default_factory=list)


class CapabilitiesResponse(BaseModel):
    """Full list of available Shell operations (for MCP tool generation)."""

    version: str
    capabilities: list[Capability]


# ---------------------------------------------------------------------------
# Package and registry models
# ---------------------------------------------------------------------------


class PackageInstallRequest(BaseModel):
    """Request body for installing a package."""

    name: str | None = None        # Package name (resolved via registry)
    source: str | None = None      # Direct Git URL or local path
    version: str | None = None     # Pin to specific version (None = latest)


class InstalledPackage(BaseModel):
    """A non-module installed package (widget-pack, catalogue, data)."""

    name: str
    type: str
    version: str
    git_url: str | None = None
    package_path: str | None = None
    installed_at: str
    registry_name: str | None = None


class RegistryRecord(BaseModel):
    """A configured package registry."""

    name: str
    git_url: str
    added_at: str
    last_refreshed: str | None = None
    package_count: int = 0          # Populated from the cloned index.json


class RegistryAddRequest(BaseModel):
    """Request body for adding a new registry."""

    name: str
    git_url: str


class InstallResult(BaseModel):
    """Outcome of an install or uninstall operation."""

    success: bool
    package_name: str
    package_type: str
    version: str
    restart_required: bool = False
    message: str = ""
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Error detail model — included in all non-2xx responses
# ---------------------------------------------------------------------------


class ErrorDetail(BaseModel):
    """Structured error response with actionable context for AI consumers."""

    error: str
    detail: str | None = None
    path: str | None = None
    suggestion: str | None = None
