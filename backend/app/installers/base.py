"""Base types shared by all installers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InstallResult:
    """The outcome of a package install or uninstall operation."""

    success: bool
    package_name: str
    package_type: str
    version: str
    restart_required: bool = False
    message: str = ""
    warnings: list[str] = field(default_factory=list)
