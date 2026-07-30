"""Regression test: field descriptions rendered via data_description in strings.json.

HA 2024.3.3 supports data_description for config flows — it was added in
HA 2024.3 and is proven by the real HA Hue integration.  The data_description
block provides per-field explanations rendered by the HA frontend directly
below each field label.

Requirement 5: Jede sichtbare Zeile braucht einen klaren deutschen Titel UND
eine kurze Erklärung direkt darunter.

This test verifies that:
1. strings.json step data_description contains explanations for all schema fields
2. Config flow still passes description_placeholders (for HA 2024.7+ compatibility)
3. All descriptions are meaningful German text
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock

from custom_components.universal_energy_manager.config_flow import (
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    UemConfigFlow,
)
from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_SOC_ENTITY,
)


def _load_strings() -> dict:
    strings_path = (
        Path(__file__).parents[1]
        / "custom_components"
        / "universal_energy_manager"
        / "strings.json"
    )
    with open(strings_path, encoding="utf-8") as f:
        return json.load(f)


def _make_flow(hass: MagicMock) -> UemConfigFlow:
    flow = UemConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.handler = DOMAIN
    ce = hass.config_entries
    _all: dict[str, list] = {E3DC_RSCP_DOMAIN: [], DOMAIN: []}

    def _async_entries(domain=None, *args, **kwargs):
        if domain is None:
            result = []
            for entries in _all.values():
                result.extend(entries)
            return result
        return _all.get(domain, [])

    ce.async_entries = MagicMock(side_effect=_async_entries)
    ce.async_entry_for_domain_unique_id = MagicMock(return_value=None)
    return flow


def _mock_location(hass: MagicMock):
    loc = MagicMock()
    loc.latitude = 52.5200
    loc.longitude = 13.4050
    hass.config.location = loc


# =========================================================================== #
# TEST 1: strings.json data_description has all field explanations             #
# =========================================================================== #


class TestDataDescriptionFieldExplanations:
    """Every schema field must have a data_description entry in each step."""

    _ALL_FIELDS = frozenset({
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
    })

    def test_confirm_data_description_has_all_fields(self):
        strings = _load_strings()
        dd = (
            strings.get("config", {})
            .get("step", {})
            .get("confirm", {})
            .get("data_description", {})
        )
        missing = self._ALL_FIELDS - set(dd.keys())
        assert not missing, (
            f"confirm/data_description missing: {missing}"
        )

    def test_manual_mapping_data_description_has_all_fields(self):
        strings = _load_strings()
        dd = (
            strings.get("config", {})
            .get("step", {})
            .get("manual_mapping", {})
            .get("data_description", {})
        )
        missing = self._ALL_FIELDS - set(dd.keys())
        assert not missing, (
            f"manual_mapping/data_description missing: {missing}"
        )

    def test_reconfigure_edit_data_description_has_all_fields(self):
        strings = _load_strings()
        dd = (
            strings.get("config", {})
            .get("step", {})
            .get("reconfigure_edit", {})
            .get("data_description", {})
        )
        missing = self._ALL_FIELDS - set(dd.keys())
        assert not missing, (
            f"reconfigure_edit/data_description missing: {missing}"
        )


# =========================================================================== #
# TEST 2: Config flow still passes description_placeholders (HA 2024.7+ compat) #
# =========================================================================== #


class TestConfigFlowDescriptionPlaceholders:
    """Config flow passes description_placeholders for compatibility with
    HA 2024.7+ which may prefer this approach."""

    def test_manual_mapping_passes_description_placeholders(self):
        hass = MagicMock()
        flow = _make_flow(hass)
        _mock_location(hass)

        async def _go():
            r1 = await flow.async_step_no_e3dc_choice({"confirm": "continue"})
            return r1

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )
        assert result["type"] == "form"
        assert result["step_id"] == "manual_mapping"

        placeholders = result.get("description_placeholders")
        assert placeholders is not None, (
            "manual_mapping step must pass description_placeholders"
        )
        assert isinstance(placeholders, dict)
        # Core field placeholders must be present
        for key in ("soc_entity_desc", "house_power_entity_desc", "grid_export_entity_desc"):
            assert key in placeholders, (
                f"description_placeholders must include '{key}'"
            )

    def test_confirm_passes_description_placeholders(self):
        from homeassistant import config_entries

        hass = MagicMock()
        flow = _make_flow(hass)
        _mock_location(hass)

        e3dc_entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=E3DC_RSCP_DOMAIN,
            title="E3DC RSCP",
            data={},
            source="user",
            entry_id="e3dc-001",
            unique_id="S10E-12345",
        )

        all_by_domain = {E3DC_RSCP_DOMAIN: [e3dc_entry], DOMAIN: []}

        def _async_entries(domain=None, *args, **kwargs):
            if domain is None:
                result = []
                for entries in all_by_domain.values():
                    result.extend(entries)
                return result
            return all_by_domain.get(domain, [])

        flow.hass.config_entries.async_entries = MagicMock(
            side_effect=_async_entries
        )

        async def _go():
            r1 = await flow.async_step_user()
            return r1

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )

        assert result["type"] == "form"
        placeholders = result.get("description_placeholders")
        assert placeholders is not None, (
            f"{result['step_id']} step must pass description_placeholders"
        )
        for key in ("soc_entity_desc", "house_power_entity_desc", "grid_export_entity_desc"):
            assert key in placeholders, (
                f"description_placeholders must include '{key}'"
            )

    def test_description_placeholders_are_german(self):
        hass = MagicMock()
        flow = _make_flow(hass)
        _mock_location(hass)

        async def _go():
            r1 = await flow.async_step_no_e3dc_choice({"confirm": "continue"})
            return r1

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )
        placeholders = result["description_placeholders"]

        for key, val in placeholders.items():
            assert val is not None and len(str(val).strip()) > 3, (
                f"description_placeholder '{key}' must have meaningful text"
            )
            val_lower = str(val).lower()
            assert any(
                kw in val_lower
                for kw in [
                    "entität", "leistung", "batterie", "netz", "haus", "verbrauch",
                    "ladestand", "kapazität", "vorzeichen", "bedeutet", "kann",
                    "soll", "messwert", "anlage", "positiv", "negativ",
                    "ein", "der", "die", "das",
                ]
            ), f"description_placeholder '{key}' must be in German, got: {val}"


# =========================================================================== #
# TEST 3: House power description explains negative values (Req 3)            #
# =========================================================================== #


class TestHousePowerDescription:
    def test_house_power_placeholder_explains_negative_values(self):
        hass = MagicMock()
        flow = _make_flow(hass)
        _mock_location(hass)

        async def _go():
            r1 = await flow.async_step_no_e3dc_choice({"confirm": "continue"})
            return r1

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )
        placeholders = result["description_placeholders"]
        house_desc = str(placeholders.get("house_power_entity_desc", ""))

        assert (
            "negativ" in house_desc.lower()
            or "balkonkraftwerk" in house_desc.lower()
            or "produziert" in house_desc.lower()
        ), (
            f"house_power_entity description_placeholder must explain negative "
            f"values, got: {house_desc}"
        )


# =========================================================================== #
# TEST 4: Reconfigure edit passes description_placeholders                    #
# =========================================================================== #


class TestReconfigureEditPlaceholders:
    def test_reconfigure_edit_passes_description_placeholders(self):
        from custom_components.universal_energy_manager.const import (
            CONF_BATTERY_CAPACITY_ENTITY,
            CONF_E3DC_CONFIG_ENTRY_ID,
            CONF_E3DC_SOURCE_UNIQUE_ID,
            CONF_MANUAL_ENTITIES,
            CONF_MAX_CHARGE_POWER_ENTITY,
        )

        hass = MagicMock()
        flow = _make_flow(hass)
        _mock_location(hass)

        uem_entry = MagicMock()
        uem_entry.entry_id = "uem-test"
        uem_entry.domain = DOMAIN
        uem_entry.version = 1
        uem_entry.minor_version = 1
        uem_entry.title = "UEM"
        uem_entry.data = {
            CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
            CONF_E3DC_SOURCE_UNIQUE_ID: "HW-999",
            CONF_MANUAL_ENTITIES: False,
            CONF_SOC_ENTITY: "sensor.e3dc_soc",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
            CONF_BATTERY_CAPACITY_ENTITY: "",
            CONF_MAX_CHARGE_POWER_ENTITY: "",
        }
        uem_entry.source = "user"
        uem_entry.unique_id = "uem:manual:test"
        uem_entry.state = MagicMock()

        all_by_domain = {DOMAIN: [uem_entry], E3DC_RSCP_DOMAIN: []}

        def _async_entries(domain=None, *args, **kwargs):
            if domain is None:
                result = []
                for entries in all_by_domain.values():
                    result.extend(entries)
                return result
            return all_by_domain.get(domain, [])

        flow.hass.config_entries.async_entries = MagicMock(
            side_effect=_async_entries
        )
        flow.context = {"entry_id": uem_entry.entry_id}

        async def _go():
            r = await flow.async_step_reconfigure({"edit_manual": "True"})
            return r

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )
        assert result["type"] == "form"
        assert result["step_id"] == "reconfigure_edit"

        placeholders = result.get("description_placeholders")
        assert placeholders is not None, "reconfigure_edit must pass description_placeholders"
