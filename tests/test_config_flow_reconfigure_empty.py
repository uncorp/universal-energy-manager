"""Regression test: reconfigure_edit must accept completely empty forms (Req 4).

Requirement 4: Keine einzige Entität oder fixe Kapazität/Ladeleistung ist Pflicht.
OK/Speichern muss auch bei komplett leerem Formular funktionieren. Dann bleibt der
Eintrag klar im sicheren Status "Shadow – Einrichtung unvollständig" und plant/steuert nicht.

This test verifies that the reconfigure_edit path — not just the initial
manual_mapping path — accepts an empty form without errors.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from homeassistant import config_entries
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
    CONF_FORECAST_SOLAR_ENTRY_IDS,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_INVERT_GRID_POWER_SIGN,
    CONF_MANUAL_ENTITIES,
    CONF_MAX_CHARGE_MANUAL_POWER_W,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    FORECAST_SOLAR_DOMAIN,
    SHADOW_STATUS_UNVOLLSTANDIG,
)

# --------------------------------------------------------------------------- #
# Helpers                                                                        #
# --------------------------------------------------------------------------- #


def _make_uem_entry(
    entry_id: str = "uem-001",
    data: dict | None = None,
) -> config_entries.ConfigEntry:
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="UEM – Universal Energy Manager",
        data=data or {},
        source="user",
        entry_id=entry_id,
        unique_id="uem:manual:test",
        state=config_entries.ConfigEntryState.LOADED,
    )


def _make_flow_with_uem(
    hass: MagicMock,
    uem_entry: config_entries.ConfigEntry,
    forecast_entries: list[config_entries.ConfigEntry] | None = None,
) -> UemConfigFlow:
    flow = UemConfigFlow()
    flow.hass = hass
    flow.context = {"entry_id": uem_entry.entry_id}
    flow.handler = DOMAIN
    ce = hass.config_entries
    _all: dict[str, list[config_entries.ConfigEntry]] = {
        DOMAIN: [uem_entry],
        E3DC_RSCP_DOMAIN: [],
        FORECAST_SOLAR_DOMAIN: forecast_entries or [],
    }

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
# TEST 1: reconfigure_edit accepts completely empty form                      #
# =========================================================================== #


class TestReconfigureEditEmptyForm:
    """Req 4: reconfigure_edit must accept an empty form."""

    def _make_complete_entry(self) -> config_entries.ConfigEntry:
        """Create a fully-populated UEM entry to edit."""
        return _make_uem_entry(
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-999",
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_MANUAL_ENTITIES: False,
                CONF_INVERT_GRID_POWER_SIGN: True,
            }
        )

    def test_reconfigure_edit_empty_form_aborts_successfully(self) -> None:
        """Submitting an empty dict in reconfigure_edit must abort with
        success and call async_update_entry with empty entity fields."""
        hass = MagicMock()
        _mock_location(hass)
        entry = self._make_complete_entry()
        flow = _make_flow_with_uem(hass, entry)

        # Submit completely empty — all entity fields blank
        result = _run(
            flow.async_step_reconfigure_edit({
                CONF_SOC_ENTITY: "",
                CONF_PV_POWER_ENTITY: "",
                CONF_HOUSE_POWER_ENTITY: "",
                CONF_BATTERY_CHARGE_ENTITY: "",
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_GRID_EXPORT_ENTITY: "",
                CONF_INVERT_GRID_POWER_SIGN: True,
            })
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

        # Verify async_update_entry was called (real HA path)
        assert hass.config_entries.async_update_entry.called

    def test_reconfigure_edit_empty_all_entity_strings(self) -> None:
        """Submitting all-entity fields as empty strings must work."""
        hass = MagicMock()
        _mock_location(hass)
        entry = self._make_complete_entry()
        flow = _make_flow_with_uem(hass, entry)

        result = _run(
            flow.async_step_reconfigure_edit({
                CONF_SOC_ENTITY: "",
                CONF_PV_POWER_ENTITY: "",
                CONF_HOUSE_POWER_ENTITY: "",
                CONF_BATTERY_CHARGE_ENTITY: "",
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_GRID_EXPORT_ENTITY: "",
                CONF_INVERT_GRID_POWER_SIGN: True,
            })
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

    def test_reconfigure_edit_preserves_non_entity_fields(self) -> None:
        """Non-entity fields (e3dc_config_entry_id, etc.) must be preserved
        in the data passed to async_update_entry.

        Note: forecast_solar_entry_ids is re-collected from HA's current state
        during reconfigure_edit (not preserved from the old entry), so the
        assertion must match what the mock returns.
        """
        from custom_components.universal_energy_manager.const import (
            FORECAST_SOLAR_DOMAIN,
        )

        hass = MagicMock()
        _mock_location(hass)

        # Existing Forecast.Solar entry in HA (so re-collection picks it up)
        forecast_entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=FORECAST_SOLAR_DOMAIN,
            title="Forecast.Solar",
            data={},
            source="user",
            entry_id="forecast-solar-existing",
            unique_id="forecast-solar:test",
            state=config_entries.ConfigEntryState.LOADED,
        )

        entry = _make_uem_entry(
            entry_id="uem-preserve",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-preserved",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-preserved",
                CONF_SOC_ENTITY: "",
                CONF_PV_POWER_ENTITY: "",
                CONF_HOUSE_POWER_ENTITY: "",
                CONF_BATTERY_CHARGE_ENTITY: "",
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_GRID_EXPORT_ENTITY: "",
                CONF_MANUAL_ENTITIES: False,
                CONF_INVERT_GRID_POWER_SIGN: True,
                CONF_FORECAST_SOLAR_ENTRY_IDS: ["fs-old"],
            },
        )
        flow = _make_flow_with_uem(
            hass, forecast_entries=[forecast_entry], uem_entry=entry
        )

        # Submit ALL 10 schema fields with sign convention changed
        result = _run(
            flow.async_step_reconfigure_edit({
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
            })
        )
        assert result["type"] == FlowResultType.ABORT

        # Verify the data passed to async_update_entry preserves non-entity fields
        # and includes the sign convention change
        call_data = hass.config_entries.async_update_entry.call_args.kwargs["data"]
        assert call_data[CONF_E3DC_CONFIG_ENTRY_ID] == "e3dc-preserved"
        assert call_data[CONF_E3DC_SOURCE_UNIQUE_ID] == "HW-preserved"
        assert call_data[CONF_INVERT_GRID_POWER_SIGN] is False
        # forecast_solar_entry_ids is re-collected from HA state, not preserved
        assert call_data[CONF_FORECAST_SOLAR_ENTRY_IDS] == ["forecast-solar-existing"]

    def test_reconfigure_edit_accepts_partial_updates(self) -> None:
        """Submitting ALL schema fields where only some are changed must
        preserve non-entity fields in the data passed to async_update_entry."""
        hass = MagicMock()
        _mock_location(hass)
        entry = _make_uem_entry(
            entry_id="uem-partial",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-999",
                CONF_SOC_ENTITY: "sensor.old_soc",
                CONF_PV_POWER_ENTITY: "sensor.old_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.old_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.old_grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.old_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.old_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.old_max",
                CONF_MANUAL_ENTITIES: False,
                CONF_INVERT_GRID_POWER_SIGN: True,
                CONF_FORECAST_SOLAR_ENTRY_IDS: ["fs-old"],
            },
        )
        flow = _make_flow_with_uem(hass, entry)

        # Submit ALL 10 schema fields — only house_power changed
        result = _run(
            flow.async_step_reconfigure_edit({
                CONF_SOC_ENTITY: "",
                CONF_PV_POWER_ENTITY: "",
                CONF_HOUSE_POWER_ENTITY: "sensor.new_house",
                CONF_BATTERY_CHARGE_ENTITY: "",
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_GRID_EXPORT_ENTITY: "",
                CONF_INVERT_GRID_POWER_SIGN: True,
            })
        )
        assert result["type"] == FlowResultType.ABORT

        call_data = hass.config_entries.async_update_entry.call_args.kwargs["data"]
        # Updated field
        assert call_data[CONF_HOUSE_POWER_ENTITY] == "sensor.new_house"
        # Unchanged non-entity fields preserved
        assert call_data[CONF_E3DC_CONFIG_ENTRY_ID] == "e3dc-001"
        assert call_data[CONF_E3DC_SOURCE_UNIQUE_ID] == "HW-999"


# =========================================================================== #
# TEST 2: Shadow status after reconfigure with empty entities                  #
# =========================================================================== #


class TestReconfigureEmptyShadowStatus:
    """After reconfigure with empty entities, coordinator must stay in Shadow."""

    def test_coordinator_shadow_after_empty_reconfigure(self) -> None:
        """A UEM entry that was reconfigured with empty entities must stay
        in Shadow status and not send any commands."""
        from custom_components.universal_energy_manager.coordinator import (
            ShadowData,
            UemShadowCoordinator,
        )

        hass = MagicMock()
        entry = _make_uem_entry(
            entry_id="uem-shadow-test",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: None,
                CONF_E3DC_SOURCE_UNIQUE_ID: None,
                CONF_MANUAL_ENTITIES: True,
                CONF_SOC_ENTITY: "",
                CONF_PV_POWER_ENTITY: "",
                CONF_HOUSE_POWER_ENTITY: "",
                CONF_GRID_EXPORT_ENTITY: "",
                CONF_BATTERY_CHARGE_ENTITY: "",
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_INVERT_GRID_POWER_SIGN: True,
            },
        )
        hass.config_entries.async_entries.return_value = [entry]
        hass.states.get.return_value = None
        hass.states.async_all.return_value = []

        coord = UemShadowCoordinator(hass, entry)
        result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            coord._async_update_data()
        )
        assert isinstance(result, ShadowData)
        assert result.status == SHADOW_STATUS_UNVOLLSTANDIG
        assert result.commands_sent is False
