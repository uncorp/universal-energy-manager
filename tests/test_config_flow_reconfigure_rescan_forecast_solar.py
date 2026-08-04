"""TDD red test: Reconfigure with `rescan_e3dc=True` must also collect
Forecast.Solar entry IDs.

Bug-Befund:
- async_step_reconfigure_edit (edit_manual=True) re-collectet FS-IDs korrekt
  (Zeile 512-515 im config_flow.py).
- async_step_reconfigure mit `rescan_e3dc=True` (und e3dc_entry_id gesetzt)
  ruft _rescan_e3dc auf, das KEINE Forecast.Solar-IDs aktualisiert.
- Daher bleibt forecast_solar_entry_ids veraltet, wenn FS später eingerichtet
  wird und der User "Rescan e3dc" wählt.

Dieser Test ist ein **roter** Test — er reproduziert den Bug und fällt durch,
solange der Fix nicht implementiert ist.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.universal_energy_manager.config_flow import UemConfigFlow
from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_MANUAL_CAPACITY_KWH,
    CONF_E3DC_CONFIG_ENTRY_ID,
    CONF_E3DC_SOURCE_UNIQUE_ID,
    CONF_FORECAST_SOLAR_ENTRY_IDS,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MANUAL_ENTITIES,
    CONF_MAX_CHARGE_MANUAL_POWER_W,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
    E3DC_RSCP_DOMAIN,
    FORECAST_SOLAR_DOMAIN,
)

# --------------------------------------------------------------------------- #
# Helpers                                                                       #
# --------------------------------------------------------------------------- #


def _make_e3dc_entry(
    entry_id: str = "e3dc-001",
    unique_id: str = "S10E-12345",
) -> config_entries.ConfigEntry:
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=E3DC_RSCP_DOMAIN,
        title="E3DC RSCP",
        data={},
        source="user",
        entry_id=entry_id,
        unique_id=unique_id,
        state=config_entries.ConfigEntryState.LOADED,
    )


def _make_forecast_solar_entry(
    entry_id: str = "forecast-solar-new",
) -> config_entries.ConfigEntry:
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=FORECAST_SOLAR_DOMAIN,
        title="Forecast.Solar",
        data={},
        source="user",
        entry_id=entry_id,
        unique_id="forecast-solar:test",
        state=config_entries.ConfigEntryState.LOADED,
    )


def _make_uem_entry_with_empty_fs(
    entry_id: str = "uem-001",
    data: dict | None = None,
) -> config_entries.ConfigEntry:
    """UEM entry created BEFORE any Forecast.Solar was configured."""
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="UEM – Universal Energy Manager",
        data=data or {},
        source="user",
        entry_id=entry_id,
        unique_id="e3dc_rscp:HW-12345",
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


# =========================================================================== #
# TEST 1: rescan_e3dc=True must collect new Forecast.Solar entry IDs         #
# =========================================================================== #


class TestRescanE3dcCollectsForecastSolarEntryIds:
    """Reconfigure mit rescan_e3dc=True und bestehender E3DC-PV muss
    vorhandene Forecast.Solar-Entry-IDs in forecast_solar_entry_ids übernehmen,
    auch wenn sie beim UEM-Install noch nicht existierten."""

    def test_rescan_e3dc_updates_forecast_solar_entry_ids(self) -> None:
        """When rescan_e3dc=True and an existing Forecast.Solar entry exists
        that was NOT present at UEM install time, the rescan path must include
        its entry ID in the saved data."""
        hass = MagicMock()

        # Existing UEM entry: forecast_solar_entry_ids was empty at install
        uem_entry = _make_uem_entry_with_empty_fs(
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
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "10.0",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "5000",
                CONF_MANUAL_ENTITIES: False,
                CONF_FORECAST_SOLAR_ENTRY_IDS: [],  # Empty — bug scenario
            },
        )

        # Forecast.Solar entry added AFTER UEM install
        forecast_entry = _make_forecast_solar_entry(entry_id="forecast-solar-new")

        e3dc_entry = _make_e3dc_entry()

        flow = _make_flow_with_all(
            hass,
            e3dc_entries=[e3dc_entry],
            forecast_entries=[forecast_entry],
            uem_entry=uem_entry,
        )
        flow.context = {"entry_id": "uem-001"}

        # Trigger reconfigure with rescan_e3dc=True (existing path with e3dc_entry_id)
        result = _run(
            flow.async_step_reconfigure(
                {"rescan_e3dc": "True", "edit_manual": "False"}
            )
        )

        # The rescan path creates a new entry directly
        assert result["type"] == FlowResultType.CREATE_ENTRY

        saved_data = result["data"]

        # The key assertion: Forecast.Solar entry ID must be collected
        assert CONF_FORECAST_SOLAR_ENTRY_IDS in saved_data, (
            f"forecast_solar_entry_ids must be present in saved data, "
            f"got keys: {list(saved_data.keys())}"
        )
        assert "forecast-solar-new" in saved_data[CONF_FORECAST_SOLAR_ENTRY_IDS], (
            f"New Forecast.Solar entry ID 'forecast-solar-new' must be in "
            f"forecast_solar_entry_ids, got: {saved_data[CONF_FORECAST_SOLAR_ENTRY_IDS]}"
        )


# =========================================================================== #
# TEST 3: reconfigure with None-valued forecast_solar_entry_ids               #
# =========================================================================== #


class TestRescanE3dcWithNoneForecastSolarEntryIds:
    """Reconfigure with rescan_e3dc=True when the UEM entry stores
    ``None`` (not just ``[]``) for ``forecast_solar_entry_ids`` must
    still collect currently existing Forecast.Solar entry IDs."""

    def test_rescan_e3dc_updates_none_forecast_solar_entry_ids(self) -> None:
        """When the UEM entry has forecast_solar_entry_ids=None (older entry
        format), rescan_e3dc=True must replace None with the current list
        of Forecast.Solar entry IDs."""
        hass = MagicMock()

        uem_entry = _make_uem_entry_with_empty_fs(
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
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "10.0",
                CONF_MAX_CHARGE_MANUAL_POWER_W: "5000",
                CONF_MANUAL_ENTITIES: False,
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
                {"rescan_e3dc": "True", "edit_manual": "False"}
            )
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        saved_data = result["data"]

        assert CONF_FORECAST_SOLAR_ENTRY_IDS in saved_data
        assert saved_data[CONF_FORECAST_SOLAR_ENTRY_IDS] is not None
        assert "forecast-solar-new" in saved_data[CONF_FORECAST_SOLAR_ENTRY_IDS], (
            f"forecast-solar-new must be in "
            f"{saved_data[CONF_FORECAST_SOLAR_ENTRY_IDS]}"
        )
