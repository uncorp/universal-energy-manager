"""TDD tests for UEM Task B: Multi-Quelle/Multi-Akku — Battery preservation.

Slice: Verifying that existing batteries survive a reconfigure_edit round-trip
when the user does not touch the batteries field.  This is the battery analogue
of ``TestGeneratorsPreservedFromInstall`` in
``test_config_flow_reconfigure_add_generator.py``.

Each battery dict has:
  - battery_name (str)
  - battery_soc_entity (str, entity ID)
  - battery_capacity_kwh (str, fixed kWh value)
  - battery_charge_power_entity (str, entity ID)
  - battery_discharge_power_entity (str, entity ID)
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.universal_energy_manager.config_flow import (
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    UemConfigFlow,
)
from custom_components.universal_energy_manager.const import (
    CONF_BATTERIES,
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_CHARGE_POWER_ENTITY,
    CONF_BATTERY_DISCHARGE_POWER_ENTITY,
    CONF_BATTERY_MANUAL_CAPACITY_KWH,
    CONF_BATTERY_NAME,
    CONF_BATTERY_SOC_ENTITY,
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
)

# --------------------------------------------------------------------------- #
# Helpers                                                                       #
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


def _make_forecast_solar_entry(
    entry_id: str = "forecast-solar-001",
    title: str = "Forecast.Solar",
) -> config_entries.ConfigEntry:
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=FORECAST_SOLAR_DOMAIN,
        title=title,
        data={},
        source="user",
        entry_id=entry_id,
        unique_id="forecast-solar:test",
        state=config_entries.ConfigEntryState.LOADED,
    )


def _make_uem_entry(
    entry_id: str = "uem-001",
    unique_id: str = "e3dc_rscp:HW-12345",
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


def _make_flow_with_all(
    hass: MagicMock,
    e3dc_entries: list[config_entries.ConfigEntry] | None = None,
    forecast_entries: list[config_entries.ConfigEntry] | None = None,
    uem_entry: config_entries.ConfigEntry | None = None,
) -> UemConfigFlow:
    """Build a UemConfigFlow with mocked async_entries for all domains."""
    flow = UemConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.handler = DOMAIN
    ce = hass.config_entries
    _all: dict[str, list[config_entries.ConfigEntry]] = {
        E3DC_RSCP_DOMAIN: e3dc_entries or [],
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


def _make_battery(
    name: str,
    soc_entity: str,
    capacity_kwh: str = "",
    charge_entity: str = "",
    discharge_entity: str = "",
) -> dict:
    """Helper to create a battery dict."""
    return {
        CONF_BATTERY_NAME: name,
        CONF_BATTERY_SOC_ENTITY: soc_entity,
        CONF_BATTERY_CAPACITY_KWH: capacity_kwh,
        CONF_BATTERY_CHARGE_POWER_ENTITY: charge_entity,
        CONF_BATTERY_DISCHARGE_POWER_ENTITY: discharge_entity,
    }


# =========================================================================== #
# TEST 1: Existing batteries survive reconfigure_edit unchanged                #
# =========================================================================== #


class TestBatteriesPreservedFromReconfigure:
    """A battery stored during initial install must survive reconfigure_edit."""

    def test_reconfigure_preserves_existing_battery(self) -> None:
        """When the UEM entry already has one battery (from initial install),
        reconfigure_edit must preserve it even when the user does not touch
        the batteries field."""
        hass = MagicMock()
        _mock_location(hass)

        existing_battery = _make_battery(
            "Wall-Power",
            "sensor.wallpower_soc",
            capacity_kwh="10",
            charge_entity="sensor.wallpower_charge",
            discharge_entity="sensor.wallpower_discharge",
        )
        uem_entry = _make_uem_entry(
            entry_id="uem-preserve-bat",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-12345",
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_MANUAL_ENTITIES: False,
                CONF_INVERT_GRID_POWER_SIGN: False,
                CONF_FORECAST_SOLAR_ENTRY_IDS: ["forecast-solar-001"],
                CONF_BATTERIES: json.dumps([existing_battery], ensure_ascii=False),
            },
        )

        e3dc_entry = _make_e3dc_entry()
        forecast_entry = _make_forecast_solar_entry()

        flow = _make_flow_with_all(
            hass,
            e3dc_entries=[e3dc_entry],
            forecast_entries=[forecast_entry],
            uem_entry=uem_entry,
        )
        flow.context = {"entry_id": "uem-preserve-bat"}

        _run(
            flow.async_step_reconfigure(
                {"rescan_e3dc": "False", "edit_manual": "True"}
            )
        )

        # Submit without changing batteries (should preserve the existing one)
        result = _run(
            flow.async_step_reconfigure_edit({
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_INVERT_GRID_POWER_SIGN: False,
                CONF_BATTERIES: json.dumps([existing_battery], ensure_ascii=False),
            })
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

        saved_data = hass.config_entries.async_update_entry.call_args.kwargs["data"]
        parsed = json.loads(saved_data[CONF_BATTERIES])
        assert len(parsed) == 1
        assert parsed[0][CONF_BATTERY_NAME] == "Wall-Power"
        assert parsed[0][CONF_BATTERY_SOC_ENTITY] == "sensor.wallpower_soc"
        assert parsed[0][CONF_BATTERY_CAPACITY_KWH] == "10"


# =========================================================================== #
# TEST 2: Existing batteries + added battery survive reconfigure               #
# =========================================================================== #


class TestBatteriesPreservedAndExtended:
    """Existing batteries must survive and new ones can be added."""

    def test_reconfigure_preserves_and_adds_battery(self) -> None:
        """When the entry has one battery and the user adds a second one,
        both must be present after reconfigure."""
        hass = MagicMock()
        _mock_location(hass)

        existing_battery = _make_battery(
            "Wall-Power",
            "sensor.wallpower_soc",
            capacity_kwh="10",
            charge_entity="sensor.wallpower_charge",
            discharge_entity="sensor.wallpower_discharge",
        )
        added_battery = _make_battery(
            "Solar-Battery",
            "sensor.solar_battery_soc",
            capacity_kwh="5",
            charge_entity="sensor.solar_battery_charge",
            discharge_entity="sensor.solar_battery_discharge",
        )
        batteries = [existing_battery, added_battery]

        uem_entry = _make_uem_entry(
            entry_id="uem-add-bat",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-12345",
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_MANUAL_ENTITIES: False,
                CONF_INVERT_GRID_POWER_SIGN: False,
                CONF_FORECAST_SOLAR_ENTRY_IDS: ["forecast-solar-001"],
                CONF_BATTERIES: json.dumps([existing_battery], ensure_ascii=False),
            },
        )

        e3dc_entry = _make_e3dc_entry()
        forecast_entry = _make_forecast_solar_entry()

        flow = _make_flow_with_all(
            hass,
            e3dc_entries=[e3dc_entry],
            forecast_entries=[forecast_entry],
            uem_entry=uem_entry,
        )
        flow.context = {"entry_id": "uem-add-bat"}

        _run(
            flow.async_step_reconfigure(
                {"rescan_e3dc": "False", "edit_manual": "True"}
            )
        )

        result = _run(
            flow.async_step_reconfigure_edit({
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_INVERT_GRID_POWER_SIGN: False,
                CONF_BATTERIES: json.dumps(batteries, ensure_ascii=False),
            })
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

        saved_data = hass.config_entries.async_update_entry.call_args.kwargs["data"]
        parsed = json.loads(saved_data[CONF_BATTERIES])
        assert len(parsed) == 2
        assert parsed[0][CONF_BATTERY_NAME] == "Wall-Power"
        assert parsed[1][CONF_BATTERY_NAME] == "Solar-Battery"
        assert parsed[1][CONF_BATTERY_CAPACITY_KWH] == "5"


# =========================================================================== #
# TEST 3: Existing battery removed via empty list                              #
# =========================================================================== #


class TestBatteriesRemoval:
    """Removing all batteries via empty list must work."""

    def test_reconfigure_removes_existing_battery(self) -> None:
        """When the entry has one battery and the user submits an empty list,
        the battery must be removed."""
        hass = MagicMock()
        _mock_location(hass)

        existing_battery = _make_battery(
            "Wall-Power",
            "sensor.wallpower_soc",
            capacity_kwh="10",
            charge_entity="sensor.wallpower_charge",
            discharge_entity="sensor.wallpower_discharge",
        )
        uem_entry = _make_uem_entry(
            entry_id="uem-remove-bat",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-12345",
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_MANUAL_ENTITIES: False,
                CONF_INVERT_GRID_POWER_SIGN: False,
                CONF_FORECAST_SOLAR_ENTRY_IDS: ["forecast-solar-001"],
                CONF_BATTERIES: json.dumps([existing_battery], ensure_ascii=False),
            },
        )

        e3dc_entry = _make_e3dc_entry()
        forecast_entry = _make_forecast_solar_entry()

        flow = _make_flow_with_all(
            hass,
            e3dc_entries=[e3dc_entry],
            forecast_entries=[forecast_entry],
            uem_entry=uem_entry,
        )
        flow.context = {"entry_id": "uem-remove-bat"}

        _run(
            flow.async_step_reconfigure(
                {"rescan_e3dc": "False", "edit_manual": "True"}
            )
        )

        result = _run(
            flow.async_step_reconfigure_edit({
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
                CONF_INVERT_GRID_POWER_SIGN: False,
                CONF_BATTERIES: "[]",
            })
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

        saved_data = hass.config_entries.async_update_entry.call_args.kwargs["data"]
        parsed = json.loads(saved_data[CONF_BATTERIES])
        assert len(parsed) == 0
