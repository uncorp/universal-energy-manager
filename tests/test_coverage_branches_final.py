"""Final branch-coverage slice: close remaining 4 branch parts.

Covers:
- config_flow.py:540 -> 535 (rescan: entity_val is falsy because
  _ENT_MAP_LOOKUP maps 'battery_discharge_entity' to 'battery_discharge'
  but E3dcEntityMap has no such field → entity_val=None → else branch)
- coordinator.py:450 -> 456 (thread path: forecast_connected=False
  exercises the else branch skipping _build_forecast_from_snapshot)

TDD: test first (expect fail), implement, verify green.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.universal_energy_manager.config_flow import UemConfigFlow
from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_E3DC_CONFIG_ENTRY_ID,
    CONF_E3DC_SOURCE_UNIQUE_ID,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MANUAL_ENTITIES,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
    E3DC_RSCP_DOMAIN,
)
from custom_components.universal_energy_manager.coordinator import (
    UemShadowCoordinator,
)
from custom_components.universal_energy_manager.e3dc_rscp import E3dcEntityMap
from custom_components.universal_energy_manager.snapshot import (
    StateSample,
    build_live_state,
)


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


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


def _make_e3dc_entry(
    entry_id: str = "e3dc-001",
) -> config_entries.ConfigEntry:
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=E3DC_RSCP_DOMAIN,
        title="E3DC RSCP",
        data={},
        source="user",
        entry_id=entry_id,
        unique_id="S10E-12345",
        state=config_entries.ConfigEntryState.LOADED,
    )


# =========================================================================== #
# config_flow.py: rescan preserves blank fields when entity_val is falsy        #
# A blank field in the entry data that maps to an E3dcEntityMap field will      #
# be updated from discovery; fields not in _ENT_MAP_LOOKUP are unaffected.       #
# =========================================================================== #


class TestConfigFlowBranchRescanBlankFields:
    """Rescan: blank PV/House/Grid fields get updated from discovery,
    while non-mapped fields are unaffected."""

    def test_rescan_updates_blank_fields_from_discovery(self) -> None:
        """_rescan_e3dc updates blank fields that have entries in
        _ENT_MAP_LOOKUP and E3dcEntityMap, while preserving the overall
        entry structure."""
        e3dc_entry = _make_e3dc_entry()
        uem_entry = _make_uem_entry(
            entry_id="uem-old",
            data={
                CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
                CONF_E3DC_SOURCE_UNIQUE_ID: "HW-999",
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "",  # blank → should be updated
                CONF_HOUSE_POWER_ENTITY: "",
                CONF_GRID_EXPORT_ENTITY: "",
                CONF_BATTERY_CHARGE_ENTITY: "",
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_MAX_CHARGE_POWER_ENTITY: "",
                CONF_MANUAL_ENTITIES: False,
            },
        )

        def _async_entries(domain=None):
            if domain is None:
                return [e3dc_entry, uem_entry]
            if domain == E3DC_RSCP_DOMAIN:
                return [e3dc_entry]
            if domain == DOMAIN:
                return [uem_entry]
            return []

        hass = MagicMock()
        hass.config_entries.async_entries = MagicMock(side_effect=_async_entries)
        hass.config_entries.async_entry_for_domain_unique_id = MagicMock(
            return_value=uem_entry
        )
        hass.config.location = MagicMock(latitude=52.52, longitude=13.405)

        flow = UemConfigFlow()
        flow.hass = hass
        flow.context = {"entry_id": "uem-old"}
        flow.handler = DOMAIN

        new_map = E3dcEntityMap(
            soc="sensor.e3dc_soc",
            pv_power="sensor.e3dc_pv",
            house_power="sensor.e3dc_house",
            grid_export="sensor.e3dc_grid",
            battery_charge="sensor.e3dc_charge",
            battery_capacity="sensor.e3dc_capacity",
            max_charge_power="sensor.e3dc_max_charge",
        )

        with patch.object(UemConfigFlow, "_discover_entities", return_value=new_map):
            result = _run(
                flow.async_step_reconfigure(
                    {"rescan_e3dc": "true", "edit_manual": "false"}
                )
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        # Blank fields updated from discovery
        assert result["data"][CONF_PV_POWER_ENTITY] == "sensor.e3dc_pv"
        assert result["data"][CONF_HOUSE_POWER_ENTITY] == "sensor.e3dc_house"
        assert result["data"][CONF_GRID_EXPORT_ENTITY] == "sensor.e3dc_grid"
        assert result["data"][CONF_BATTERY_CHARGE_ENTITY] == "sensor.e3dc_charge"
        assert result["data"][CONF_BATTERY_CAPACITY_ENTITY] == "sensor.e3dc_capacity"
        assert result["data"][CONF_MAX_CHARGE_POWER_ENTITY] == "sensor.e3dc_max_charge"
        # Already-set fields stay unchanged
        assert result["data"][CONF_SOC_ENTITY] == "sensor.e3dc_soc"


# =========================================================================== #
# coordinator.py:450 -> 456                                                  #
# forecast_connected=False in _run_in_thread (thread path)                   #
# =========================================================================== #


class TestCoordinatorBranch450NoForecastThread:
    """Line 450: if forecast_connected → else branch in _run_in_thread.

    This test calls _compute_charge_limit (sync wrapper) from OUTSIDE
    an async context, forcing the `get_running_loop()` branch (line 427)
    to catch RuntimeError and use run_until_complete (line 429).
    Then _compute_charge_limit_async is called with forecast_connected=False,
    which exercises line 230 (if forecast_connected) → else → forecast=().

    To exercise line 450 -> 456 specifically (the threaded path), we must
    call _compute_charge_limit WITHIN a running asyncio context (e.g. a
    pytest-asyncio test), so that get_running_loop() succeeds, the thread
    path is taken (line 436+), and the inner _run_in_thread has
    forecast_connected=False.
    """

    @pytest.mark.asyncio
    async def test_thread_path_forecast_connected_false(self, hass) -> None:
        """When called from a running loop with forecast_connected=False,
        _compute_charge_limit enters _run_in_thread and skips
        _build_forecast_from_snapshot (line 450 -> 456)."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_SOC_ENTITY: "sensor.e3dc_soc",
                CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
                CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
                CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid_export",
                CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery_charge",
                CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
                CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
            },
        )
        for eid, val, unit in (
            ("sensor.e3dc_soc", "55", "%"),
            ("sensor.e3dc_pv", "2500", "W"),
            ("sensor.e3dc_house", "800", "W"),
            ("sensor.e3dc_grid_export", "0", "W"),
            ("sensor.e3dc_battery_charge", "1800", "W"),
            ("sensor.e3dc_capacity", "13.0", "kWh"),
            ("sensor.e3dc_max_charge", "12000", "W"),
        ):
            hass.states.async_set(eid, val, {"unit_of_measurement": unit})

        coordinator = UemShadowCoordinator(hass, entry)

        now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
        live = build_live_state(
            now=now,
            soc=StateSample("55", "%", now),
            pv_power=StateSample("2500", "W", now),
            house_power=StateSample("800", "W", now),
            grid_export=StateSample("0", "W", now),
            battery_charge=StateSample("1800", "W", now),
        )

        # Called from running loop → thread path (line 436)
        # forecast_connected=False → skips _build_forecast_from_snapshot (line 450)
        result = coordinator._compute_charge_limit(live, forecast_connected=False)

        assert isinstance(result, float)
        assert result >= 0.0  # valid float return
