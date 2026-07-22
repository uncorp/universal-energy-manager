"""Config-flow integration tests against a real Home Assistant test instance.

Uses direct UemConfigFlow instantiation with a mock hass (same pattern as
test_config_flow_no_e3dc_abort.py) because the conftest's MockHass does not
provide a full HA event loop.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.universal_energy_manager.config_flow import (
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    FORECAST_SOLAR_DOMAIN,
    UemConfigFlow,
)
from custom_components.universal_energy_manager.const import (
    CONF_FORECAST_SOLAR_ENTRY_IDS,
    CONF_MANUAL_ENTITIES,
)


def _run(coro):
    """Run a coroutine on a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_flow(hass, e3dc_entries=None, forecast_entries=None):
    """Create a UemConfigFlow with the given hass and pre-populated entries."""
    flow = UemConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.handler = DOMAIN

    if e3dc_entries is None:
        e3dc_entries = []
    if forecast_entries is None:
        forecast_entries = []

    _all_entries_by_domain = {
        E3DC_RSCP_DOMAIN: e3dc_entries,
        FORECAST_SOLAR_DOMAIN: forecast_entries,
    }

    def _async_entries(domain=None, *args, **kwargs):
        if domain is None:
            result = []
            for entries in _all_entries_by_domain.values():
                result.extend(entries)
            return result
        return _all_entries_by_domain.get(domain, [])

    hass.config_entries.async_entries = MagicMock(side_effect=_async_entries)
    hass.config_entries.async_entry_for_domain_unique_id = MagicMock(
        return_value=None
    )
    return flow


def _mock_location(hass, lat=52.5200, lon=13.4050):
    loc = MagicMock()
    loc.latitude = lat
    loc.longitude = lon
    hass.config.location = loc


def _make_manual_data():
    return {
        "soc_entity": "sensor.manual_soc",
        "pv_power_entity": "sensor.manual_pv",
        "house_power_entity": "sensor.manual_house",
        "grid_export_entity": "sensor.manual_grid",
        "battery_charge_entity": "sensor.manual_charge",
        "battery_capacity_entity": "sensor.manual_capacity",
        "max_charge_power_entity": "sensor.manual_max",
    }


# =========================================================================== #
# Integration tests: config flow without e3dc_rscp                           #
# =========================================================================== #


def test_user_flow_shows_choice_without_e3dc_rscp():
    """Without e3dc_rscp, UEM shows a choice form instead of aborting."""
    hass = MagicMock()
    _mock_location(hass)
    flow = _make_flow(hass, e3dc_entries=[])

    result = _run(flow.async_step_user())

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "no_e3dc_choice"


def test_user_flow_cancel_aborts_without_e3dc_rscp():
    """Selecting cancel on the choice form aborts with a clear message."""
    hass = MagicMock()
    _mock_location(hass)
    flow = _make_flow(hass, e3dc_entries=[])

    result = _run(flow.async_step_user())
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "no_e3dc_choice"

    result = _run(
        flow.async_step_no_e3dc_choice({"confirm": "cancel"})
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "e3dc_rscp_optional_cancel"


def test_user_flow_continues_to_manual_mapping_without_e3dc():
    """Selecting continue on the choice form goes to manual mapping."""
    hass = MagicMock()
    _mock_location(hass)
    flow = _make_flow(hass, e3dc_entries=[])

    result = _run(flow.async_step_user())
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "no_e3dc_choice"

    result = _run(
        flow.async_step_no_e3dc_choice({"confirm": "continue"})
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual_mapping"


def test_manual_mapping_creates_entry_without_e3dc():
    """Manual mapping without e3dc_rscp creates a valid UEM entry."""
    hass = MagicMock()
    _mock_location(hass)
    flow = _make_flow(hass, e3dc_entries=[])

    result = _run(flow.async_step_user())
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "no_e3dc_choice"

    result = _run(
        flow.async_step_no_e3dc_choice({"confirm": "continue"})
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual_mapping"

    result = _run(flow.async_step_manual_mapping(_make_manual_data()))

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["e3dc_config_entry_id"] is None
    assert result["data"]["e3dc_source_unique_id"] is None
    assert result["data"][CONF_MANUAL_ENTITIES] is True
    assert result["data"]["soc_entity"] == "sensor.manual_soc"


def test_user_flow_prefills_e3dc_rscp_entities_and_creates_shadow_entry():
    """The real flow must create only a Shadow entry from registry discovery."""
    hass = MagicMock()
    _mock_location(hass)

    source_entry = config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=E3DC_RSCP_DOMAIN,
        title="E3DC S10",
        data={},
        source="user",
        entry_id="e3dc-001",
        unique_id="S10E-12345",
        state=config_entries.ConfigEntryState.LOADED,
    )

    forecast_entries = [
        config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain="forecast_solar",
            title="Hauptdach",
            data={},
            source="user",
            entry_id="fs-001",
            unique_id="fs-001",
            state=config_entries.ConfigEntryState.NOT_LOADED,
        ),
        config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain="forecast_solar",
            title="Balkon",
            data={},
            source="user",
            entry_id="fs-002",
            unique_id="fs-002",
            state=config_entries.ConfigEntryState.NOT_LOADED,
        ),
    ]

    flow = _make_flow(
        hass,
        e3dc_entries=[source_entry],
        forecast_entries=forecast_entries,
    )

    # Patch discover_e3dc_entities to return a map with all core entities
    e3dc_map = MagicMock()
    e3dc_map.soc = "sensor.e3dc_soc"
    e3dc_map.pv_power = "sensor.e3dc_pv"
    e3dc_map.house_power = "sensor.e3dc_house"
    e3dc_map.grid_export = "sensor.e3dc_grid"
    e3dc_map.battery_charge = "sensor.e3dc_battery"
    e3dc_map.battery_capacity = "sensor.e3dc_capacity"
    e3dc_map.max_charge_power = "sensor.e3dc_max_charge"

    with patch(
        "custom_components.universal_energy_manager.config_flow.discover_e3dc_entities",
        return_value=e3dc_map,
    ):
        result = _run(flow.async_step_user())

    # Should go to confirm step with e3dc entry
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert "detected" in result.get("description_placeholders", {})

    # Confirm with empty user input (accept prefill)
    result = _run(flow.async_step_confirm({}))

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "UEM – Universal Energy Manager"
    assert result["data"]["e3dc_source_unique_id"] == "S10E-12345"
    assert result["data"][CONF_FORECAST_SOLAR_ENTRY_IDS] == [
        "fs-001",
        "fs-002",
    ]
    assert result["data"][CONF_MANUAL_ENTITIES] is False
