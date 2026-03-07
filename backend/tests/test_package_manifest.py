"""Tests for PackageManifest — makestack-package.json schema."""

import pytest
from pydantic import ValidationError

from backend.app.package_manifest import PackageManifest


# ---------------------------------------------------------------------------
# Valid manifests
# ---------------------------------------------------------------------------


def test_valid_module_manifest():
    m = PackageManifest(name="my-module", type="module", version="1.0.0")
    assert m.name == "my-module"
    assert m.type == "module"
    assert m.version == "1.0.0"


def test_valid_widget_pack_manifest():
    m = PackageManifest(name="timer-widgets", type="widget-pack", version="0.2.1")
    assert m.type == "widget-pack"


def test_valid_catalogue_manifest():
    m = PackageManifest(name="leatherwork", type="catalogue", version="3.0.0")
    assert m.type == "catalogue"


def test_valid_data_manifest():
    m = PackageManifest(name="cyberpunk-theme", type="data", version="1.1.0")
    assert m.type == "data"


def test_optional_fields_default():
    m = PackageManifest(name="my-pkg", type="module", version="0.1.0")
    assert m.description == ""
    assert m.author == ""
    assert m.license == ""
    assert m.shell_compatibility == ""


def test_optional_fields_populated():
    m = PackageManifest(
        name="my-pkg",
        type="module",
        version="1.0.0",
        description="A test package",
        author="Alice",
        license="MIT",
        shell_compatibility=">=0.1.0",
    )
    assert m.description == "A test package"
    assert m.author == "Alice"


# ---------------------------------------------------------------------------
# Name validation
# ---------------------------------------------------------------------------


def test_name_must_start_with_lowercase():
    with pytest.raises(ValidationError, match="invalid"):
        PackageManifest(name="MyModule", type="module", version="1.0.0")


def test_name_cannot_start_with_digit():
    with pytest.raises(ValidationError, match="invalid"):
        PackageManifest(name="1bad", type="module", version="1.0.0")


def test_name_allows_hyphens_and_digits():
    m = PackageManifest(name="my-module-v2", type="module", version="1.0.0")
    assert m.name == "my-module-v2"


def test_name_rejects_underscores():
    with pytest.raises(ValidationError, match="invalid"):
        PackageManifest(name="my_module", type="module", version="1.0.0")


def test_name_rejects_spaces():
    with pytest.raises(ValidationError, match="invalid"):
        PackageManifest(name="my module", type="module", version="1.0.0")


# ---------------------------------------------------------------------------
# Type validation
# ---------------------------------------------------------------------------


def test_type_rejects_unknown():
    with pytest.raises(ValidationError, match="not recognised"):
        PackageManifest(name="pkg", type="plugin", version="1.0.0")


def test_type_rejects_empty():
    with pytest.raises(ValidationError):
        PackageManifest(name="pkg", type="", version="1.0.0")


# ---------------------------------------------------------------------------
# Version validation
# ---------------------------------------------------------------------------


def test_version_must_be_semver():
    with pytest.raises(ValidationError, match="semver"):
        PackageManifest(name="pkg", type="module", version="latest")


def test_version_must_have_three_parts():
    with pytest.raises(ValidationError, match="semver"):
        PackageManifest(name="pkg", type="module", version="1.0")


def test_version_allows_prerelease_suffix():
    # Semver with pre-release suffix is allowed (regex matches leading digits).
    m = PackageManifest(name="pkg", type="module", version="1.0.0-beta.1")
    assert m.version == "1.0.0-beta.1"


# ---------------------------------------------------------------------------
# Model validation from dict (JSON parse path)
# ---------------------------------------------------------------------------


def test_model_validate_from_dict():
    raw = {"name": "my-pkg", "type": "widget-pack", "version": "2.0.0", "description": "Hi"}
    m = PackageManifest.model_validate(raw)
    assert m.name == "my-pkg"
    assert m.description == "Hi"


def test_model_validate_missing_required_field():
    with pytest.raises(ValidationError):
        PackageManifest.model_validate({"name": "pkg", "version": "1.0.0"})  # missing type
