"""Regression test: confirm step in strings.json provides field descriptions.

Requirement 5: Jede sichtbare Zeile braucht einen klaren deutschen Titel
UND eine kurze Erklärung direkt darunter.

HA 2024.3.3 (pinned version) does NOT support ``data_description`` in
config-flow strings.json — it was added in HA 2024.7+.  The actual
mechanism is:
- The step's ``description`` text contains ``{*_desc}`` placeholder tokens.
- The config flow passes ``description_placeholders`` with the real German
  text for each placeholder to ``async_show_form()``.
- The HA frontend substitutes placeholders at render time.

This test verifies that:
1. The confirm step has a ``data`` dict with German field titles.
2. The confirm step's ``description`` contains all ``{*_desc}`` placeholder tokens.
3. All field descriptions are present (mirroring manual_mapping).
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
# TEST 2: confirm step description contains placeholder tokens               #
# =========================================================================== #


class TestConfirmStepDescriptionPlaceholders:
    """The confirm step's description must contain {*_desc} tokens for
    field explanations.  These are substituted by HA at render time
    via description_placeholders passed by the config flow."""

    def _description_tokens(self, step_name: str) -> list[str]:
        strings = _load_strings()
        desc = strings.get("config", {}).get("step", {}).get(step_name, {}).get("description", "")
        # Find all {token} patterns
        import re
        return re.findall(r"\{(\w+)_desc\}", desc)

    def test_confirm_has_all_placeholder_tokens(self):
        """confirm description must contain all 10 field-description tokens."""
        tokens = self._description_tokens("confirm")
        expected_tokens = [
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
        ]
        for t in expected_tokens:
            assert t in tokens, (
                f"confirm description must contain {{{t}_desc}} placeholder, "
                f"found: {tokens}"
            )

    def test_confirm_and_manual_mapping_share_all_placeholder_tokens(self):
        """Both steps must define placeholders for the same fields."""
        confirm_tokens = set(self._description_tokens("confirm"))
        manual_tokens = set(self._description_tokens("manual_mapping"))
        expected = {
            "soc_entity", "pv_power_entity", "house_power_entity",
            "battery_charge_entity", "battery_capacity_entity",
            "battery_manual_capacity_kwh", "max_charge_power_entity",
            "max_charge_manual_power_w", "grid_export_entity",
            "grid_power_sign_convention",
        }
        assert confirm_tokens == expected, (
            f"confirm placeholder tokens mismatch: missing={expected - confirm_tokens}"
        )
        assert manual_tokens == expected, (
            f"manual_mapping placeholder tokens mismatch: missing={expected - manual_tokens}"
        )


# =========================================================================== #
# TEST 3: data_description is dead code (removed)                             #
# =========================================================================== #


class TestConfirmNoDeadDataDescription:
    """HA 2024.3.3 does not support data_description — it must be removed."""

    def test_confirm_has_no_data_description_key(self):
        """confirm step must not have data_description (dead code)."""
        strings = _load_strings()
        confirm = strings.get("config", {}).get("step", {}).get("confirm", {})
        assert "data_description" not in confirm, (
            "confirm step must not have data_description (HA 2024.3.3 unsupported)"
        )

    def test_manual_mapping_has_no_data_description_key(self):
        """manual_mapping step must not have data_description (dead code)."""
        strings = _load_strings()
        mapping = strings.get("config", {}).get("step", {}).get("manual_mapping", {})
        assert "data_description" not in mapping, (
            "manual_mapping must not have data_description (HA 2024.3.3 unsupported)"
        )
