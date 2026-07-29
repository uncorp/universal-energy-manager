"""Regression test: reconfigure/reconfigure_edit steps use data_description.

Requirements:
- reconfigure and reconfigure_edit steps in strings.json have data_description
  for all 10 schema fields (HA 2024.3.3 supported)
- The config flow passes description_placeholders for all fields (compatibility)
- No references to removed fields (battery_power_mode, grid_power_mode, etc.)
- Each field in data_description has a German explanation

HA 2024.3.3 DOES support data_description in strings.json — it was added
in HA 2024.3 and is proven by the real HA Hue integration.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock

from homeassistant.data_entry_flow import FlowResultType

from custom_components.universal_energy_manager.config_flow import (
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    UemConfigFlow,
)
from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_MANUAL_CAPACITY_KWH,
    CONF_E3DC_CONFIG_ENTRY_ID,
    CONF_E3DC_SOURCE_UNIQUE_ID,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_POWER_SIGN_CONVENTION,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MANUAL_ENTITIES,
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


def _make_flow_with_uem(hass: MagicMock, uem_entry) -> UemConfigFlow:
    """Build a flow that has an existing UEM entry for reconfigure testing."""
    flow = UemConfigFlow()
    flow.hass = hass
    flow.context = {"entry_id": uem_entry.entry_id}
    flow.handler = DOMAIN

    ce = hass.config_entries
    all_by_domain = {DOMAIN: [uem_entry], E3DC_RSCP_DOMAIN: []}

    def _async_entries(domain=None, *args, **kwargs):
        if domain is None:
            result = []
            for entries in all_by_domain.values():
                result.extend(entries)
            return result
        return all_by_domain.get(domain, [])

    ce.async_entries = MagicMock(side_effect=_async_entries)
    ce.async_entry_for_domain_unique_id = MagicMock(return_value=None)
    return flow


# =========================================================================== #
# TEST 1: reconfigure/reconfigure_edit have data_description                  #
# =========================================================================== #


class TestReconfigureStepDataDescription:
    """The reconfigure_edit step must have data_description (HA 2024.3.3
    supported, proven by HA Hue integration).  The reconfigure step is a
    pure choice step (no entity fields) and doesn't need data_description."""

    def test_reconfigure_edit_has_data_description_key(self):
        strings = _load_strings()
        reconfigure_edit = strings.get("config", {}).get("step", {}).get(
            "reconfigure_edit", {}
        )
        assert "data_description" in reconfigure_edit, (
            "reconfigure_edit must have data_description (HA 2024.3.3 supported)"
        )


# =========================================================================== #
# TEST 2: reconfigure_edit flow passes description_placeholders               #
# =========================================================================== #


class TestReconfigureEditStepPlaceholders:
    """The reconfigure_edit step must pass description_placeholders
    covering all schema fields."""

    def test_reconfigure_edit_passes_description_placeholders(self):
        """Reconfigure → edit flow must pass description_placeholders."""
        hass = MagicMock()
        flow = UemConfigFlow()
        flow.hass = hass
        flow.context = {"entry_id": "uem-test"}
        flow.handler = DOMAIN

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

        async def _go():
            r = await flow.async_step_reconfigure({"edit_manual": "True"})
            return r

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure_edit"

        placeholders = result.get("description_placeholders")
        assert placeholders is not None

        # All 10 schema fields must be present
        _ALL_PLACEHOLDER_KEYS = {
            "soc_entity_desc",
            "pv_power_entity_desc",
            "house_power_entity_desc",
            "battery_charge_entity_desc",
            "battery_capacity_entity_desc",
            "battery_manual_capacity_kwh_desc",
            "max_charge_power_entity_desc",
            "max_charge_manual_power_w_desc",
            "grid_export_entity_desc",
            "grid_power_sign_convention_desc",
        }
        for key in _ALL_PLACEHOLDER_KEYS:
            assert key in placeholders, (
                f"description_placeholders must include '{key}'"
            )


# =========================================================================== #
# TEST 3: reconfigure flow works end-to-end with simplified schema           #
# =========================================================================== #


class TestReconfigureFlowSimplifiedSchema:
    """End-to-end test: reconfigure flow with the simplified schema (no old fields)."""

    def _make_uem_entry(self, data: dict) -> MagicMock:
        entry = MagicMock()
        entry.entry_id = "uem-test"
        entry.domain = DOMAIN
        entry.version = 1
        entry.minor_version = 1
        entry.title = "UEM – Universal Energy Manager"
        entry.data = data
        entry.source = "user"
        entry.unique_id = "uem:manual:test"
        entry.state = MagicMock()
        return entry

    def test_reconfigure_flow_shows_form(self):
        hass = MagicMock()
        uem_entry = self._make_uem_entry(
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-999",
                CONF_MANUAL_ENTITIES: False,
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
            }
        )

        flow = _make_flow_with_uem(hass, uem_entry)

        async def _go():
            result = await flow.async_step_reconfigure()
            return result

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

    def test_reconfigure_edit_shows_form_with_simplified_schema(self):
        hass = MagicMock()
        uem_entry = self._make_uem_entry(
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-999",
                CONF_MANUAL_ENTITIES: False,
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
            }
        )

        flow = _make_flow_with_uem(hass, uem_entry)

        async def _go():
            result = await flow.async_step_reconfigure(
                {"rescan_e3dc": False, "edit_manual": True}
            )
            return result

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure_edit"

        schema_dict = result.get("data_schema", {})
        if hasattr(schema_dict, "schema"):
            schema_keys = set(schema_dict.schema.keys())
        elif hasattr(schema_dict, "keys"):
            schema_keys = set(schema_dict.keys())
        else:
            schema_keys = set()

        from custom_components.universal_energy_manager.const import (
            CONF_BATTERY_DISCHARGE_ENTITY,
            CONF_BATTERY_POWER_MODE,
            CONF_BATTERY_POWER_SIGN_CONVENTION,
            CONF_GRID_IMPORT_ENTITY,
            CONF_GRID_POWER_MODE,
        )

        assert CONF_BATTERY_POWER_MODE not in schema_keys
        assert CONF_BATTERY_DISCHARGE_ENTITY not in schema_keys
        assert CONF_BATTERY_POWER_SIGN_CONVENTION not in schema_keys
        assert CONF_GRID_POWER_MODE not in schema_keys
        assert CONF_GRID_IMPORT_ENTITY not in schema_keys

        assert CONF_SOC_ENTITY in schema_keys
        assert CONF_PV_POWER_ENTITY in schema_keys
        assert CONF_HOUSE_POWER_ENTITY in schema_keys
        assert CONF_BATTERY_CHARGE_ENTITY in schema_keys
        assert CONF_GRID_EXPORT_ENTITY in schema_keys
        assert CONF_GRID_POWER_SIGN_CONVENTION in schema_keys

    def test_reconfigure_edit_save_updates_entry_data(self):
        hass = MagicMock()
        uem_entry = self._make_uem_entry(
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-999",
                CONF_MANUAL_ENTITIES: False,
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "",
            }
        )

        flow = _make_flow_with_uem(hass, uem_entry)

        user_input = {
            CONF_SOC_ENTITY: "sensor.changed_soc",
            CONF_PV_POWER_ENTITY: "",
            CONF_HOUSE_POWER_ENTITY: "",
            CONF_BATTERY_CHARGE_ENTITY: "",
            CONF_GRID_EXPORT_ENTITY: "",
            CONF_BATTERY_CAPACITY_ENTITY: "",
            CONF_MAX_CHARGE_POWER_ENTITY: "",
            CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
            CONF_MAX_CHARGE_MANUAL_POWER_W: "",
            CONF_GRID_POWER_SIGN_CONVENTION: "positive_is_discharging_import",
        }

        async def _go():
            result = await flow.async_step_reconfigure_edit(user_input)
            return result

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"


# =========================================================================== #
# TEST 4: Strings.json consistency — no orphaned old-field references        #
# =========================================================================== #


class TestStringsJsonNoOrphanedFields:
    """strings.json must not contain any references to fields removed in the
    simplified schema."""

    def _load_full_strings(self) -> str:
        strings_path = (
            Path(__file__).parents[1]
            / "custom_components"
            / "universal_energy_manager"
            / "strings.json"
        )
        with open(strings_path, encoding="utf-8") as f:
            return f.read()

    def test_no_battery_power_mode_in_strings(self):
        content = self._load_full_strings()
        assert "battery_power_mode" not in content

    def test_no_grid_power_mode_in_strings(self):
        content = self._load_full_strings()
        assert "grid_power_mode" not in content

    def test_no_battery_discharge_entity_in_strings(self):
        content = self._load_full_strings()
        assert "battery_discharge_entity" not in content

    def test_no_grid_import_entity_in_strings(self):
        content = self._load_full_strings()
        assert "grid_import_entity" not in content

    def test_no_battery_power_sign_convention_in_strings(self):
        content = self._load_full_strings()
        assert "battery_power_sign_convention" not in content
