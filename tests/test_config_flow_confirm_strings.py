"""Regression test: confirm step in strings.json must have data_description.

Requirement 5: Jede sichtbare Zeile braucht einen klaren deutschen Titel
UND eine kurze Erklärung direkt darunter. Die HA-UI-Mechanik (data_description
in strings.json) muss für DENSELBEN Fields in confirm wie in manual_mapping
vorhanden sein, da der confirm-Schritt dieselben Felder aus _build_full_schema
nutzt.
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
# TEST 1: confirm step has data_description                                  #
# =========================================================================== #


class TestConfirmStepDataDescription:
    """The confirm step must have a data_description for every schema field."""

    def test_confirm_has_data_description_key(self):
        """strings.json confirm step must have a data_description key."""
        strings = _load_strings()
        confirm = (
            strings.get("config", {})
            .get("step", {})
            .get("confirm", {})
        )
        assert "data_description" in confirm, (
            "confirm step must have a data_description section"
        )

    def test_confirm_data_description_has_soc(self):
        strings = _load_strings()
        dd = (
            strings.get("config", {})
            .get("step", {})
            .get("confirm", {})
            .get("data_description", {})
        )
        assert CONF_SOC_ENTITY in dd

    def test_confirm_data_description_has_pv_power(self):
        strings = _load_strings()
        dd = (
            strings.get("config", {})
            .get("step", {})
            .get("confirm", {})
            .get("data_description", {})
        )
        assert CONF_PV_POWER_ENTITY in dd

    def test_confirm_data_description_has_house_power(self):
        strings = _load_strings()
        dd = (
            strings.get("config", {})
            .get("step", {})
            .get("confirm", {})
            .get("data_description", {})
        )
        assert CONF_HOUSE_POWER_ENTITY in dd
        # Must explain negative values for house power
        desc_text = dd[CONF_HOUSE_POWER_ENTITY]
        assert (
            "negativ" in desc_text.lower()
            or "balkonkraftwerk" in desc_text.lower()
        ), (
            "confirm data_description for house_power_entity must explain "
            "negative values (Balkonkraftwerk)"
        )

    def test_confirm_data_description_has_battery_charge(self):
        strings = _load_strings()
        dd = (
            strings.get("config", {})
            .get("step", {})
            .get("confirm", {})
            .get("data_description", {})
        )
        assert CONF_BATTERY_CHARGE_ENTITY in dd

    def test_confirm_data_description_has_grid_export(self):
        strings = _load_strings()
        dd = (
            strings.get("config", {})
            .get("step", {})
            .get("confirm", {})
            .get("data_description", {})
        )
        assert CONF_GRID_EXPORT_ENTITY in dd

    def test_confirm_data_description_has_grid_sign_convention(self):
        strings = _load_strings()
        dd = (
            strings.get("config", {})
            .get("step", {})
            .get("confirm", {})
            .get("data_description", {})
        )
        assert CONF_GRID_POWER_SIGN_CONVENTION in dd

    def test_confirm_data_description_has_battery_capacity(self):
        strings = _load_strings()
        dd = (
            strings.get("config", {})
            .get("step", {})
            .get("confirm", {})
            .get("data_description", {})
        )
        assert CONF_BATTERY_CAPACITY_ENTITY in dd

    def test_confirm_data_description_has_battery_manual_capacity(self):
        strings = _load_strings()
        dd = (
            strings.get("config", {})
            .get("step", {})
            .get("confirm", {})
            .get("data_description", {})
        )
        assert CONF_BATTERY_MANUAL_CAPACITY_KWH in dd

    def test_confirm_data_description_has_max_charge_power_entity(self):
        strings = _load_strings()
        dd = (
            strings.get("config", {})
            .get("step", {})
            .get("confirm", {})
            .get("data_description", {})
        )
        assert CONF_MAX_CHARGE_POWER_ENTITY in dd

    def test_confirm_data_description_has_max_charge_manual_power(self):
        strings = _load_strings()
        dd = (
            strings.get("config", {})
            .get("step", {})
            .get("confirm", {})
            .get("data_description", {})
        )
        assert CONF_MAX_CHARGE_MANUAL_POWER_W in dd

    def test_confirm_data_description_values_are_german(self):
        """All data_description values in confirm must be in German."""
        strings = _load_strings()
        dd = (
            strings.get("config", {})
            .get("step", {})
            .get("confirm", {})
            .get("data_description", {})
        )
        for key, val in dd.items():
            assert len(val.strip()) > 5, (
                f"data_description for {key} must be a meaningful German sentence"
            )
            val_lower = val.lower()
            assert any(
                kw in val_lower
                for kw in ["entität", "leistung", "batterie", "netz", "haus",
                           "verbrauch", "ladestand", "kapazität", "vorzeichen",
                           "bedeutet", "kann", "soll", "messwert", "anlage"]
            ), f"confirm data_description for {key} must be in German, got: {val}"


# =========================================================================== #
# TEST 2: confirm data_description mirrors manual_mapping                    #
# =========================================================================== #


class TestConfirmManualMappingDataDescriptionConsistency:
    """data_description in confirm should match manual_mapping (same fields)."""

    def _dd_for_step(self, step_name: str) -> dict:
        strings = _load_strings()
        return (
            strings.get("config", {})
            .get("step", {})
            .get(step_name, {})
            .get("data_description", {})
        )

    def test_confirm_and_manual_mapping_share_all_fields(self):
        """Both steps must define data_description for the same fields."""
        dd_confirm = self._dd_for_step("confirm")
        dd_manual = self._dd_for_step("manual_mapping")

        confirm_keys = set(dd_confirm.keys())
        manual_keys = set(dd_manual.keys())

        # confirm should have at least all the fields that manual_mapping has
        assert manual_keys.issubset(confirm_keys), (
            f"confirm data_description missing fields: {manual_keys - confirm_keys}"
        )

    def test_confirm_and_manual_mapping_house_power_description_match(self):
        """House power explanation must be identical in both steps."""
        dd_confirm = self._dd_for_step("confirm")
        dd_manual = self._dd_for_step("manual_mapping")

        assert dd_confirm[CONF_HOUSE_POWER_ENTITY] == dd_manual[CONF_HOUSE_POWER_ENTITY], (
            "house_power_entity data_description must be identical in confirm and manual_mapping"
        )
