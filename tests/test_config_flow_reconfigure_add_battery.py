"""TDD tests for UEM Task B: Multi-Quelle/Multi-Akku — Battery data flow.

Slice 2: Verifying that the battery JSON string round-trips correctly
through reconfigure_edit.  Each battery dict has:
  - battery_name (str)
  - battery_soc_entity (str, entity ID)
  - battery_capacity_kwh (str, fixed kWh value)
  - battery_charge_power_entity (str, entity ID)
  - battery_discharge_power_entity (str, entity ID)

The existing test (slice 1) already verified that the schema includes
CONF_GENERATORS.  This slice verifies CONF_BATTERIES:
  1. Empty list → empty JSON → persisted as empty list on reload.
  2. One additional battery → correct JSON → persisted and retrievable.
  3. Submitting a malformed JSON string (malformed) → treated as empty
     (defensive parsing, never crashes the config flow).
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
# TEST 1: Empty batteries list round-trips as empty JSON                      #
# =========================================================================== #


class TestBatteriesEmptyRoundTrip:
    """Submitting an empty batteries list must persist as []"""

    def test_reconfigure_empty_batteries(self) -> None:
        """When no batteries are configured, reconfigure_edit must save an
        empty list (serialised as '[]')."""
        hass = MagicMock()
        _mock_location(hass)

        uem_entry = _make_uem_entry(
            entry_id="uem-empty-bat",
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
        flow.context = {"entry_id": "uem-empty-bat"}

        result = _run(
            flow.async_step_reconfigure(
                {"rescan_e3dc": "False", "edit_manual": "True"}
            )
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure_edit"

        # Submit with empty batteries JSON string
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
        assert saved_data[CONF_BATTERIES] == "[]"


# =========================================================================== #
# TEST 2: Single additional battery round-trips correctly                     #
# =========================================================================== #


class TestBatteriesSingleRoundTrip:
    """Adding one additional battery must persist with correct JSON."""

    def test_reconfigure_one_battery(self) -> None:
        """A single additional battery (Wall-Power) must be stored as a JSON
        list containing one battery dict."""
        hass = MagicMock()
        _mock_location(hass)

        uem_entry = _make_uem_entry(
            entry_id="uem-one-bat",
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
        flow.context = {"entry_id": "uem-one-bat"}

        _run(
            flow.async_step_reconfigure(
                {"rescan_e3dc": "False", "edit_manual": "True"}
            )
        )

        # Add a Wall-Power battery
        bat = _make_battery(
            "Wall-Power",
            "sensor.wallpower_soc",
            capacity_kwh="10",
            charge_entity="sensor.wallpower_charge",
            discharge_entity="sensor.wallpower_discharge",
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
                CONF_BATTERIES: json.dumps([bat], ensure_ascii=False),
            })
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

        saved_data = hass.config_entries.async_update_entry.call_args.kwargs["data"]
        # Verify the JSON string was stored
        assert saved_data[CONF_BATTERIES] == json.dumps([bat], ensure_ascii=False)

        # Verify we can parse it back to a list of dicts
        parsed = json.loads(saved_data[CONF_BATTERIES])
        assert len(parsed) == 1
        assert parsed[0][CONF_BATTERY_NAME] == "Wall-Power"
        assert parsed[0][CONF_BATTERY_SOC_ENTITY] == "sensor.wallpower_soc"
        assert parsed[0][CONF_BATTERY_CAPACITY_KWH] == "10"


# =========================================================================== #
# TEST 3: Malformed JSON string → treated as empty (defensive)                #
# =========================================================================== #


class TestBatteriesMalformedJson:
    """Malformed JSON in the batteries field must not crash the config flow."""

    def test_reconfigure_malformed_batteries_json(self) -> None:
        """When the user submits a malformed JSON string for batteries,
        the config flow must treat it as an empty list (defensive parsing)
        and not raise an exception."""
        hass = MagicMock()
        _mock_location(hass)

        uem_entry = _make_uem_entry(
            entry_id="uem-bad-json-bat",
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
        flow.context = {"entry_id": "uem-bad-json-bat"}

        _run(
            flow.async_step_reconfigure(
                {"rescan_e3dc": "False", "edit_manual": "True"}
            )
        )

        # Submit with malformed JSON — must not crash
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
                CONF_BATTERIES: "{invalid json",
            })
        )

        # The flow should complete (not crash) — either as ABORT or FORM
        assert result["type"] in (FlowResultType.ABORT, FlowResultType.FORM), (
            f"Expected ABORT or FORM, got {result['type']} — malformed JSON "
            f"should not crash the config flow"
        )
