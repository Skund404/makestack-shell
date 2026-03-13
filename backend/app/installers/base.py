"""Base types shared by all installers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InstallResult:
    """The outcome of a package install or uninstall operation.

    The base fields (success through warnings) are unchanged from Phase 6.
    The Phase 10 fields (steps_completed through suggestion) have defaults so
    all existing callers continue to compile without modification.
    """

    # --- Base fields (Phase 6) ---
    success: bool
    package_name: str
    package_type: str
    version: str
    restart_required: bool = False
    message: str = ""
    warnings: list[str] = field(default_factory=list)

    # --- Phase 10 fields ---
    steps_completed: list[str] = field(default_factory=list)
    failed_step: str | None = None      # Which step caused the failure
    rolled_back: bool = False           # Was rollback attempted?
    rollback_clean: bool = True         # Did rollback succeed fully?
    suggestion: str | None = None       # What to do next (human + Claude readable)
