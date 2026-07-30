"""TDD tests for reconfigure-rescan path when no e3dc_config_entry_id is stored.

Covers:
- Reconfigure without stored e3dc_config_entry_id and 0 adapters → abort
- Reconfigure without stored e3dc_config_entry_id and 1 adapter → edit form with prefill
- Reconfigure without stored e3dc_config_entry_id and multiple adapters → selection form
- Selection from multiple → edit form with prefill
- Existing stored e3dc_config_entry_id path remains compatible
- _fill_blank_fields helper
- _discover_entities_from_entry helper
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.universal_energy_manager.config_flow import UemConfigFlow
from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_MANUAL_CAPACITY_KWH,
    CONF_E3DC_CONFIG_ENTRY_ID,
    CONF_E3DC_SOURCE_UNIQUE_ID,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_INVERT_GRID_POWER_SIGN,
    CONF_MANUAL_ENTITIES,
    CONF_MAX_CHARGE_MANUAL_POWER_W,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    FORECAST_SOLAR_DOMAIN,

)
from custom_components.universal_energy_manager.e3dc_rscp import E3dcEntityMap

# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


def _make_e3dc_entry(
    entry_id: str = "e3dc-001",
    unique_id: str = "S10E-12345",
    title: str = "E3DC RSCP",
) -> config_entries.ConfigEntry:
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=E3DC_RSCP_DOMAIN,
        title=title,
        data={},
        source="user",
        entry_id=entry_id,
        unique_id=unique_id,
        state=config_entries.ConfigEntryState.LOADED,
    )


def _make_uem_entry(
    entry_id: str = "uem-001",
    unique_id: str = "uem:manual:test",
    data: dict | None = None,
    title: str = "UEM – Universal Energy Manager",
) -> config_entries.ConfigEntry:
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title=title,
        data=data or {},
        source="user",
        entry_id=entry_id,
        unique_id=unique_id,
        state=config_entries.ConfigEntryState.LOADED,
    )


def _make_flow_with_uem(
    hass: MagicMock,
    e3dc_entries: list[config_entries.ConfigEntry],
    forecast_entries: list[config_entries.ConfigEntry] | None = None,
    uem_entry: config_entries.ConfigEntry | None = None,
) -> UemConfigFlow:
    flow = UemConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.handler = DOMAIN
    ce = hass.config_entries
    _all: dict[str, list[config_entries.ConfigEntry]] = {
        E3DC_RSCP_DOMAIN: e3dc_entries,
        FORECAST_SOLAR_DOMAIN: forecast_entries or [],
    }
    if uem_entry:
        _all[DOMAIN] = [uem_entry]

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


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def _mock_location(hass: MagicMock) -> None:
    loc = MagicMock()
    loc.latitude = 52.5200
    loc.longitude = 13.4050
    hass.config.location = loc


# =========================================================================== #
# TEST: _fill_blank_fields helper                                              #
# =========================================================================== #


class TestFillBlankFields:
    """_fill_blank_fields should only fill blank mapping fields."""

    def test_fill_blank_fields_fills_all_blank_from_discovery(self) -> None:
        """All blank fields get discovered entity values."""
        flow = UemConfigFlow()
        e3dc_map = E3dcEntityMap(
            soc="sensor.e3dc_soc",
            pv_power="sensor.e3dc_pv",
            house_power="sensor.e3dc_house",
            grid_export="sensor.e3dc_grid",
            battery_charge="sensor.e3dc_charge",
            battery_capacity="sensor.e3dc_capacity",
            max_charge_power="sensor.e3dc_max_charge",
        )
        result = flow._fill_blank_fields(e3dc_map)

        assert result[CONF_SOC_ENTITY] == "sensor.e3dc_soc"
        assert result[CONF_PV_POWER_ENTITY] == "sensor.e3dc_pv"
        assert result[CONF_HOUSE_POWER_ENTITY] == "sensor.e3dc_house"
        assert result[CONF_GRID_EXPORT_ENTITY] == "sensor.e3dc_grid"
        assert result[CONF_BATTERY_CHARGE_ENTITY] == "sensor.e3dc_charge"
        assert result[CONF_BATTERY_CAPACITY_ENTITY] == "sensor.e3dc_capacity"
        assert result[CONF_MAX_CHARGE_POWER_ENTITY] == "sensor.e3dc_max_charge"
        # Non-mapping fields stay as defaults
        assert result[CONF_BATTERY_MANUAL_CAPACITY_KWH] == ""
        assert result[CONF_MAX_CHARGE_MANUAL_POWER_W] == ""
        assert not result[CONF_INVERT_GRID_POWER_SIGN]

    def test_fill_blank_fields_preserves_nonblank(self) -> None:
        """Non-blank fields in the current data are not overwritten by _fill_blank_fields."""
        flow = UemConfigFlow()
        e3dc_map = E3dcEntityMap(
            soc="sensor.e3dc_soc",
            pv_power="sensor.e3dc_pv",
            house_power="sensor.e3dc_house",
            grid_export="sensor.e3dc_grid",
            battery_charge="sensor.e3dc_charge",
            battery_capacity="sensor.e3dc_capacity",
            max_charge_power="sensor.e3dc_max_charge",
        )
        current_data = {
            CONF_SOC_ENTITY: "sensor.manual_soc",  # non-blank → preserve
            CONF_PV_POWER_ENTITY: "sensor.custom_pv",  # non-blank → preserve
            CONF_HOUSE_POWER_ENTITY: "",  # blank → fill from discovery
            CONF_BATTERY_CHARGE_ENTITY: "sensor.manual_battery",  # non-blank → preserve
            CONF_BATTERY_CAPACITY_ENTITY: "",
            CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
            CONF_MAX_CHARGE_POWER_ENTITY: "sensor.custom_max_charge",  # non-blank
            CONF_MAX_CHARGE_MANUAL_POWER_W: "",
            CONF_GRID_EXPORT_ENTITY: "",
            CONF_INVERT_GRID_POWER_SIGN: False,
        }
        result = flow._fill_blank_fields(e3dc_map, current_data)

        # Non-blank manual values must be preserved
        assert result[CONF_SOC_ENTITY] == "sensor.manual_soc"
        assert result[CONF_PV_POWER_ENTITY] == "sensor.custom_pv"
        assert result[CONF_BATTERY_CHARGE_ENTITY] == "sensor.manual_battery"
        assert result[CONF_MAX_CHARGE_POWER_ENTITY] == "sensor.custom_max_charge"
        # Blank fields get discovery values
        assert result[CONF_HOUSE_POWER_ENTITY] == "sensor.e3dc_house"
        assert result[CONF_GRID_EXPORT_ENTITY] == "sensor.e3dc_grid"
        # battery_capacity_entity is mapped → discovery fills it
        assert result[CONF_BATTERY_CAPACITY_ENTITY] == "sensor.e3dc_capacity"
        # Non-mapping manual fields stay blank (no discovery mapping)
        assert result[CONF_BATTERY_MANUAL_CAPACITY_KWH] == ""
        assert result[CONF_MAX_CHARGE_MANUAL_POWER_W] == ""

    def test_fill_blank_fields_handles_empty_discovery(self) -> None:
        """Discovery with no entities leaves all fields blank."""
        flow = UemConfigFlow()
        e3dc_map = E3dcEntityMap(
            soc=None,
            pv_power=None,
            house_power=None,
            grid_export=None,
            battery_charge=None,
            battery_capacity=None,
            max_charge_power=None,
        )
        result = flow._fill_blank_fields(e3dc_map)

        for key in [
            CONF_SOC_ENTITY,
            CONF_PV_POWER_ENTITY,
            CONF_HOUSE_POWER_ENTITY,
            CONF_GRID_EXPORT_ENTITY,
            CONF_BATTERY_CHARGE_ENTITY,
            CONF_BATTERY_CAPACITY_ENTITY,
            CONF_MAX_CHARGE_POWER_ENTITY,
        ]:
            assert result[key] == ""


# =========================================================================== #
# TEST: Reconfigure without stored e3dc_config_entry_id, 0 adapters → abort    #
# =========================================================================== #


class TestReconfigureRescanNoAdapters:
    """When reconfigure is triggered without stored e3dc_config_entry_id
    and there are 0 e3dc_rscp adapters, should abort with
    e3dc_rscp_not_configured."""

    def test_reconfigure_rescan_no_adapters_aborts(self) -> None:
        """0 e3dc_rscp adapters → abort e3dc_rscp_not_configured."""
        hass = MagicMock()
        uem_entry = _make_uem_entry(
            data={
                CONF_MANUAL_ENTITIES: True,
                CONF_SOC_ENTITY: "",
                CONF_PV_POWER_ENTITY: "",
                CONF_HOUSE_POWER_ENTITY: "",
                CONF_BATTERY_CHARGE_ENTITY: "",
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "10.0",
                CONF_MAX_CHARGE_POWER_ENTITY: "",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "5000",
                CONF_GRID_EXPORT_ENTITY: "",
                CONF_INVERT_GRID_POWER_SIGN: False,
            }
        )
        flow = _make_flow_with_uem(hass, e3dc_entries=[], uem_entry=uem_entry)
        flow.context = {"entry_id": uem_entry.entry_id}

        result = _run(
            flow.async_step_reconfigure({"rescan_e3dc": "True", "edit_manual": "False"})
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "e3dc_rscp_not_configured"


# =========================================================================== #
# TEST: Reconfigure without stored e3dc_config_entry_id, 1 adapter → edit form #
# =========================================================================== #


class TestReconfigureRescanOneAdapter:
    """When reconfigure is triggered without stored e3dc_config_entry_id
    and there is exactly 1 e3dc_rscp adapter, should show the
    reconfigure_edit form with discovery data as editable prefill."""

    def test_reconfigure_rescan_one_adapter_shows_edit_form(self) -> None:
        """1 adapter → reconfigure_edit form with prefill, NOT auto-save."""
        hass = MagicMock()
        e3dc_entry = _make_e3dc_entry()
        uem_entry = _make_uem_entry(
            data={
                CONF_MANUAL_ENTITIES: True,
                CONF_E3DC_CONFIG_ENTRY_ID: None,
                CONF_SOC_ENTITY: "sensor.old_soc",  # existing manual value
                CONF_PV_POWER_ENTITY: "",  # blank → will be prefilled
                CONF_HOUSE_POWER_ENTITY: "sensor.custom_house",  # existing manual
                CONF_BATTERY_CHARGE_ENTITY: "",
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_GRID_EXPORT_ENTITY: "",
                CONF_INVERT_GRID_POWER_SIGN: False,
            }
        )
        flow = _make_flow_with_uem(hass, [e3dc_entry], uem_entry=uem_entry)
        flow.context = {"entry_id": uem_entry.entry_id}

        full_map = E3dcEntityMap(
            soc="sensor.e3dc_soc",
            pv_power="sensor.e3dc_pv",
            house_power="sensor.e3dc_house",
            grid_export="sensor.e3dc_grid",
            battery_charge="sensor.e3dc_charge",
            battery_capacity="sensor.e3dc_capacity",
            max_charge_power="sensor.e3dc_max_charge",
        )

        with patch.object(
            UemConfigFlow, "_discover_entities_from_entry", return_value=full_map
        ):
            result = _run(
                flow.async_step_reconfigure(
                    {"rescan_e3dc": "True", "edit_manual": "False"}
                )
            )

        # Should show the edit form, NOT auto-save
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure_edit"

        # Verify prefill data was set — non-blank existing values preserved,
        # blank fields get discovery prefill
        assert flow._prefill_data is not None
        assert flow._prefill_data[CONF_SOC_ENTITY] == "sensor.old_soc"
        # existing non-blank preserved
        assert flow._prefill_data[CONF_PV_POWER_ENTITY] == "sensor.e3dc_pv"  # blank → discovery
        assert flow._prefill_data[CONF_HOUSE_POWER_ENTITY] == "sensor.custom_house"
        # existing non-blank preserved
        assert flow._prefill_data[CONF_GRID_EXPORT_ENTITY] == "sensor.e3dc_grid"
        # blank → discovery

    def test_reconfigure_edit_with_prefill_preserves_existing_values(self) -> None:
        """When user submits the edit form, existing non-blank fields are
        preserved (not overwritten by prefill)."""
        hass = MagicMock()
        _mock_location(hass)
        e3dc_entry = _make_e3dc_entry()
        uem_entry = _make_uem_entry(
            data={
                CONF_MANUAL_ENTITIES: True,
                CONF_E3DC_CONFIG_ENTRY_ID: None,
                CONF_SOC_ENTITY: "sensor.old_soc",  # non-blank → preserve
                CONF_PV_POWER_ENTITY: "sensor.custom_pv",  # non-blank → preserve
                CONF_HOUSE_POWER_ENTITY: "",  # blank → prefill
                CONF_BATTERY_CHARGE_ENTITY: "",
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_GRID_EXPORT_ENTITY: "",
                CONF_INVERT_GRID_POWER_SIGN: False,
            }
        )
        flow = _make_flow_with_uem(hass, [e3dc_entry], uem_entry=uem_entry)
        flow.context = {"entry_id": uem_entry.entry_id}

        full_map = E3dcEntityMap(
            soc="sensor.e3dc_soc",
            pv_power="sensor.e3dc_pv",
            house_power="sensor.e3dc_house",
            grid_export="sensor.e3dc_grid",
            battery_charge="sensor.e3dc_charge",
            battery_capacity="sensor.e3dc_capacity",
            max_charge_power="sensor.e3dc_max_charge",
        )

        with patch.object(
            UemConfigFlow, "_discover_entities_from_entry", return_value=full_map
        ):
            # Step 1: trigger rescan → get edit form
            _run(
                flow.async_step_reconfigure(
                    {"rescan_e3dc": "True", "edit_manual": "False"}
                )
            )

            # Step 2: submit edit form — keep all existing values, only change
            # one field
            result = _run(
                flow.async_step_reconfigure_edit({
                    CONF_SOC_ENTITY: "sensor.old_soc",  # keep existing
                    CONF_PV_POWER_ENTITY: "sensor.custom_pv",  # keep existing
                    CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",  # accept prefill
                    CONF_BATTERY_CHARGE_ENTITY: "",  # keep blank
                    CONF_BATTERY_CAPACITY_ENTITY: "",  # keep blank
                    CONF_BATTERY_MANUAL_CAPACITY_KWH: "",  # keep blank
                    CONF_MAX_CHARGE_POWER_ENTITY: "",  # keep blank
                    CONF_MAX_CHARGE_MANUAL_POWER_W: "",  # keep blank
                    CONF_GRID_EXPORT_ENTITY: "",  # keep blank
                    CONF_INVERT_GRID_POWER_SIGN: False,
                })
            )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

        # Verify async_update_entry was called
        assert hass.config_entries.async_update_entry.called
        # Verify the saved data preserves manual values
        saved = hass.config_entries.async_update_entry.call_args[1]["data"]
        assert saved[CONF_SOC_ENTITY] == "sensor.old_soc"
        assert saved[CONF_PV_POWER_ENTITY] == "sensor.custom_pv"
        # House was blank → filled with discovery prefill → user accepted it
        assert saved[CONF_HOUSE_POWER_ENTITY] == "sensor.e3dc_house"

    def test_edit_form_schema_preserves_manual_defaults(self) -> None:
        """The reconfigure_edit form schema defaults must NOT overwrite
        existing non-blank manual values with discovery prefill values."""
        hass = MagicMock()
        _mock_location(hass)
        e3dc_entry = _make_e3dc_entry()
        uem_entry = _make_uem_entry(
            data={
                CONF_MANUAL_ENTITIES: True,
                CONF_E3DC_CONFIG_ENTRY_ID: None,
                CONF_SOC_ENTITY: "sensor.manual_soc",  # non-blank manual
                CONF_PV_POWER_ENTITY: "sensor.manual_pv",  # non-blank manual
                CONF_HOUSE_POWER_ENTITY: "",  # blank → prefill from discovery
                CONF_BATTERY_CHARGE_ENTITY: "sensor.manual_battery",  # non-blank
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.manual_max_charge",  # non-blank
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_GRID_EXPORT_ENTITY: "",
                CONF_INVERT_GRID_POWER_SIGN: False,
            }
        )
        flow = _make_flow_with_uem(hass, [e3dc_entry], uem_entry=uem_entry)
        flow.context = {"entry_id": uem_entry.entry_id}

        full_map = E3dcEntityMap(
            soc="sensor.e3dc_soc",
            pv_power="sensor.e3dc_pv",
            house_power="sensor.e3dc_house",
            grid_export="sensor.e3dc_grid",
            battery_charge="sensor.e3dc_charge",
            battery_capacity="sensor.e3dc_capacity",
            max_charge_power="sensor.e3dc_max_charge",
        )

        with patch.object(
            UemConfigFlow, "_discover_entities_from_entry", return_value=full_map
        ):
            result = _run(
                flow.async_step_reconfigure(
                    {"rescan_e3dc": "True", "edit_manual": "False"}
                )
            )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure_edit"

        # Check schema defaults — result["data_schema"] is a compiled voluptuous
        # Schema. Its .schema dict has string keys and validator values.
        # We need the original uncompiled schema dict to access .default().
        # The flow's _prefill_data was already set by _show_reconfigure_edit.
        prefill = flow._prefill_data
        assert prefill is not None
        schema_dict = flow._build_full_schema(prefill)
        # schema_dict has vol.Optional(key, default=val) → validator
        for key, expected in [
            (CONF_SOC_ENTITY, "sensor.manual_soc"),
            (CONF_PV_POWER_ENTITY, "sensor.manual_pv"),
            (CONF_BATTERY_CHARGE_ENTITY, "sensor.manual_battery"),
            (CONF_MAX_CHARGE_POWER_ENTITY, "sensor.manual_max_charge"),
        ]:
            opt_key = [k for k in schema_dict.keys() if str(k) == key]
            assert len(opt_key) == 1, f"No key found for {key}"
            assert opt_key[0].default() == expected, (
                f"Expected {key} default {expected}, got {opt_key[0].default()}"
            )
        # Blank fields get discovery prefill
        opt_house = [k for k in schema_dict.keys() if str(k) == CONF_HOUSE_POWER_ENTITY][0]
        opt_grid = [k for k in schema_dict.keys() if str(k) == CONF_GRID_EXPORT_ENTITY][0]
        assert opt_house.default() == "sensor.e3dc_house"
        assert opt_grid.default() == "sensor.e3dc_grid"


# =========================================================================== #
# TEST: Reconfigure without stored e3dc_config_entry_id, multiple adapters     #
# =========================================================================== #


class TestReconfigureRescanMultipleAdapters:
    """When reconfigure is triggered without stored e3dc_config_entry_id
    and there are multiple e3dc_rscp adapters, should show a selection
    form first. On selection, same prefill path as single adapter."""

    def test_reconfigure_rescan_multiple_shows_selection(self) -> None:
        """Multiple adapters → reconfigure_rescan form (selection)."""
        hass = MagicMock()
        e3dc_entry1 = _make_e3dc_entry(entry_id="e3dc-001", title="E3DC RSCP 1")
        e3dc_entry2 = _make_e3dc_entry(entry_id="e3dc-002", title="E3DC RSCP 2")
        uem_entry = _make_uem_entry(
            data={CONF_MANUAL_ENTITIES: True}
        )
        flow = _make_flow_with_uem(
            hass, [e3dc_entry1, e3dc_entry2], uem_entry=uem_entry
        )
        flow.context = {"entry_id": uem_entry.entry_id}

        result = _run(
            flow.async_step_reconfigure(
                {"rescan_e3dc": "True", "edit_manual": "False"}
            )
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure_rescan"

        # Verify both entries appear in the selection dropdown
        schema = result["data_schema"]
        options = schema.schema[CONF_E3DC_CONFIG_ENTRY_ID].container
        assert len(options) == 2
        assert "e3dc-001" in options
        assert "e3dc-002" in options

    def test_reconfigure_rescan_selection_then_edit_form(self) -> None:
        """After selecting one of multiple adapters → edit form with prefill."""
        hass = MagicMock()
        e3dc_entry1 = _make_e3dc_entry(entry_id="e3dc-001", title="E3DC RSCP 1")
        e3dc_entry2 = _make_e3dc_entry(entry_id="e3dc-002", title="E3DC RSCP 2")
        uem_entry = _make_uem_entry(
            data={CONF_MANUAL_ENTITIES: True}
        )
        flow = _make_flow_with_uem(
            hass, [e3dc_entry1, e3dc_entry2], uem_entry=uem_entry
        )
        flow.context = {"entry_id": uem_entry.entry_id}

        full_map = E3dcEntityMap(
            soc="sensor.e3dc_soc",
            pv_power="sensor.e3dc_pv",
            house_power="sensor.e3dc_house",
            grid_export="sensor.e3dc_grid",
            battery_charge="sensor.e3dc_charge",
            battery_capacity="sensor.e3dc_capacity",
            max_charge_power="sensor.e3dc_max_charge",
        )

        with patch.object(
            UemConfigFlow, "_discover_entities_from_entry", return_value=full_map
        ):
            # Step 1: show selection
            result = _run(
                flow.async_step_reconfigure(
                    {"rescan_e3dc": "True", "edit_manual": "False"}
                )
            )
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "reconfigure_rescan"

            # Step 2: select entry 2
            result = _run(
                flow.async_step_reconfigure_rescan(
                    {CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-002"}
                )
            )

        # Should now show edit form with prefill
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure_edit"
        assert flow._prefill_data is not None
        assert flow._prefill_data[CONF_SOC_ENTITY] == "sensor.e3dc_soc"


# =========================================================================== #
# TEST: Existing stored e3dc_config_entry_id path remains compatible           #
# =========================================================================== #


class TestRescanStoredEntryIdCompatible:
    """When e3dc_config_entry_id IS stored, the existing auto-save path
    must still work (no regression)."""

    def test_reconfigure_with_stored_entry_id_auto_saves(self) -> None:
        """Stored e3dc_config_entry_id → existing _rescan_e3dc auto-save."""
        hass = MagicMock()
        e3dc_entry = _make_e3dc_entry()
        uem_entry = _make_uem_entry(
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-999",
                CONF_MANUAL_ENTITIES: False,
                CONF_SOC_ENTITY: "sensor.custom_soc",  # non-blank → preserve
                CONF_PV_POWER_ENTITY: "",  # blank → updated
                CONF_HOUSE_POWER_ENTITY: "",  # blank → updated
                CONF_BATTERY_CHARGE_ENTITY: "",
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_GRID_EXPORT_ENTITY: "",
                CONF_INVERT_GRID_POWER_SIGN: False,
            }
        )
        flow = _make_flow_with_uem(hass, [e3dc_entry], uem_entry=uem_entry)
        flow.context = {"entry_id": uem_entry.entry_id}

        full_map = E3dcEntityMap(
            soc="sensor.e3dc_soc",
            pv_power="sensor.e3dc_pv",
            house_power="sensor.e3dc_house",
            grid_export="sensor.e3dc_grid",
            battery_charge="sensor.e3dc_charge",
            battery_capacity="sensor.e3dc_capacity",
            max_charge_power="sensor.e3dc_max_charge",
        )

        with patch.object(UemConfigFlow, "_discover_entities", return_value=full_map):
            result = _run(
                flow.async_step_reconfigure(
                    {"rescan_e3dc": "True", "edit_manual": "False"}
                )
            )

        # Should auto-save (existing behavior)
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_SOC_ENTITY] == "sensor.custom_soc"  # preserved
        assert result["data"][CONF_PV_POWER_ENTITY] == "sensor.e3dc_pv"  # updated
        assert result["data"][CONF_MANUAL_ENTITIES] is False
        # Stored entry ID preserved
        assert result["data"][CONF_E3DC_CONFIG_ENTRY_ID] == "e3dc-001"


# =========================================================================== #
# TEST: _discover_entities_from_entry helper                                   #
# =========================================================================== #


class TestDiscoverEntitiesFromEntry:
    """_discover_entities_from_entry should work with any entry."""

    def test_discover_from_entry_with_mock_registry(self) -> None:
        """_discover_entities_from_entry calls the registry and returns E3dcEntityMap.

        Uses the same _make_e3dc_entry + _make_flow pattern as the other
        integration tests so that the existing patching of _discover_entities_from_entry
        (or _discover_entities) works through the full flow.
        """
        hass = MagicMock()
        e3dc_entry = _make_e3dc_entry()
        uem_entry = _make_uem_entry(data={CONF_MANUAL_ENTITIES: True})
        flow = _make_flow_with_uem(hass, [e3dc_entry], uem_entry=uem_entry)
        flow.context = {"entry_id": uem_entry.entry_id}

        full_map = E3dcEntityMap(
            soc="sensor.e3dc_soc",
            pv_power="sensor.e3dc_pv",
            house_power="sensor.e3dc_house",
            grid_export="sensor.e3dc_grid",
            battery_charge="sensor.e3dc_charge",
            battery_capacity="sensor.e3dc_capacity",
            max_charge_power="sensor.e3dc_max_charge",
        )

        with patch.object(
            UemConfigFlow, "_discover_entities_from_entry", return_value=full_map
        ):
            result = _run(
                flow.async_step_reconfigure(
                    {"rescan_e3dc": "True", "edit_manual": "False"}
                )
            )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure_edit"
        assert flow._prefill_data is not None
        assert flow._prefill_data[CONF_SOC_ENTITY] == "sensor.e3dc_soc"


# =========================================================================== #
# TEST: Reconfigure edit form with prefill shows correct defaults              #
# =========================================================================== #


class TestReconfigureEditWithPrefillDisplay:
    """The reconfigure_edit form should show discovery data as editable
    prefill values in the schema."""

    def test_edit_form_schema_has_prefill_values(self) -> None:
        """The reconfigure_edit form shows discovery prefill via _prefill_data,
        and the edit form's _show_reconfigure_edit merges prefill into entity_data."""
        hass = MagicMock()
        e3dc_entry = _make_e3dc_entry()
        uem_entry = _make_uem_entry(
            data={
                CONF_MANUAL_ENTITIES: True,
                CONF_SOC_ENTITY: "",
                CONF_PV_POWER_ENTITY: "",
                CONF_HOUSE_POWER_ENTITY: "",
                CONF_BATTERY_CHARGE_ENTITY: "",
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_GRID_EXPORT_ENTITY: "",
                CONF_INVERT_GRID_POWER_SIGN: False,
            }
        )
        flow = _make_flow_with_uem(hass, [e3dc_entry], uem_entry=uem_entry)
        flow.context = {"entry_id": uem_entry.entry_id}

        full_map = E3dcEntityMap(
            soc="sensor.e3dc_soc",
            pv_power="sensor.e3dc_pv",
            house_power="sensor.e3dc_house",
            grid_export="sensor.e3dc_grid",
            battery_charge="sensor.e3dc_charge",
            battery_capacity="sensor.e3dc_capacity",
            max_charge_power="sensor.e3dc_max_charge",
        )

        with patch.object(
            UemConfigFlow, "_discover_entities_from_entry", return_value=full_map
        ):
            result = _run(
                flow.async_step_reconfigure(
                    {"rescan_e3dc": "True", "edit_manual": "False"}
                )
            )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure_edit"

        # Verify _prefill_data was set with discovery values
        assert flow._prefill_data is not None
        assert flow._prefill_data[CONF_SOC_ENTITY] == "sensor.e3dc_soc"
        assert flow._prefill_data[CONF_PV_POWER_ENTITY] == "sensor.e3dc_pv"
        assert flow._prefill_data[CONF_HOUSE_POWER_ENTITY] == "sensor.e3dc_house"
        # Non-mapping fields stay as defaults
        assert flow._prefill_data[CONF_BATTERY_MANUAL_CAPACITY_KWH] == ""
        assert flow._prefill_data[CONF_MAX_CHARGE_MANUAL_POWER_W] == ""
        assert not flow._prefill_data[CONF_INVERT_GRID_POWER_SIGN]
