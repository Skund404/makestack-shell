"""Phase 10 test suite — package manager hardening.

Tests each failure fixture to verify:
  - The right error is returned
  - The system is clean after the failure (no partial state left behind)

Fixtures live in backend/tests/fixtures/.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from backend.app.installers.module_installer import (
    ModuleInstaller,
    _check_conflicts,
    _check_down_migrations,
)
from backend.app.installers.skill_installer import SkillInstaller
from backend.app.package_manifest import PackageManifest
from backend.app.userdb import UserDB
from pydantic import ValidationError

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db():
    """In-memory UserDB with all migrations applied."""
    database = UserDB(":memory:", dev_mode=True)
    await database.open()
    await database.run_migrations()
    yield database
    await database.close()


def _empty_registry():
    """A mock ModuleRegistry with no loaded modules."""
    registry = MagicMock()
    registry.get_all_keywords.return_value = {}
    registry.get_all_panels.return_value = []
    registry._shell_view_claims = {}
    return registry


def _registry_with_panel(panel_id: str, module_name: str):
    """A mock ModuleRegistry with one panel already claimed."""
    registry = MagicMock()
    registry.get_all_keywords.return_value = {}
    registry.get_all_panels.return_value = [{"id": panel_id, "module": module_name}]
    registry._shell_view_claims = {}
    return registry


def _pkg_manifest(fixture_name: str) -> PackageManifest:
    """Parse the makestack-package.json from a fixture directory."""
    import json
    pkg_json = FIXTURES / fixture_name / "makestack-package.json"
    raw = json.loads(pkg_json.read_text())
    return PackageManifest.model_validate(raw)


# ---------------------------------------------------------------------------
# PackageManifest validation — missing-name, empty-version, bad-semver
# ---------------------------------------------------------------------------


def test_missing_name_fails_package_manifest_validation():
    """An empty package name must fail PackageManifest validation."""
    with pytest.raises(ValidationError) as exc_info:
        _pkg_manifest("missing-name")
    errors = exc_info.value.errors()
    assert any("name" in str(e["loc"]) for e in errors), \
        f"Expected error on 'name' field, got: {errors}"


def test_empty_version_fails_package_manifest_validation():
    """An empty version string must fail PackageManifest validation."""
    with pytest.raises(ValidationError) as exc_info:
        _pkg_manifest("empty-version")
    errors = exc_info.value.errors()
    assert any("version" in str(e["loc"]) for e in errors), \
        f"Expected error on 'version' field, got: {errors}"


def test_bad_semver_fails_package_manifest_validation():
    """'latest' is not a valid semver and must fail PackageManifest validation."""
    with pytest.raises(ValidationError) as exc_info:
        _pkg_manifest("bad-semver")
    errors = exc_info.value.errors()
    assert any("version" in str(e["loc"]) for e in errors), \
        f"Expected error on 'version' field, got: {errors}"


# ---------------------------------------------------------------------------
# ModuleInstaller — no-manifest (step 1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_manifest_fails_at_step1(db):
    """A module without manifest.json fails at validate_manifest."""
    fixture_path = str(FIXTURES / "no-manifest")
    pkg = _pkg_manifest("no-manifest")
    installer = ModuleInstaller(db)
    result = await installer.install(
        package_path=fixture_path,
        manifest=pkg,
        module_registry=_empty_registry(),
    )
    assert not result.success
    assert result.failed_step == "validate_manifest"
    assert "manifest.json" in result.message

    # System is clean — no transaction left in_progress
    row = await db.fetch_one(
        "SELECT status FROM install_transactions WHERE package_name = ?",
        ["no-manifest"],
    )
    assert row is None or row["status"] != "in_progress"


# ---------------------------------------------------------------------------
# ModuleInstaller — invalid-manifest-field (step 1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_manifest_field_fails_at_step1(db):
    """has_backend='yes-please' fails ModuleManifest Pydantic validation."""
    fixture_path = str(FIXTURES / "invalid-manifest-field")
    pkg = _pkg_manifest("invalid-manifest-field")
    installer = ModuleInstaller(db)
    result = await installer.install(
        package_path=fixture_path,
        manifest=pkg,
        module_registry=_empty_registry(),
    )
    assert not result.success
    assert result.failed_step == "validate_manifest"
    assert "has_backend" in result.message or "validation" in result.message.lower()


# ---------------------------------------------------------------------------
# ModuleInstaller — compat-fail (step 2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compat_fail_fails_at_step2(db):
    """shell_compatibility >=99.0.0 fails the shell version check."""
    fixture_path = str(FIXTURES / "compat-fail")
    # compat-fail makestack-package.json has shell_compatibility >=99.0.0
    # which will cause PackageManifest.model_validate to fail.
    # The module installer checks shell_compatibility from manifest.json (step 2).
    import json
    pkg_raw = json.loads((FIXTURES / "compat-fail" / "makestack-package.json").read_text())
    # Strip shell_compatibility from package manifest so it passes pkg validation
    pkg_raw.pop("shell_compatibility", None)
    pkg = PackageManifest.model_validate(pkg_raw)

    installer = ModuleInstaller(db)
    result = await installer.install(
        package_path=fixture_path,
        manifest=pkg,
        module_registry=_empty_registry(),
    )
    assert not result.success
    assert result.failed_step == "check_compat"
    assert "99.0.0" in result.message or "shell" in result.message.lower()
    assert "validate_manifest" in result.steps_completed


# ---------------------------------------------------------------------------
# ModuleInstaller — keyword-conflict (step 3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_keyword_conflict_fails_at_step3(db):
    """TIMER_ is a core keyword — any module claiming it must be rejected."""
    fixture_path = str(FIXTURES / "keyword-conflict")
    pkg = _pkg_manifest("keyword-conflict")
    installer = ModuleInstaller(db)
    result = await installer.install(
        package_path=fixture_path,
        manifest=pkg,
        module_registry=_empty_registry(),
    )
    assert not result.success
    assert result.failed_step == "check_conflicts"
    assert "TIMER_" in result.message
    assert "core keyword" in result.message.lower()
    # Validate and compat steps completed before conflict check
    assert "validate_manifest" in result.steps_completed
    assert "check_compat" in result.steps_completed


@pytest.mark.asyncio
async def test_all_keyword_conflicts_reported(db):
    """All conflicts must be reported, not just the first one."""
    # Build a manifest with multiple core-keyword conflicts directly
    from backend.app.module_manifest import ModuleManifest, ModuleKeyword
    manifest = ModuleManifest(
        name="multi-conflict",
        display_name="Multi Conflict",
        version="1.0.0",
        description="test",
        author="test",
        keywords=[
            ModuleKeyword(keyword="TIMER_", description="timer", renderer="A"),
            ModuleKeyword(keyword="IMAGE_", description="image", renderer="B"),
        ],
    )
    conflicts = _check_conflicts(manifest, _empty_registry())
    assert len(conflicts) == 2
    keywords_mentioned = " ".join(conflicts)
    assert "TIMER_" in keywords_mentioned
    assert "IMAGE_" in keywords_mentioned


# ---------------------------------------------------------------------------
# ModuleInstaller — panel-conflict (step 3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_panel_conflict_fails_at_step3(db):
    """A panel ID already claimed by another module must be rejected."""
    fixture_path = str(FIXTURES / "panel-conflict")
    pkg = _pkg_manifest("panel-conflict")
    # Simulate a registry that already has 'already-claimed-panel' from 'other-module'
    registry = _registry_with_panel("already-claimed-panel", "other-module")
    installer = ModuleInstaller(db)
    result = await installer.install(
        package_path=fixture_path,
        manifest=pkg,
        module_registry=registry,
    )
    assert not result.success
    assert result.failed_step == "check_conflicts"
    assert "already-claimed-panel" in result.message


# ---------------------------------------------------------------------------
# ModuleInstaller — missing-down (step 4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_down_fails_at_step4(db):
    """A migration without down() must fail at check_down_migrations."""
    fixture_path = str(FIXTURES / "missing-down")
    pkg = _pkg_manifest("missing-down")
    installer = ModuleInstaller(db)
    result = await installer.install(
        package_path=fixture_path,
        manifest=pkg,
        module_registry=_empty_registry(),
    )
    assert not result.success
    assert result.failed_step == "check_down_migrations"
    assert "001_initial.py" in result.message
    # No DB state written — all validation steps before step 5
    rows = await db.fetch_all(
        "SELECT * FROM installed_modules WHERE name = ?", ["missing-down"]
    )
    assert rows == []


def test_check_down_migrations_detects_missing_down():
    """_check_down_migrations returns the filename of the bad migration."""
    bad = _check_down_migrations(str(FIXTURES / "missing-down"))
    assert "001_initial.py" in bad


def test_check_down_migrations_passes_for_valid_module():
    """A module with proper down() functions returns an empty list."""
    # broken-up has down() — only up() raises
    bad = _check_down_migrations(str(FIXTURES / "broken-up"))
    assert bad == []


# ---------------------------------------------------------------------------
# ModuleInstaller — broken-up (step 6) — triggers rollback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broken_up_fails_at_step6_and_rolls_back(db):
    """A migration whose up() raises must fail at run_migrations and roll back."""
    fixture_path = str(FIXTURES / "broken-up")
    pkg = _pkg_manifest("broken-up")
    installer = ModuleInstaller(db)
    result = await installer.install(
        package_path=fixture_path,
        manifest=pkg,
        module_registry=_empty_registry(),
    )
    assert not result.success
    assert result.failed_step == "run_migrations"
    assert result.rolled_back is True
    assert "Intentional migration failure" in result.message

    # Validation steps and snapshot step should have completed
    assert "validate_manifest" in result.steps_completed
    assert "check_conflicts" in result.steps_completed
    assert "check_down_migrations" in result.steps_completed

    # Module must NOT be in installed_modules
    row = await db.fetch_one(
        "SELECT name FROM installed_modules WHERE name = ?", ["broken-up"]
    )
    assert row is None

    # Transaction must be marked rolled_back, not in_progress
    tx = await db.fetch_one(
        "SELECT status FROM install_transactions WHERE package_name = ?",
        ["broken-up"],
    )
    assert tx is not None
    assert tx["status"] == "rolled_back"


# ---------------------------------------------------------------------------
# SkillInstaller — zero-byte-skill
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zero_byte_skill_fails(db):
    """An empty skill.md must be rejected by SkillInstaller."""
    fixture_path = str(FIXTURES / "zero-byte-skill")
    pkg = _pkg_manifest("zero-byte-skill")
    installer = SkillInstaller(db)
    result = await installer.install(
        package_path=fixture_path,
        manifest=pkg,
    )
    assert not result.success
    assert "empty" in result.message.lower()

    # Not registered in installed_packages
    row = await db.fetch_one(
        "SELECT name FROM installed_packages WHERE name = ?", ["zero-byte-skill"]
    )
    assert row is None


# ---------------------------------------------------------------------------
# Dry-run mode — validation only, no DB writes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dry_run_valid_module_succeeds_with_no_writes(db):
    """Dry-run on a valid module returns success without touching the DB."""
    # Use the broken-up fixture — it passes steps 1–4 but fails on step 6.
    # Dry-run should succeed (only steps 1–4 run).
    fixture_path = str(FIXTURES / "broken-up")
    pkg = _pkg_manifest("broken-up")
    installer = ModuleInstaller(db)
    result = await installer.install(
        package_path=fixture_path,
        manifest=pkg,
        module_registry=_empty_registry(),
        dry_run=True,
    )
    assert result.success
    assert "Dry run" in result.message
    # Steps 1–4 should all be in steps_completed
    assert "validate_manifest" in result.steps_completed
    assert "check_down_migrations" in result.steps_completed
    # No transaction row written (dry_run skips DB writes)
    tx = await db.fetch_one(
        "SELECT id FROM install_transactions WHERE package_name = ?",
        ["broken-up"],
    )
    assert tx is None
    # Not registered
    row = await db.fetch_one(
        "SELECT name FROM installed_modules WHERE name = ?", ["broken-up"]
    )
    assert row is None


@pytest.mark.asyncio
async def test_dry_run_stops_at_validation_failure(db):
    """Dry-run reports failure without creating any DB state."""
    fixture_path = str(FIXTURES / "keyword-conflict")
    pkg = _pkg_manifest("keyword-conflict")
    installer = ModuleInstaller(db)
    result = await installer.install(
        package_path=fixture_path,
        manifest=pkg,
        module_registry=_empty_registry(),
        dry_run=True,
    )
    assert not result.success
    assert result.failed_step == "check_conflicts"
    # No transaction row written
    tx = await db.fetch_one(
        "SELECT id FROM install_transactions WHERE package_name = ?",
        ["keyword-conflict"],
    )
    assert tx is None


# ---------------------------------------------------------------------------
# SkillInstaller — dry-run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_dry_run(db):
    """Dry-run on a valid skill returns success without writing files."""
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a minimal valid skill package
        pkg_path = Path(tmpdir)
        (pkg_path / "makestack-package.json").write_text(
            '{"name": "my-skill", "type": "skill", "version": "1.0.0"}'
        )
        (pkg_path / "skill.md").write_text("# My Skill\nSome content.")
        import json as _json
        raw = _json.loads((pkg_path / "makestack-package.json").read_text())
        pkg = PackageManifest.model_validate(raw)

        installer = SkillInstaller(db)
        result = await installer.install(
            package_path=str(pkg_path),
            manifest=pkg,
            dry_run=True,
        )
    assert result.success
    assert "Dry run" in result.message
    # Not registered
    row = await db.fetch_one(
        "SELECT name FROM installed_packages WHERE name = ?", ["my-skill"]
    )
    assert row is None
