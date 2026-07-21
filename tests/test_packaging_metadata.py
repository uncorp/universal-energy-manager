"""Static validation of HACS / Home Assistant packaging metadata.

These tests verify that the integration's manifest and HACS files
satisfy the structural requirements enforced by hassfest and HACS at
install time. A broken manifest blocks installation for every user,
so this is a packaging safety net — not a runtime logic test.

Forbidden modules to touch (Shadow-only lane boundary):
    coordinator.py, config_flow.py, __init__.py, snapshot.py,
    normalization.py, planner.py, or any test thereof.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PKG_ROOT = _REPO_ROOT / "custom_components" / "universal_energy_manager"


# ------------------------------------------------------------------
# Required HA hassfest manifest fields (Home Assistant 2024+)
# ------------------------------------------------------------------
_REQUIRED_MANIFEST_FIELDS: dict[str, type] = {
    "domain": str,
    "name": str,
    "version": str,
    "config_flow": bool,
    "documentation": str,
    "iot_class": str,
}

# Home Assistant 2024.3+ supports optional fields.
# e3dc_rscp is optional, no after_dependencies needed.
_OPTIONAL_MANIFEST_FIELDS: dict[str, type] = {
    "codeowners": list,
    "integration_type": str,
}

# ------------------------------------------------------------------
# hacs.json requirements
# ------------------------------------------------------------------
_REQUIRED_HACS_FIELDS: dict[str, type] = {
    "name": str,
}


def _load_json(filename: str) -> dict:
    """Load a JSON file from the repo root and return the parsed dict."""
    path = _REPO_ROOT / filename
    assert path.exists(), f"{filename} not found at {path}"
    raw = path.read_text(encoding="utf-8")
    return json.loads(raw)


class TestManifestStructure:
    """Validate manifest.json against HA hassfest schema requirements."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.manifest = _load_json(
            "custom_components/universal_energy_manager/manifest.json"
        )

    def test_manifest_is_valid_json(self) -> None:
        """manifest.json must be parseable JSON — the first line of defence."""
        # Already loaded by fixture; if JSON is broken we fail above.

    def test_required_fields_present(self) -> None:
        """Every hassfest-required field must exist in the manifest."""
        for field, expected_type in _REQUIRED_MANIFEST_FIELDS.items():
            assert field in self.manifest, f"Missing required field: {field}"
            actual = type(self.manifest[field]).__name__
            assert isinstance(
                self.manifest[field], expected_type
            ), f"Field {field}: expected {expected_type.__name__}, got {actual}"

    def test_optional_fields_present(self) -> None:
        """Optional manifest fields should be present when configured."""
        for field, expected_type in _OPTIONAL_MANIFEST_FIELDS.items():
            assert field in self.manifest, f"Missing optional field: {field}"
            actual = type(self.manifest[field]).__name__
            assert isinstance(
                self.manifest[field], expected_type
            ), f"Field {field}: expected {expected_type.__name__}, got {actual}"

    def test_version_is_semver(self) -> None:
        """Version must follow MAJOR.MINOR.PATCH format."""
        version = self.manifest["version"]
        parts = version.split(".")
        assert len(parts) == 3, f"Version {version!r} must have exactly 3 parts"
        for part in parts:
            assert part.isdigit(), f"Version part {part!r} is not numeric"

    def test_domain_matches_directory_name(self) -> None:
        """The manifest domain must match the integration directory name."""
        domain = self.manifest["domain"]
        expected_dir = _PKG_ROOT.name
        assert domain == expected_dir, (
            f"Domain {domain!r} does not match directory "
            f"name {expected_dir!r}"
        )


class TestHacsMetadata:
    """Validate hacs.json structure."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.hacs = _load_json("hacs.json")

    def test_hacs_json_is_valid(self) -> None:
        """hacs.json must be valid JSON."""
        assert isinstance(self.hacs, dict), "hacs.json must contain a JSON object"

    def test_required_fields_present(self) -> None:
        """hacs.json must have a 'name' field."""
        for field, expected_type in _REQUIRED_HACS_FIELDS.items():
            assert field in self.hacs, f"Missing required hacs.json field: {field}"
            actual = type(self.hacs[field]).__name__
            assert isinstance(
                self.hacs[field], expected_type
            ), f"Field {field}: expected {expected_type.__name__}, got {actual}"


class TestIntegrationFiles:
    """Ensure the integration directory contains all required files."""

    def test_integration_has_manifest(self) -> None:
        assert (_PKG_ROOT / "manifest.json").exists()

    def test_integration_has_init(self) -> None:
        assert (_PKG_ROOT / "__init__.py").exists()

    def test_integration_has_strings(self) -> None:
        """A config_flow integration must have strings.json for i18n."""
        assert (_PKG_ROOT / "strings.json").exists()
        strings = _load_json("custom_components/universal_energy_manager/strings.json")
        assert isinstance(strings, dict), "strings.json must be a JSON object"
