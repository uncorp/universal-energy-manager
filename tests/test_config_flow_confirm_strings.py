"""Regression test: confirm step in de.json provides German field descriptions.

Requirement 5: Jede sichtbare Zeile braucht einen klaren deutschen Titel
UND eine kurze Erklärung direkt darunter.

With de.json now present (created by Stefan's HA-version commit), the German
UI text lives in translations/de.json, not strings.json (which holds the
English base locale). This test validates the German translations in de.json.

This test verifies that:
1. The confirm step has both ``data`` (field titles) and ``data_description``.
2. The confirm step's ``description`` contains {*_desc} tokens for per-field
   explanations.
3. All data and data_description values are in German.
"""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_MANUAL_CAPACITY_KWH,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_INVERT_GRID_POWER_SIGN,
    CONF_MAX_CHARGE_MANUAL_POWER_W,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
)


def _load_de_strings() -> dict:
    """Load translations/de.json (German UI text) from the integration package."""
    strings_path = (
        Path(__file__).parents[1]
        / "custom_components"
        / "universal_energy_manager"
        / "translations"
        / "de.json"
    )
    with open(strings_path, encoding="utf-8") as f:
        return json.load(f)


def _load_base_strings() -> dict:
    """Load strings.json (base/English locale) from the integration package."""
    strings_path = (
        Path(__file__).parents[1]
        / "custom_components"
        / "universal_energy_manager"
        / "strings.json"
    )
    with open(strings_path, encoding="utf-8") as f:
        return json.load(f)


def _confirm_data() -> dict:
    """Return the confirm step's ``data`` dict from de.json."""
    return _load_de_strings()["config"]["step"]["confirm"]["data"]


def _confirm_data_description() -> dict:
    """Return the confirm step's ``data_description`` dict from de.json."""
    return _load_de_strings()["config"]["step"]["confirm"]["data_description"]


# =========================================================================== #
# TEST 1: confirm step has both data and data_description                    #
# =========================================================================== #


class TestConfirmStepDataTitles:
    """The confirm step has field titles (data) and descriptions."""

    def test_confirm_has_data_and_data_description(self):
        """de.json confirm step has both data and data_description keys."""
        de = _load_de_strings()
        confirm = de.get("config", {}).get("step", {}).get("confirm", {})
        assert "data" in confirm, (
            "confirm step must have a 'data' key with field titles"
        )
        assert "data_description" in confirm, (
            "confirm step must have a 'data_description' key"
        )

    def test_confirm_data_has_soc(self):
        assert CONF_SOC_ENTITY in _confirm_data()

    def test_confirm_data_has_pv_power(self):
        assert CONF_PV_POWER_ENTITY in _confirm_data()

    def test_confirm_data_has_house_power(self):
        assert CONF_HOUSE_POWER_ENTITY in _confirm_data()

    def test_confirm_data_has_battery_charge(self):
        assert CONF_BATTERY_CHARGE_ENTITY in _confirm_data()

    def test_confirm_data_has_grid_export(self):
        assert CONF_GRID_EXPORT_ENTITY in _confirm_data()

    def test_confirm_data_has_grid_sign_convention(self):
        assert CONF_INVERT_GRID_POWER_SIGN in _confirm_data()

    def test_confirm_data_has_battery_capacity(self):
        assert CONF_BATTERY_CAPACITY_ENTITY in _confirm_data()

    def test_confirm_data_has_battery_manual_capacity(self):
        assert CONF_BATTERY_MANUAL_CAPACITY_KWH in _confirm_data()

    def test_confirm_data_has_max_charge_power_entity(self):
        assert CONF_MAX_CHARGE_POWER_ENTITY in _confirm_data()

    def test_confirm_data_has_max_charge_manual_power(self):
        assert CONF_MAX_CHARGE_MANUAL_POWER_W in _confirm_data()

    def test_confirm_data_values_are_german(self):
        """All data values in confirm must be in German."""
        data = _confirm_data()
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
        dd = _confirm_data_description()
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
        dd = _confirm_data_description()
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
            "invert_grid_power_sign",
        }
        missing = expected - set(dd.keys())
        assert not missing, (
            f"confirm/data_description missing fields: {missing}"
        )

    def test_confirm_data_has_all_fields(self):
        """confirm/data must cover all schema fields."""
        data = _confirm_data()
        expected = {
            "soc_entity", "pv_power_entity", "house_power_entity",
            "battery_charge_entity", "battery_capacity_entity",
            "battery_manual_capacity_kwh", "max_charge_power_entity",
            "max_charge_manual_power_w", "grid_export_entity",
            "invert_grid_power_sign",
        }
        missing = expected - set(data.keys())
        assert not missing, (
            f"confirm/data missing fields: {missing}"
        )


# =========================================================================== #
# TEST 2: Confirm step description contains {*_desc} tokens                  #
# =========================================================================== #


class TestConfirmStepDescriptionTokens:
    """The confirm step description must reference per-field explanations."""

    def test_confirm_description_has_soc_token(self):
        de = _load_de_strings()
        desc = de["config"]["step"]["confirm"]["description"]
        assert "{soc_entity_desc}" in desc

    def test_confirm_description_has_pv_token(self):
        de = _load_de_strings()
        desc = de["config"]["step"]["confirm"]["description"]
        assert "{pv_power_entity_desc}" in desc

    def test_confirm_description_has_house_token(self):
        de = _load_de_strings()
        desc = desc = de["config"]["step"]["confirm"]["description"]
        assert "{house_power_entity_desc}" in desc

    def test_confirm_description_has_battery_charge_token(self):
        de = _load_de_strings()
        desc = de["config"]["step"]["confirm"]["description"]
        assert "{battery_charge_entity_desc}" in desc

    def test_confirm_description_has_battery_capacity_token(self):
        de = _load_de_strings()
        desc = de["config"]["step"]["confirm"]["description"]
        assert "{battery_capacity_entity_desc}" in desc

    def test_confirm_description_has_battery_manual_capacity_token(self):
        de = _load_de_strings()
        desc = de["config"]["step"]["confirm"]["description"]
        assert "{battery_manual_capacity_kwh_desc}" in desc

    def test_confirm_description_has_max_charge_power_token(self):
        de = _load_de_strings()
        desc = de["config"]["step"]["confirm"]["description"]
        assert "{max_charge_power_entity_desc}" in desc

    def test_confirm_description_has_max_charge_manual_token(self):
        de = _load_de_strings()
        desc = de["config"]["step"]["confirm"]["description"]
        assert "{max_charge_manual_power_w_desc}" in desc

    def test_confirm_description_has_grid_export_token(self):
        de = _load_de_strings()
        desc = de["config"]["step"]["confirm"]["description"]
        assert "{grid_export_entity_desc}" in desc

    def test_confirm_description_has_invert_token(self):
        de = _load_de_strings()
        desc = de["config"]["step"]["confirm"]["description"]
        assert "{invert_grid_power_sign_desc}" in desc
