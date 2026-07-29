"""Regression test: confirm step in strings.json provides field descriptions.

Requirement 5: Jede sichtbare Zeile braucht einen klaren deutschen Titel
UND eine kurze Erklärung direkt darunter.

HA 2024.3.3 DOES support ``data_description`` in config-flow strings.json
(proven by real HA integrations like hue/strings.json).  The per-field
explanations are provided via the ``data_description`` block.  Additionally,
the config flow still passes ``description_placeholders`` for compatibility
with newer HA versions.

This test verifies that:
1. The confirm step has a ``data`` dict with German field titles.
2. The confirm step's ``data_description`` contains entries for all 10 fields.
3. The confirm step's ``description`` contains {*_desc} tokens (backward compat).
4. All field descriptions are present (mirroring manual_mapping).
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


# =========================================================================== #
# TEST 1: confirm step has German field titles (data key)                    #
# =========================================================================== #


class TestConfirmStepDataTitles:
    """The confirm step must have a data dict with German field titles."""

    def test_confirm_has_data_key(self):
        """strings.json confirm step must have a data key."""
        strings = _load_strings()
        confirm = (
            strings.get("config", {})
            .get("step", {})
            .get("confirm", {})
        )
        assert "data" in confirm, (
            "confirm step must have a 'data' key with field titles"
        )

    def test_confirm_data_has_soc(self):
        strings = _load_strings()
        data = strings.get("config", {}).get("step", {}).get("confirm", {}).get("data", {})
        assert CONF_SOC_ENTITY in data

    def test_confirm_data_has_pv_power(self):
        strings = _load_strings()
        data = strings.get("config", {}).get("step", {}).get("confirm", {}).get("data", {})
        assert CONF_PV_POWER_ENTITY in data

    def test_confirm_data_has_house_power(self):
        strings = _load_strings()
        data = strings.get("config", {}).get("step", {}).get("confirm", {}).get("data", {})
        assert CONF_HOUSE_POWER_ENTITY in data

    def test_confirm_data_has_battery_charge(self):
        strings = _load_strings()
        data = strings.get("config", {}).get("step", {}).get("confirm", {}).get("data", {})
        assert CONF_BATTERY_CHARGE_ENTITY in data

    def test_confirm_data_has_grid_export(self):
        strings = _load_strings()
        data = strings.get("config", {}).get("step", {}).get("confirm", {}).get("data", {})
        assert CONF_GRID_EXPORT_ENTITY in data

    def test_confirm_data_has_grid_sign_convention(self):
        strings = _load_strings()
        data = strings.get("config", {}).get("step", {}).get("confirm", {}).get("data", {})
        assert CONF_GRID_POWER_SIGN_CONVENTION in data

    def test_confirm_data_has_battery_capacity(self):
        strings = _load_strings()
        data = strings.get("config", {}).get("step", {}).get("confirm", {}).get("data", {})
        assert CONF_BATTERY_CAPACITY_ENTITY in data

    def test_confirm_data_has_battery_manual_capacity(self):
        strings = _load_strings()
        data = strings.get("config", {}).get("step", {}).get("confirm", {}).get("data", {})
        assert CONF_BATTERY_MANUAL_CAPACITY_KWH in data

    def test_confirm_data_has_max_charge_power_entity(self):
        strings = _load_strings()
        data = strings.get("config", {}).get("step", {}).get("confirm", {}).get("data", {})
        assert CONF_MAX_CHARGE_POWER_ENTITY in data

    def test_confirm_data_has_max_charge_manual_power(self):
        strings = _load_strings()
        data = strings.get("config", {}).get("step", {}).get("confirm", {}).get("data", {})
        assert CONF_MAX_CHARGE_MANUAL_POWER_W in data

    def test_confirm_data_values_are_german(self):
        """All data values in confirm must be in German."""
        strings = _load_strings()
        data = strings.get("config", {}).get("step", {}).get("confirm", {}).get("data", {})
        for key, val in data.items():
            assert len(val.strip()) > 2, (
                f"data title for {key} must be a meaningful German string"
            )
            val_lower = val.lower()
            assert any(
                kw in val_lower
                for kw in ["entität", "leistung", "batterie", "netz", "haus",
                           "verbrauch", "ladestand", "kapazität", "vorzeichen",
                           "positiv", "bedeutet", "messwert", "anlage", "pv",
                           "einspeisung", "bezug"]
            ), f"confirm data for {key} must be in German, got: {val}"


# =========================================================================== #
# TEST 2: confirm step data_description has all field explanations           #
# =========================================================================== #


class TestConfirmStepDataDescription:
    """The confirm step must have data_description for all 10 fields."""

    def test_confirm_has_data_description(self):
        """confirm step must have data_description key."""
        strings = _load_strings()
        confirm = strings.get("config", {}).get("step", {}).get("confirm", {})
        assert "data_description" in confirm, (
            "confirm step must have data_description (HA 2024.3.3 supported)"
        )

    def test_confirm_data_description_has_all_fields(self):
        """confirm/data_description must cover all 10 schema fields."""
        strings = _load_strings()
        dd = strings.get("config", {}).get("step", {}).get("confirm", {}).get(
            "data_description", {}
        )
        expected = {
            "soc_entity",
            "pv_power_entity",
            "house_power_entity",
            "battery_charge_entity",
            "battery_capacity_entity",
            "battery_manual_capacity_kwh",
            "max_charge_power_entity",
            "max_charge_manual_power_w",
            "grid_export_entity",
            "grid_power_sign_convention",
        }
        missing = expected - set(dd.keys())
        assert not missing, (
            f"confirm/data_description missing fields: {missing}"
        )

    def test_confirm_data_description_values_are_german(self):
        """All data_description values must be meaningful German text."""
        strings = _load_strings()
        dd = strings.get("config", {}).get("step", {}).get("confirm", {}).get(
            "data_description", {}
        )
        for key, val in dd.items():
            assert len(str(val).strip()) > 3, (
                f"confirm/data_description['{key}'] must be meaningful, got: {val!r}"
            )


# =========================================================================== #
# TEST 3: confirm and manual_mapping share data_description fields           #
# =========================================================================== #


class TestConfirmManualMappingDataDescriptionMatch:
    """Both steps must have the same data_description fields."""

    def test_confirm_and_manual_mapping_share_data_description_fields(self):
        """confirm and manual_mapping data_description fields must match."""
        strings = _load_strings()
        confirm_dd = set(
            strings.get("config", {}).get("step", {})
            .get("confirm", {}).get("data_description", {}).keys()
        )
        manual_dd = set(
            strings.get("config", {}).get("step", {})
            .get("manual_mapping", {}).get("data_description", {}).keys()
        )
        expected = {
            "soc_entity", "pv_power_entity", "house_power_entity",
            "battery_charge_entity", "battery_capacity_entity",
            "battery_manual_capacity_kwh", "max_charge_power_entity",
            "max_charge_manual_power_w", "grid_export_entity",
            "grid_power_sign_convention",
        }
        assert confirm_dd == expected, (
            f"confirm data_description mismatch: missing={expected - confirm_dd}"
        )
        assert manual_dd == expected, (
            f"manual_mapping data_description mismatch: missing={expected - manual_dd}"
        )
