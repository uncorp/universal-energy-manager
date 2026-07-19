"""Tests for coordinator behavior with old persisted config entries (pre-forecast_solar)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from homeassistant import config_entries
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.util import dt as dt_util

from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_E3DC_CONFIG_ENTRY_ID,
    CONF_E3DC_SOURCE_UNIQUE_ID,
    CONF_FORECAST_SOLAR_ENTRY_IDS,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
)
from custom_components.universal_energy_manager.coordinator import ShadowData, UemShadowCoordinator


def _make_old_uem_entry() -> config_entries.ConfigEntry:
    """Simulate a UEM entry persisted before CONF_FORECAST_SOLAR_ENTRY_IDS was added."""
    return config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="UEM",
        data={
            CONF_E3DC_CONFIG_ENTRY_ID: "e3dc-001",
            CONF_E3DC_SOURCE_UNIQUE_ID: "S10E-12345",
            CONF_SOC_ENTITY: "sensor.e3dc_soc",
            CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
            CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
            CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
            CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
        },
        source="user",
        entry_id="uem-001",
        unique_id="e3dc_rscp:S10E-12345",
        state=config_entries.ConfigEntryState.LOADED,
    )


def _make_mock_hass(states: dict[str, object]) -> MagicMock:
    """Build a hass mock where hass.states.get() returns the given states."""
    hass = MagicMock()

    class MockState:
        def __init__(self, entity_id: str, state_val: str, unit: str | None = None):
            self.entity_id = entity_id
            self.state = state_val
            self.attributes = {}
            if unit:
                self.attributes[ATTR_UNIT_OF_MEASUREMENT] = unit
            self.last_updated = dt_util.utcnow()

        def __getattr__(self, name):
            if name == "entity_id":
                return self.entity_id
            if name == "state":
                return self.state
            if name == "attributes":
                return self.attributes
            if name == "last_updated":
                return self.last_updated
            raise AttributeError(name)

    state_map = {}
    for entity_id, val in states.items():
        if isinstance(val, tuple):
            state_map[entity_id] = MockState(entity_id, val[0], val[1])
        else:
            state_map[entity_id] = MockState(entity_id, val, "W")

    hass.states.get = MagicMock(side_effect=lambda eid: state_map.get(eid))
    return hass


class TestCoordinatorWithOldEntry:
    """Verify coordinator handles old-entry data (missing CONF_FORECAST_SOLAR_ENTRY_IDS)."""

    def test_old_entry_missing_forecast_key_does_not_crash(self) -> None:
        """An old entry without CONF_FORECAST_SOLAR_ENTRY_IDS must not crash the
        coordinator's first refresh. The key simply returns None and forecast is skipped."""
        entry = _make_old_uem_entry()
        assert CONF_FORECAST_SOLAR_ENTRY_IDS not in entry.data

        hass = _make_mock_hass({
            "sensor.e3dc_soc": ("45", "%"),
            "sensor.e3dc_pv": ("3200", "W"),
            "sensor.e3dc_house": ("2100", "W"),
            "sensor.e3dc_grid": ("1100", "W"),
            "sensor.e3dc_charge": ("1800", "W"),
        })

        coordinator = UemShadowCoordinator(hass, entry)

        # First refresh — must not raise
        asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            coordinator.async_config_entry_first_refresh()
        )

        # Should succeed with valid data, forecast_connected=False
        assert coordinator.data is not None
        assert isinstance(coordinator.data, ShadowData)
        assert coordinator.data.error is None
        assert coordinator.data.forecast_connected is False
        assert coordinator.data.status != "Shadow – Messdatenfehler"

    def test_old_entry_forecast_fallback_chain(self) -> None:
        """When CONF_FORECAST_SOLAR_ENTRY_IDS is absent, coordinator falls back to
        CONF_FORECAST_ENTITY (also absent) → returns False. No exception raised."""
        entry = _make_old_uem_entry()

        hass = _make_mock_hass({
            "sensor.e3dc_soc": ("45", "%"),
            "sensor.e3dc_pv": ("3200", "W"),
            "sensor.e3dc_house": ("2100", "W"),
            "sensor.e3dc_grid": ("1100", "W"),
            "sensor.e3dc_charge": ("1800", "W"),
        })

        coordinator = UemShadowCoordinator(hass, entry)
        asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            coordinator.async_config_entry_first_refresh()
        )

        # forecast_connected must be False (not an error, just unavailable)
        assert coordinator.data is not None
        assert coordinator.data.forecast_connected is False

    def test_old_entry_all_required_entities_present(self) -> None:
        """Old entries must have all required entity keys for coordinator _sample() to work."""
        entry = _make_old_uem_entry()

        required_keys = [
            CONF_SOC_ENTITY,
            CONF_PV_POWER_ENTITY,
            CONF_HOUSE_POWER_ENTITY,
            CONF_GRID_EXPORT_ENTITY,
            CONF_BATTERY_CHARGE_ENTITY,
        ]
        for key in required_keys:
            assert key in entry.data, f"Old entry is missing required key: {key}"
            assert isinstance(entry.data[key], str), f"Old entry key {key} is not a string"
