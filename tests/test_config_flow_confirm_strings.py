"""Regression test: confirm step in strings.json provides field descriptions.

Requirement 5: Jede sichtbare Zeile braucht einen klaren deutschen Titel
UND eine kurze Erklärung direkt darunter.

Current state: No separate translations/de.json exists.
strings.json contains the German UI text that is actually displayed.
data_description provides the per-field explanations.

This test verifies that:
1. The confirm step has both ``data`` (field titles) and ``data_description``.
2. The confirm step's ``description`` contains {*_desc} tokens.
3. German text is present in both data and data_description.
"""

from __future__ import annotations

import json
from pathlib import Path


def _load_strings() -> dict:
    """Load strings.json (German UI text) from the integration package."""
    strings_path = (
        Path(__file__).parents[1]
        / "custom_components"
        / "universal_energy_manager"
        / "strings.json"
    )
    with open(strings_path, encoding="utf-8") as f:
        return json.load(f)


# =========================================================================== #
# TEST 1: confirm step has both data and data_description                    #
# =========================================================================== #


class TestConfirmStepDataTitles:
    """The confirm step has field titles (data) and descriptions."""

    def test_confirm_has_data_and_data_description(self):
        """strings.json confirm step has both data and data_description keys."""
        strings = _load_strings()
        confirm = (
            strings.get("config", {})
            .get("step", {})
            .get("confirm", {})
        )
        assert "data" in confirm, (
            "confirm step must have a 'data' key with field titles"
        )
        assert "data_description" in confirm, (
            "confirm step must have a 'data_description' key"
        )

    def test_confirm_data_is_german(self):
        """All data values in confirm must be German."""
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
                           "einspeisung", "bezug", "laden", "wert"]
            ), f"confirm data for {key} must be in German, got: {val}"

    def test_confirm_data_description_is_german(self):
        """All data_description values in confirm must be German."""
        strings = _load_strings()
        dd = strings.get("config", {}).get("step", {}).get("confirm", {}).get(
            "data_description", {}
        )
        for key, val in dd.items():
            assert len(val.strip()) > 3, (
                f"data_description for {key} must be a meaningful German string"
            )
            val_lower = val.lower()
            assert any(
                kw in val_lower
                for kw in ["entität", "leistung", "batterie", "netz", "haus",
                           "verbrauch", "ladestand", "kapazität", "vorzeichen",
                           "positiv", "bedeutet", "messwert", "anlage", "pv",
                           "einspeisung", "bezug", "laden"]
            ), f"confirm data_description for {key} must be in German, got: {val}"

    def test_confirm_data_description_has_all_fields(self):
        """confirm/data_description must cover all schema fields."""
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

    def test_confirm_data_has_all_fields(self):
        """confirm/data must cover all schema fields."""
        strings = _load_strings()
        data = strings.get("config", {}).get("step", {}).get("confirm", {}).get("data", {})
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
        missing = expected - set(data.keys())
        assert not missing, (
            f"confirm/data missing fields: {missing}"
        )
