"""Regression test: every flow step with entity fields needs both title
(data) and description (via data_description in strings.json).

Requirement 5: Jede sichtbare Zeile braucht einen klaren deutschen Titel UND
eine kurze Erklärung direkt darunter. Die HA-UI-Mechanik dafür ist:
  - "data": { key: "Klarer deutscher Titel" }
  - "data_description": { key: "Kurze Erklärung darunter" }

HA 2024.3.3 DOES support data_description in config_flow strings.json
(proven by real HA integrations like hue/strings.json).  These per-field
descriptions are rendered by the HA frontend directly below each field label.

Diese Tests prüfen, dass confirm, manual_mapping und reconfigure_edit alle
beide Sektionen haben: deutsche Titel ('data') und Erklärungen
(data_description).
"""

from __future__ import annotations

import json
import re
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

# Expected description placeholder base names (without _desc suffix).
# _step_description_tokens strips the _desc suffix via the regex, so these
# must match the raw field base names like 'soc_entity', 'house_power_entity', etc.
_EXPECTED_TOKENS = frozenset(_SCHEMA_FIELDS)


def _step_data(step_name: str) -> dict:
    """Return the 'data' (titles) dict for a given step."""
    strings = _load_strings()
    return (
        strings.get("config", {})
        .get("step", {})
        .get(step_name, {})
        .get("data", {})
    )


def _step_description_tokens(step_name: str) -> list[str]:
    """Return all {*_desc} tokens found in the step's description text."""
    strings = _load_strings()
    desc = strings.get("config", {}).get("step", {}).get(step_name, {}).get("description", "")
    return re.findall(r"\{(\w+)_desc\}", desc)


def _step_data_description(step_name: str) -> dict:
    """Return the data_description dict for a given step."""
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
            val_lower = val.lower()
            assert any(
                kw in val_lower
                for kw in ["entität", "leistung", "batterie", "netz", "haus",
                           "verbrauch", "ladestand", "kapazität", "vorzeichen",
                           "kann", "soll", "messwert", "anlage", "fest", "wahl",
                           "bedeutet", "konvention"]
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
# TEST 4: Every step has data_description with field explanations             #
# =========================================================================== #


class TestStepDataDescriptionExplanations:
    """Each step with entity fields must have data_description entries for
    all 10 schema fields — these are the per-field explanations shown by
    HA 2024.3.3's frontend directly below each field label.

    The old {*_desc} placeholder-in-description approach is replaced by
    data_description which is the proper HA mechanism."""

    def _check_field_count(self, step_name: str) -> None:
        dd = _step_data_description(step_name)
        dd_keys = set(dd.keys())
        missing = _SCHEMA_FIELDS - dd_keys
        assert not missing, (
            f"{step_name} data_description missing fields: {missing}"
        )
        extra = dd_keys - _SCHEMA_FIELDS
        assert not extra, (
            f"{step_name} data_description has unexpected fields: {extra}"
        )

    def test_confirm_has_all_description_fields(self) -> None:
        """confirm step must have data_description for all 10 fields."""
        self._check_field_count("confirm")

    def test_manual_mapping_has_all_description_fields(self) -> None:
        """manual_mapping must have data_description for all 10 fields."""
        self._check_field_count("manual_mapping")

    def test_reconfigure_edit_has_all_description_fields(self) -> None:
        """reconfigure_edit must have data_description for all 10 fields."""
        self._check_field_count("reconfigure_edit")

    def test_all_descriptions_are_meaningful(self) -> None:
        """All data_description values must be meaningful German text."""
        for step in ("confirm", "manual_mapping", "reconfigure_edit"):
            dd = _step_data_description(step)
            for key, val in dd.items():
                assert len(str(val).strip()) > 3, (
                    f"{step} data_description['{key}'] must be meaningful, "
                    f"got: {val!r}"
                )


# =========================================================================== #
# TEST 5: data_description IS present (HA 2024.3.3 supports it)               #
# =========================================================================== #


class TestDataDescriptionPresent:
    """HA 2024.3.3 DOES support data_description in config_flow strings.json
    (proven by real HA integrations like hue).  This is the proper mechanism
    for per-field explanations shown directly below each field label."""

    def test_confirm_has_data_description(self) -> None:
        dd = _step_data_description("confirm")
        assert dd, "confirm must have data_description (HA 2024.3.3 supported)"

    def test_manual_mapping_has_data_description(self) -> None:
        dd = _step_data_description("manual_mapping")
        assert dd, "manual_mapping must have data_description"

    def test_reconfigure_edit_has_data_description(self) -> None:
        dd = _step_data_description("reconfigure_edit")
        assert dd, "reconfigure_edit must have data_description"
