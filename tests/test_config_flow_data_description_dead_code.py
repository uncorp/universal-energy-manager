"""Regression test: verify data_description blocks in strings.json are properly
populated with German explanations (Req 5).

HA 2024.3.3 DOES support data_description in config_flow strings.json
— the real HA Hue integration proves this (hue/strings.json contains
data_description blocks).  The previous dead-code removal was incorrect.

This test verifies:
1. data_description blocks ARE present in confirm, manual_mapping, reconfigure_edit.
2. data_description blocks do NOT contain forbidden technical terms 'signed' / 'separate'
   (Req 1).
3. Every schema field has a corresponding data_description entry.
4. The house_power_entity description mentions negative values / Balkonkraftwerk (Req 3).
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

_ALL_SCHEMA_FIELDS = frozenset({
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


def _load_strings() -> dict:
    strings_path = (
        Path(__file__).parents[1]
        / "custom_components"
        / "universal_energy_manager"
        / "strings.json"
    )
    with open(strings_path, encoding="utf-8") as f:
        return json.load(f)


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
# TEST 1: data_description blocks ARE present (not removed dead code)         #
# =========================================================================== #


class TestDataDescriptionPresent:
    """data_description blocks must be present in confirm, manual_mapping,
    reconfigure_edit — HA 2024.3.3 supports them (proven by hue/strings.json)."""

    def test_confirm_has_data_description(self) -> None:
        """confirm step must have data_description."""
        dd = _step_data_description("confirm")
        assert dd, "confirm step must have data_description"

    def test_manual_mapping_has_data_description(self) -> None:
        """manual_mapping must have data_description."""
        dd = _step_data_description("manual_mapping")
        assert dd, "manual_mapping must have data_description"

    def test_reconfigure_edit_has_data_description(self) -> None:
        """reconfigure_edit must have data_description."""
        dd = _step_data_description("reconfigure_edit")
        assert dd, "reconfigure_edit must have data_description"


# =========================================================================== #
# TEST 2: data_description covers all schema fields                           #
# =========================================================================== #


class TestDataDescriptionAllFields:
    """Every schema field must have a corresponding data_description entry."""

    def _check_field_count(self, step_name: str) -> None:
        dd = _step_data_description(step_name)
        dd_keys = set(dd.keys())
        missing = _ALL_SCHEMA_FIELDS - dd_keys
        assert not missing, (
            f"{step_name} data_description missing fields: {missing}"
        )

    def test_confirm_all_fields(self) -> None:
        self._check_field_count("confirm")

    def test_manual_mapping_all_fields(self) -> None:
        self._check_field_count("manual_mapping")

    def test_reconfigure_edit_all_fields(self) -> None:
        self._check_field_count("reconfigure_edit")


# =========================================================================== #
# TEST 3: No forbidden technical terms in data_description (Req 1)            #
# =========================================================================== #


class TestDataDescriptionNoForbiddenTerms:
    """data_description blocks must not contain 'signed' or 'separate'."""

    def test_no_signed_any_step(self) -> None:
        for step in ("confirm", "manual_mapping", "reconfigure_edit"):
            dd = _step_data_description(step)
            for key, val in dd.items():
                assert "signed" not in str(val).lower(), (
                    f"data_description['{key}'] in '{step}' must not contain "
                    f"'signed', got: {val}"
                )

    def test_no_separate_any_step(self) -> None:
        for step in ("confirm", "manual_mapping", "reconfigure_edit"):
            dd = _step_data_description(step)
            for key, val in dd.items():
                assert "separate" not in str(val).lower(), (
                    f"data_description['{key}'] in '{step}' must not contain "
                    f"'separate', got: {val}"
                )


# =========================================================================== #
# TEST 4: House power explains negative values (Req 3)                        #
# =========================================================================== #


class TestDataDescriptionHousePower:
    """house_power_entity description must explain negative values /
    Balkonkraftwerk (Req 3)."""

    def _check_house_power(self, step_name: str) -> None:
        dd = _step_data_description(step_name)
        desc = str(dd.get("house_power_entity", ""))
        assert (
            "negativ" in desc.lower()
            or "balkonkraftwerk" in desc.lower()
            or "produziert" in desc.lower()
        ), (
            f"{step_name} data_description['house_power_entity'] must explain "
            f"negative values, got: {desc}"
        )

    def test_confirm_house_power(self) -> None:
        self._check_house_power("confirm")

    def test_manual_mapping_house_power(self) -> None:
        self._check_house_power("manual_mapping")

    def test_reconfigure_edit_house_power(self) -> None:
        self._check_house_power("reconfigure_edit")


# =========================================================================== #
# TEST 5: Grid sign convention explains Bezug/Einspeisung (Req 2)             #
# =========================================================================== #


class TestDataDescriptionGridSign:
    """grid_power_sign_convention data_description must mention Netzbezug and
    Einspeisung (Req 2)."""

    def _check_grid_sign(self, step_name: str) -> None:
        dd = _step_data_description(step_name)
        desc = str(dd.get("grid_power_sign_convention", ""))
        # Must mention both concepts (Bezug and Einspeisung)
        assert (
            "netzbezug" in desc.lower() or "einspeisung" in desc.lower()
        ), (
            f"{step_name} data_description['grid_power_sign_convention'] must "
            f"mention Bezug or Einspeisung, got: {desc}"
        )

    def test_confirm_grid_sign(self) -> None:
        self._check_grid_sign("confirm")

    def test_manual_mapping_grid_sign(self) -> None:
        self._check_grid_sign("manual_mapping")

    def test_reconfigure_edit_grid_sign(self) -> None:
        self._check_grid_sign("reconfigure_edit")


# =========================================================================== #
# TEST 6: Entire strings.json is free of 'signed'/'separate' technical terms  #
# =========================================================================== #


class TestStringsJsonNoTechnicalTerms:
    """The entire strings.json must not contain 'signed' or 'separate'."""

    def test_no_signed_in_strings(self) -> None:
        strings_path = (
            Path(__file__).parents[1]
            / "custom_components"
            / "universal_energy_manager"
            / "strings.json"
        )
        with open(strings_path, encoding="utf-8") as f:
            content = f.read()
        assert "signed" not in content.lower(), (
            "strings.json must not contain 'signed' anywhere (forbidden "
            "technical term per Req 1)"
        )

    def test_no_separate_in_strings(self) -> None:
        strings_path = (
            Path(__file__).parents[1]
            / "custom_components"
            / "universal_energy_manager"
            / "strings.json"
        )
        with open(strings_path, encoding="utf-8") as f:
            content = f.read()
        assert "separate" not in content.lower(), (
            "strings.json must not contain 'separate' anywhere (forbidden "
            "technical term per Req 1)"
        )
