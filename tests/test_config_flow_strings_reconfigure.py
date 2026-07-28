"""Regression test: reconfigure/reconfigure_edit steps use HA data_description.

Requirements:
- reconfigure and reconfigure_edit steps in strings.json have data_description entries
- The data_description for reconfigure_edit mirrors the manual_mapping one
- No references to removed fields (battery_power_mode, grid_power_mode, etc.)
- Each field in data_description has a German explanation
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
# TEST 1: reconfigure step has data_description                              #
# =========================================================================== #


class TestReconfigureStepDataDescription:
    """The reconfigure step must have a data_description section in strings.json."""

    def test_reconfigure_step_has_data_description_key(self):
        """strings.json reconfigure step must have a data_description key."""
        strings = _load_strings()
        reconfigure = (
            strings.get("config", {})
            .get("step", {})
            .get("reconfigure", {})
        )
        assert "data_description" in reconfigure, (
            "reconfigure step must have a data_description section"
        )

    def test_reconfigure_data_description_exists(self):
        """data_description for reconfigure should exist (may be empty since
        the reconfigure form only has checkboxes, not entity fields)."""
        strings = _load_strings()
        dd = (
            strings.get("config", {})
            .get("step", {})
            .get("reconfigure", {})
            .get("data_description", {})
        )
        # The reconfigure form only shows rescan/edit checkboxes, no entity fields
        # An empty dict is acceptable here. The key just needs to exist.
        assert isinstance(dd, dict)


# =========================================================================== #
# TEST 2: reconfigure_edit step has data_description                         #
# =========================================================================== #


class TestReconfigureEditStepDataDescription:
    """The reconfigure_edit step must have a data_description section."""

    def test_reconfigure_edit_has_data_description_key(self):
        """strings.json reconfigure_edit step must have a data_description key."""
        strings = _load_strings()
        reconfigure_edit = (
            strings.get("config", {})
            .get("step", {})
            .get("reconfigure_edit", {})
        )
        assert "data_description" in reconfigure_edit, (
            "reconfigure_edit step must have a data_description section"
        )

    def test_reconfigure_edit_data_description_has_all_fields(self):
        """data_description for reconfigure_edit should have descriptions for all
        schema fields — matching the manual_mapping set."""
        strings = _load_strings()
        dd = (
            strings.get("config", {})
            .get("step", {})
            .get("reconfigure_edit", {})
            .get("data_description", {})
        )
        # Must have at least the core fields
        for field in (
            CONF_SOC_ENTITY,
            CONF_PV_POWER_ENTITY,
            CONF_HOUSE_POWER_ENTITY,
            CONF_BATTERY_CHARGE_ENTITY,
            CONF_GRID_EXPORT_ENTITY,
            CONF_GRID_POWER_SIGN_CONVENTION,
        ):
            assert field in dd, (
                f"reconfigure_edit data_description must have entry for {field}"
            )

    def test_reconfigure_edit_data_description_is_german(self):
        """All data_description values in reconfigure_edit must be in German."""
        strings = _load_strings()
        dd = (
            strings.get("config", {})
            .get("step", {})
            .get("reconfigure_edit", {})
            .get("data_description", {})
        )
        for key, val in dd.items():
            # Must not be empty
            assert len(val.strip()) > 5, (
                f"data_description for {key} must be a meaningful German sentence"
            )
            # Should not contain English-only technical terms
            val_lower = val.lower()
            # Should not be purely English
            assert any(
                kw in val_lower
                for kw in ["entität", "leistung", "batterie", "netz", "haus", "verbrauch",
                           "ladestand", "kapazität", "vorzeichen", "bedeutet", "soll", "kann"]
            ), f"data_description for {key} must be in German, got: {val}"


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
        """Starting reconfigure should show the reconfigure step with form type."""
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
        """Reconfigure → edit_manual should show reconfigure_edit form with
        simplified schema (no battery_power_mode, grid_power_mode, etc.)."""
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
            # Trigger reconfigure → edit_manual
            result = await flow.async_step_reconfigure(
                {"rescan_e3dc": False, "edit_manual": True}
            )
            return result

        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            _go()
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure_edit"

        # Verify simplified schema — no removed fields
        schema_dict = result.get("data_schema", {})
        # Schema is a voluptuous.Schema wrapping a dict; extract keys
        if hasattr(schema_dict, "schema"):
            schema_keys = set(schema_dict.schema.keys())
        elif hasattr(schema_dict, "keys"):
            schema_keys = set(schema_dict.keys())
        else:
            schema_keys = set()

        # These must NOT be in the schema
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

        # These MUST be in the schema
        assert CONF_SOC_ENTITY in schema_keys
        assert CONF_PV_POWER_ENTITY in schema_keys
        assert CONF_HOUSE_POWER_ENTITY in schema_keys
        assert CONF_BATTERY_CHARGE_ENTITY in schema_keys
        assert CONF_GRID_EXPORT_ENTITY in schema_keys
        assert CONF_GRID_POWER_SIGN_CONVENTION in schema_keys

    def test_reconfigure_edit_save_updates_entry_data(self):
        """Saving reconfigure_edit should update entry data and return abort."""
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
        # The stub returns ABORT, and the entry's data should be updated
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
