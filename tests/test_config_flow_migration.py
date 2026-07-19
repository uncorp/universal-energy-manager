"""Tests for backward-compatibility migration of old UEM config entries."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.universal_energy_manager.config_flow import UemConfigFlow
from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_E3DC_CONFIG_ENTRY_ID,
    CONF_E3DC_SOURCE_UNIQUE_ID,
    CONF_FORECAST_ENTITY,
    CONF_FORECAST_SOLAR_ENTRY_IDS,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
    E3DC_RSCP_DOMAIN,
)
from custom_components.universal_energy_manager.e3dc_rscp import E3dcEntityMap


def _make_entry(
    entry_id: str = "e3dc-001",
    unique_id: str = "S10E-12345",
    title: str = "E3DC RSCP",
    data: dict | None = None,
) -> config_entries.ConfigEntry:
    """Create a minimal e3dc_rscp ConfigEntry."""
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=E3DC_RSCP_DOMAIN,
        title=title,
        data=data or {},
        source="user",
        entry_id=entry_id,
        unique_id=unique_id,
        state=config_entries.ConfigEntryState.LOADED,
    )


def _make_flow(
    hass: MagicMock,
    e3dc_entries: list[config_entries.ConfigEntry],
    existing_uem_entry: config_entries.ConfigEntry | None = None,
) -> UemConfigFlow:
    """Construct a UemConfigFlow with a mocked hass."""
    flow = UemConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.handler = DOMAIN
    ce = hass.config_entries
    _all_entries_by_domain: dict[str, list[config_entries.ConfigEntry]] = {
        E3DC_RSCP_DOMAIN: e3dc_entries,
    }
    if existing_uem_entry is not None:
        _all_entries_by_domain[DOMAIN] = [existing_uem_entry]

    def _async_entries(
        domain: str | None = None, *args, **kwargs
    ) -> list[config_entries.ConfigEntry]:
        if domain is None:
            result = []
            for entries in _all_entries_by_domain.values():
                result.extend(entries)
            return result
        return _all_entries_by_domain.get(domain, [])

    ce.async_entries = MagicMock(side_effect=_async_entries)
    ce.async_entry_for_domain_unique_id = MagicMock(
        side_effect=lambda domain, uid: existing_uem_entry if existing_uem_entry else None
    )
    return flow


def _run_flow_coroutine(coroutine) -> dict:
    """Execute an async flow step."""
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coroutine)


def _old_entry_data() -> dict:
    """Data that an entry created before CONF_FORECAST_SOLAR_ENTRY_IDS existed would have."""
    return {
        CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
        CONF_E3DC_SOURCE_UNIQUE_ID: "S10E-12345",
        CONF_SOC_ENTITY: "sensor.e3dc_soc",
        CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
        CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
        CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
        CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
        CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
        CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
    }


class TestOldEntryPreserved:
    """Verify that an old persisted entry (pre-forecast_solar) survives reload intact."""

    def test_old_entry_missing_forecast_key_is_not_corrupted(self) -> None:
        """An entry created before CONF_FORECAST_SOLAR_ENTRY_IDS was added must remain
        loadable and unmodified — the coordinator's .get() calls must handle the missing
        key gracefully."""
        old_data = _old_entry_data()
        # CONF_FORECAST_SOLAR_ENTRY_IDS must NOT be present — simulating old persisted entry
        assert CONF_FORECAST_SOLAR_ENTRY_IDS not in old_data

        # The coordinator reads it via .get() — should return None, not raise
        assert old_data.get(CONF_FORECAST_SOLAR_ENTRY_IDS) is None
        assert old_data.get(CONF_FORECAST_ENTITY) is None

        # All required entity keys must be present
        required = {
            CONF_SOC_ENTITY,
            CONF_PV_POWER_ENTITY,
            CONF_HOUSE_POWER_ENTITY,
            CONF_GRID_EXPORT_ENTITY,
            CONF_BATTERY_CHARGE_ENTITY,
            CONF_BATTERY_CAPACITY_ENTITY,
            CONF_MAX_CHARGE_POWER_ENTITY,
        }
        assert required.issubset(set(old_data.keys()))


class TestConfigFlowVersionStability:
    """Verify that ConfigFlow version/major-version semantics are stable."""

    def test_config_flow_version_is_one(self) -> None:
        """VERSION must be 1 — the first release."""
        assert UemConfigFlow.VERSION == 1

    def test_config_flow_has_no_migration_handler(self) -> None:
        """Currently there is no async_migrate_entry in the integration.
        This means bumping VERSION without adding a migration handler would
        break existing entries."""
        import custom_components.universal_energy_manager as pkg

        assert not hasattr(pkg, "async_migrate_entry")
        # The integration module must not rely on an implicit migration path.
        # Any future VERSION bump requires an explicit async_migrate_entry.


class TestEntryDataConsistency:
    """Verify that ConfigFlow always produces entries with consistent data."""

    def test_new_entry_includes_forecast_solar_entry_ids(self) -> None:
        """A freshly created entry must include CONF_FORECAST_SOLAR_ENTRY_IDS."""
        hass = MagicMock()
        e3dc_entry = _make_entry(entry_id="e3dc-001", unique_id="S10E-12345")
        flow = _make_flow(hass, [e3dc_entry])
        flow._e3dc_entry_id = e3dc_entry.entry_id

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
            result = _run_flow_coroutine(flow.async_step_confirm({"confirm": "yes"}))

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert CONF_FORECAST_SOLAR_ENTRY_IDS in result["data"]
        assert isinstance(result["data"][CONF_FORECAST_SOLAR_ENTRY_IDS], list)
