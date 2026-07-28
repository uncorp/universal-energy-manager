"""Regression test: every flow step with entity fields needs both title
(data) and description (data_description).

Requirement 5: Jede sichtbare Zeile braucht einen klaren deutschen Titel UND
eine kurze Erklärung direkt darunter. Die HA-UI-Mechanik dafür ist:
  - "data": { key: "Klarer deutscher Titel" }
  - "data_description": { key: "Kurze Erklärung direkt darunter." }

Diese Tests prüfen, dass confirm, manual_mapping und reconfigure_edit alle
beide Sektionen für alle 10 Schema-Felder haben.
"""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_MANUAL_CAPACITY_KWH,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_POWER_SIGN_CONVENTION,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MAX_CHARGE_MANUAL_POWER_W,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
)


def _load_strings() -> dict:
    """Load strings.json from the integration package."""
    strings_path = (
        Path(__file__).parents[1]
        / "custom_components"
        / "universal_energy_manager"
        / "strings.json"
    )
    with open(strings_path, encoding="utf-8") as f:
        return json.load(f)


# All 10 schema fields that need titles + descriptions
_SCHEMA_FIELDS = frozenset({
    CONF_SOC_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_MANUAL_CAPACITY_KWH,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_MAX_CHARGE_MANUAL_POWER_W,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_POWER_SIGN_CONVENTION,
})


def _step_data(step_name: str) -> dict:
    """Return the 'data' (titles) dict for a given step."""
    strings = _load_strings()
    return (
        strings.get("config", {})
        .get("step", {})
        .get(step_name, {})
        .get("data", {})
    )


def _step_data_description(step_name: str) -> dict:
    """Return the 'data_description' dict for a given step."""
    strings = _load_strings()
    return (
        strings.get("config", {})
        .get("step", {})
        .get(step_name, {})
        .get("data_description", {})
    )


# =========================================================================== #
# TEST 1: confirm step must have "data" titles                                #
# =========================================================================== #


class TestConfirmStepDataTitles:
    """confirm step needs clear German titles (data section)."""

    def test_confirm_has_data_key(self) -> None:
        """strings.json confirm step must have a 'data' key with titles."""
        strings = _load_strings()
        confirm = strings.get("config", {}).get("step", {}).get("confirm", {})
        assert "data" in confirm, (
            "confirm step must have a 'data' section for field titles"
        )

    def test_confirm_data_has_all_titles(self) -> None:
        """Every schema field must have a German title in confirm/data."""
        data = _step_data("confirm")
        missing = _SCHEMA_FIELDS - set(data.keys())
        assert not missing, (
            f"confirm/data missing titles for: {missing}"
        )

    def test_confirm_data_titles_are_german(self) -> None:
        """All confirm/data titles must be meaningful German text."""
        data = _step_data("confirm")
        for key, val in data.items():
            assert len(val.strip()) > 2, (
                f"confirm/data[{key}] must be a meaningful title, got: {val!r}"
            )
            # Titles should not contain English technical jargon as primary
            val_lower = val.lower()
            assert any(
                kw in val_lower
                for kw in ["entität", "leistung", "batterie", "netz", "haus",
                           "verbrauch", "ladestand", "kapazität", "vorzeichen",
                           "kann", "soll", "messwert", "anlage", "fest", "wahl",
                           "bedeutet", "wahl", "konvention"]
            ), (
                f"confirm/data[{key}] = {val!r} is not a proper German title"
            )


# =========================================================================== #
# TEST 2: manual_mapping step already has "data" titles                       #
# =========================================================================== #


class TestManualMappingDataTitles:
    """manual_mapping step must have clear German titles (data section)."""

    def test_manual_mapping_has_data_key(self) -> None:
        strings = _load_strings()
        mm = strings.get("config", {}).get("step", {}).get("manual_mapping", {})
        assert "data" in mm, (
            "manual_mapping must have a 'data' section for field titles"
        )

    def test_manual_mapping_data_has_all_titles(self) -> None:
        data = _step_data("manual_mapping")
        missing = _SCHEMA_FIELDS - set(data.keys())
        assert not missing, (
            f"manual_mapping/data missing titles for: {missing}"
        )


# =========================================================================== #
# TEST 3: reconfigure_edit step must have "data" titles                       #
# =========================================================================== #


class TestReconfigureEditDataTitles:
    """reconfigure_edit step needs clear German titles (data section)."""

    def test_reconfigure_edit_has_data_key(self) -> None:
        """strings.json reconfigure_edit step must have a 'data' key."""
        strings = _load_strings()
        re = strings.get("config", {}).get("step", {}).get("reconfigure_edit", {})
        assert "data" in re, (
            "reconfigure_edit must have a 'data' section for field titles"
        )

    def test_reconfigure_edit_data_has_all_titles(self) -> None:
        """Every schema field must have a German title in reconfigure_edit/data."""
        data = _step_data("reconfigure_edit")
        missing = _SCHEMA_FIELDS - set(data.keys())
        assert not missing, (
            f"reconfigure_edit/data missing titles for: {missing}"
        )

    def test_reconfigure_edit_data_titles_are_german(self) -> None:
        """All reconfigure_edit/data titles must be meaningful German text."""
        data = _step_data("reconfigure_edit")
        for key, val in data.items():
            assert len(val.strip()) > 2, (
                f"reconfigure_edit/data[{key}] must be a meaningful title, got: {val!r}"
            )


# =========================================================================== #
# TEST 4: Pairing — every field has BOTH title and description                #
# =========================================================================== #


class TestDataDescriptionPairing:
    """For every flow step with entity fields, each field must have both
    a German title ('data') AND a German explanation ('data_description')."""

    def _check_pairing(self, step_name: str) -> None:
        """Assert both 'data' and 'data_description' exist and cover all fields."""
        data = _step_data(step_name)
        desc = _step_data_description(step_name)
        missing_title = _SCHEMA_FIELDS - set(data.keys())
        missing_desc = _SCHEMA_FIELDS - set(desc.keys())
        assert not missing_title, (
            f"{step_name}/data missing titles for: {missing_title}"
        )
        assert not missing_desc, (
            f"{step_name}/data_description missing descriptions for: {missing_desc}"
        )

    def test_confirm_has_both_title_and_description(self) -> None:
        """confirm step must have both 'data' and 'data_description' for all fields."""
        self._check_pairing("confirm")

    def test_manual_mapping_has_both_title_and_description(self) -> None:
        """manual_mapping must have both 'data' and 'data_description' for all fields."""
        self._check_pairing("manual_mapping")

    def test_reconfigure_edit_has_both_title_and_description(self) -> None:
        """reconfigure_edit must have both 'data' and 'data_description' for all fields."""
        self._check_pairing("reconfigure_edit")
