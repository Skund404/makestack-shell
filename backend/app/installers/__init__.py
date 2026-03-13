"""Type-specific package installers.

Each installer handles one of the five package types:
  module       — ModuleInstaller
  widget-pack  — WidgetInstaller
  catalogue    — CatalogueInstaller
  data         — DataInstaller
  skill        — SkillInstaller

The PackageInstaller dispatcher selects the right handler based on
the makestack-package.json 'type' field.
"""

from .base import InstallResult
from .catalogue_installer import CatalogueInstaller
from .data_installer import DataInstaller
from .module_installer import ModuleInstaller
from .skill_installer import SkillInstaller
from .widget_installer import WidgetInstaller


class PackageInstaller:
    """Dispatcher: selects the correct type-specific installer and runs it."""

    def __init__(
        self,
        module_installer: ModuleInstaller,
        widget_installer: WidgetInstaller,
        catalogue_installer: CatalogueInstaller,
        data_installer: DataInstaller,
        skill_installer: SkillInstaller,
    ) -> None:
        self._handlers = {
            "module": module_installer,
            "widget-pack": widget_installer,
            "catalogue": catalogue_installer,
            "data": data_installer,
            "skill": skill_installer,
        }

    async def install(
        self,
        package_path: str,
        manifest,  # PackageManifest
        git_url: str | None = None,
        registry_name: str | None = None,
        module_registry=None,
        dry_run: bool = False,
    ) -> InstallResult:
        """Dispatch to the correct type-specific installer."""
        handler = self._handlers.get(manifest.type)
        if handler is None:
            return InstallResult(
                success=False,
                package_name=manifest.name,
                package_type=manifest.type,
                version=manifest.version,
                message=f"Unknown package type '{manifest.type}'.",
            )
        return await handler.install(
            package_path=package_path,
            manifest=manifest,
            git_url=git_url,
            registry_name=registry_name,
            module_registry=module_registry,
            dry_run=dry_run,
        )

    async def uninstall(self, name: str, pkg_type: str) -> InstallResult:
        """Dispatch to the correct type-specific uninstaller."""
        handler = self._handlers.get(pkg_type)
        if handler is None:
            return InstallResult(
                success=False,
                package_name=name,
                package_type=pkg_type,
                version="",
                message=f"Unknown package type '{pkg_type}'.",
            )
        return await handler.uninstall(name)


__all__ = [
    "InstallResult",
    "ModuleInstaller",
    "WidgetInstaller",
    "CatalogueInstaller",
    "DataInstaller",
    "SkillInstaller",
    "PackageInstaller",
]
