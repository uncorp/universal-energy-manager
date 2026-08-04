"""TDD regression test: Reconfigure einer vorhandenen UEM-Instanz mit
vorhandenem Forecast.Solar-Entry speichert dessen Entry-ID.

Bug-Befund:
- UEM sammelt `forecast_solar_entry_ids` bei Erstinstallation (confirm/manual_mapping).
- async_step_reconfigure_edit hingegen re-collectet keine Forecast.Solar-Entry-IDs.
- Deshalb bleibt `forecast_connected` (coordinator-seitig) auf False, wenn ein
  Forecast.Solar-Entry NACH der UEM-Erstinstandrichtung eingerichtet wird.

Dieser Test prüft die minimale reproduzierbare failure scenario:
  1. UEM-Eintrag existiert bereits mit empty forecast_solar_entry_ids (None/[]).
  2. Es gibt ein Forecast.Solar-ConfigEntry in HA.
  3. Reconfigure edit wird durchgespielt (show form → submit).
  4. Das gespeicherte data dict MUSS die Forecast.Solar entry ID enthalten.
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


# =========================================================================== #
# TEST 1: Reconfigure existing UEM with newly added Forecast.Solar entry     #
# =========================================================================== #


class TestReconfigureForecastSolarNewEntry:
    """Reconfigure einer vorhandenen UEM-Instanz, bei der ein Forecast.Solar-
    ConfigEntry nachträglich hinzugefügt wurde, muss dessen Entry-ID speichern."""

    def test_reconfigure_collects_forecast_solar_entry_ids(self) -> None:
        """When reconfigure_edit saves, it must include any currently existing
        Forecast.Solar entry IDs — even if the UEM entry was created before the
        Forecast.Solar integration was set up (empty list in existing data)."""
        hass = MagicMock()
        _mock_location(hass)

        # Existing UEM entry: created BEFORE any Forecast.Solar was configured
        # → forecast_solar_entry_ids is empty (the bug scenario)
        uem_entry = _make_uem_entry(
            entry_id="uem-001",
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
                CONF_FORECAST_SOLAR_ENTRY_IDS: [],  # Empty — no FS at install time
            },
        )

        # Forecast.Solar entry added LATER (the key scenario)
        forecast_entry = _make_forecast_solar_entry(
            entry_id="forecast-solar-new",
        )

        e3dc_entry = _make_e3dc_entry()

        flow = _make_flow_with_all(
            hass,
            e3dc_entries=[e3dc_entry],
            forecast_entries=[forecast_entry],
            uem_entry=uem_entry,
        )
        flow.context = {"entry_id": "uem-001"}

        # Step 1: Trigger reconfigure → get edit form
        result = _run(
            flow.async_step_reconfigure(
                {"rescan_e3dc": "False", "edit_manual": "True"}
            )
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure_edit"

        # Step 2: Submit the edit form (all 10 schema fields)
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
            })
        )

        # Verify: reconfigure_successful
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

        # Verify: Forecast.Solar entry ID was collected and saved
        saved_data = hass.config_entries.async_update_entry.call_args.kwargs["data"]
        assert CONF_FORECAST_SOLAR_ENTRY_IDS in saved_data, (
            "forecast_solar_entry_ids must be present in saved data"
        )
        assert "forecast-solar-new" in saved_data[CONF_FORECAST_SOLAR_ENTRY_IDS], (
            f"New Forecast.Solar entry ID 'forecast-solar-new' must be in "
            f"forecast_solar_entry_ids, got: {saved_data[CONF_FORECAST_SOLAR_ENTRY_IDS]}"
        )


# =========================================================================== #
# TEST 2: Multiple newly added Forecast.Solar entries                         #
# =========================================================================== #


class TestReconfigureMultipleForecastSolarEntries:
    """Reconfigure muss mehrere Forecast.Solar-Entries sammeln."""

    def test_reconfigure_collects_multiple_forecast_solar_entries(self) -> None:
        """Multiple Forecast.Solar entries added after UEM install must all be
        collected during reconfigure_edit."""
        hass = MagicMock()
        _mock_location(hass)

        uem_entry = _make_uem_entry(
            entry_id="uem-multi",
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
                CONF_FORECAST_SOLAR_ENTRY_IDS: ["forecast-solar-old"],  # Only old one
            },
        )

        # Two new Forecast.Solar entries
        forecast1 = _make_forecast_solar_entry(entry_id="forecast-solar-new1")
        forecast2 = _make_forecast_solar_entry(entry_id="forecast-solar-new2")
        e3dc_entry = _make_e3dc_entry()

        flow = _make_flow_with_all(
            hass,
            e3dc_entries=[e3dc_entry],
            forecast_entries=[forecast1, forecast2],
            uem_entry=uem_entry,
        )
        flow.context = {"entry_id": "uem-multi"}

        # Trigger reconfigure → submit edit
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
            })
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

        saved_data = hass.config_entries.async_update_entry.call_args.kwargs["data"]
        forecast_ids = saved_data.get(CONF_FORECAST_SOLAR_ENTRY_IDS, [])
        # The new entries should be collected; old entry (if still present in HA)
        # would also be there. The key point: new ones must appear.
        assert "forecast-solar-new1" in forecast_ids, (
            f"forecast-solar-new1 must be in {forecast_ids}"
        )
        assert "forecast-solar-new2" in forecast_ids, (
            f"forecast-solar-new2 must be in {forecast_ids}"
        )


# =========================================================================== #
# TEST 3: Reconfigure existing UEM with None-valued forecast_solar_entry_ids  #
# =========================================================================== #


class TestReconfigureForecastSolarNoneValue:
    """Reconfigure einer UEM-Instanz mit forecast_solar_entry_ids=None
    (älterer Eintrag) muss die vorhandenen Forecast.Solar-Entries sammeln."""

    def test_reconfigure_collects_forecast_solar_when_none(self) -> None:
        """When forecast_solar_entry_ids is None in the existing UEM entry,
        reconfigure_edit must collect the current Forecast.Solar entry IDs."""
        hass = MagicMock()
        _mock_location(hass)

        uem_entry = _make_uem_entry(
            entry_id="uem-001",
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
                CONF_FORECAST_SOLAR_ENTRY_IDS: None,  # None — older entry format
            },
        )

        forecast_entry = _make_forecast_solar_entry(entry_id="forecast-solar-new")
        e3dc_entry = _make_e3dc_entry()

        flow = _make_flow_with_all(
            hass,
            e3dc_entries=[e3dc_entry],
            forecast_entries=[forecast_entry],
            uem_entry=uem_entry,
        )
        flow.context = {"entry_id": "uem-001"}

        result = _run(
            flow.async_step_reconfigure(
                {"rescan_e3dc": "False", "edit_manual": "True"}
            )
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure_edit"

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
            })
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

        saved_data = hass.config_entries.async_update_entry.call_args.kwargs["data"]
        assert CONF_FORECAST_SOLAR_ENTRY_IDS in saved_data
        assert saved_data[CONF_FORECAST_SOLAR_ENTRY_IDS] is not None
        assert "forecast-solar-new" in saved_data[CONF_FORECAST_SOLAR_ENTRY_IDS], (
            f"forecast-solar-new must be in "
            f"{saved_data[CONF_FORECAST_SOLAR_ENTRY_IDS]}"
        )
