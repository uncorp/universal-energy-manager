"""TDD for UEM Task B slice 4: Multi-battery storage capabilities.

Slice 4 (vertical slice): _build_storage_capabilities must sum usable
capacity (kWh) and max charge power (W) from the E3DC battery AND all
additional batteries configured via CONF_BATTERIES.

The existing E3DC battery is configured via CONF_BATTERY_CAPACITY_ENTITY,
CONF_BATTERY_MANUAL_CAPACITY_KWH, CONF_MAX_CHARGE_POWER_ENTITY, and
CONF_MAX_CHARGE_MANUAL_POWER_W.  Additional batteries contribute from
their battery_capacity_kwh field (a string, fixed kWh or entity-derived).

Each additional battery contributes its capacity.  Max charge power for
additional batteries is not yet configurable, so only capacity sums up.
The E3DC battery's max charge power is unchanged.

This slice verifies:
  1. Only E3DC battery → unchanged behavior.
  2. E3DC + one additional battery → capacity sums up.
  3. E3DC + two additional batteries → all capacities summed.
  4. Malformed batteries JSON → falls back to E3DC only (no crash).
  5. Empty batteries JSON → E3DC only (no crash).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from unittest.mock import MagicMock

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
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
)
from custom_components.universal_energy_manager.coordinator import (
    UemShadowCoordinator,
)
from custom_components.universal_energy_manager.models import StorageCapabilities

# --------------------------------------------------------------------------- #
# Helpers                                                                       #
# --------------------------------------------------------------------------- #


def _make_entry(
    batteries_json: str = "[]",
    extra_data: dict | None = None,
) -> MagicMock:
    """Build a MagicMock ConfigEntry with standard UEM fields."""
    data = {
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
        CONF_FORECAST_SOLAR_ENTRY_IDS: [],
        CONF_BATTERIES: batteries_json,
    }
    if extra_data:
        data.update(extra_data)
    entry = MagicMock()
    entry.data = data
    entry.unique_id = "uem:test"
    entry.entry_id = "uem-001"
    return entry


def _make_hass_with_entities(entity_map: dict) -> MagicMock:
    """Build a MagicMock HA with pre-configured entity states."""
    hass = MagicMock()
    states = {}
    for entity_id, state in entity_map.items():
        mock_state = MagicMock()
        mock_state.state = state.get("state", "unavailable")
        mock_state.attributes = state.get("attributes", {})
        mock_state.last_updated = datetime.now()
        mock_state.last_changed = datetime.now()
        states[entity_id] = mock_state
    hass.states.get = MagicMock(side_effect=lambda eid: states.get(eid))
    return hass


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


# =========================================================================== #
# TEST 1: Only E3DC battery → unchanged behavior                               #
# =========================================================================== #


class TestStorageCapabilitiesOnlyE3dc:
    """When no additional batteries are configured, only E3DC values are used."""

    def test_e3dc_only_capacity(self) -> None:
        """E3DC battery with entity capacity 10 kWh and manual capacity should
        both try entity first; entity wins with 10 kWh."""
        entry = _make_entry(batteries_json="[]")
        hass = _make_hass_with_entities({
            "sensor.e3dc_soc": {"state": "50"},
            "sensor.e3dc_pv": {"state": "3000"},
            "sensor.e3dc_house": {"state": "1500"},
            "sensor.e3dc_grid": {"state": "500"},
            "sensor.e3dc_charge": {"state": "2000"},
            "sensor.e3dc_capacity": {"state": "10"},
            "sensor.e3dc_max": {"state": "3000"},
        })
        coord = UemShadowCoordinator(hass, entry)
        storage = coord._build_storage_capabilities()
        assert isinstance(storage, StorageCapabilities)
        assert storage.usable_capacity_kwh == 10.0
        assert storage.max_charge_power_w == 3000.0

    def test_e3dc_only_manual_capacity(self) -> None:
        """When entity capacity is unavailable, manual kWh is used."""
        entry = _make_entry(
            batteries_json="[]",
            extra_data={
                CONF_BATTERY_CAPACITY_ENTITY: "",
                CONF_BATTERY_MANUAL_CAPACITY_KWH: "8",
            },
        )
        hass = _make_hass_with_entities({
            "sensor.e3dc_soc": {"state": "50"},
            "sensor.e3dc_pv": {"state": "3000"},
            "sensor.e3dc_house": {"state": "1500"},
            "sensor.e3dc_grid": {"state": "500"},
            "sensor.e3dc_charge": {"state": "2000"},
            "sensor.e3dc_capacity": {"state": "unavailable"},
            "sensor.e3dc_max": {"state": "3000"},
        })
        coord = UemShadowCoordinator(hass, entry)
        storage = coord._build_storage_capabilities()
        assert storage.usable_capacity_kwh == 8.0
        assert storage.max_charge_power_w == 3000.0


# =========================================================================== #
# TEST 2: E3DC + one additional battery → capacity sums up                     #
# =========================================================================== #


class TestStorageCapabilitiesE3dcPlusOne:
    """E3DC + one additional battery: usable capacity sums both."""

    def test_e3dc_plus_one_battery(self) -> None:
        """E3DC 10 kWh + Wall-Power 10 kWh = 20 kWh total."""
        battery = {
            CONF_BATTERY_NAME: "Wall-Power",
            CONF_BATTERY_SOC_ENTITY: "sensor.wallpower_soc",
            CONF_BATTERY_CAPACITY_KWH: "10",
            CONF_BATTERY_CHARGE_POWER_ENTITY: "sensor.wallpower_charge",
            CONF_BATTERY_DISCHARGE_POWER_ENTITY: "sensor.wallpower_discharge",
        }
        entry = _make_entry(
            batteries_json=json.dumps([battery], ensure_ascii=False),
        )
        hass = _make_hass_with_entities({
            "sensor.e3dc_soc": {"state": "50"},
            "sensor.e3dc_pv": {"state": "3000"},
            "sensor.e3dc_house": {"state": "1500"},
            "sensor.e3dc_grid": {"state": "500"},
            "sensor.e3dc_charge": {"state": "2000"},
            "sensor.e3dc_capacity": {"state": "10"},
            "sensor.e3dc_max": {"state": "3000"},
            "sensor.wallpower_soc": {"state": "75"},
            "sensor.wallpower_charge": {"state": "1500"},
            "sensor.wallpower_discharge": {"state": "-1500"},
        })
        coord = UemShadowCoordinator(hass, entry)
        storage = coord._build_storage_capabilities()
        assert storage.usable_capacity_kwh == 20.0  # 10 + 10
        assert storage.max_charge_power_w == 3000.0  # E3DC only


# =========================================================================== #
# TEST 3: E3DC + two additional batteries → all capacities summed             #
# =========================================================================== #


class TestStorageCapabilitiesE3dcPlusTwo:
    """E3DC + two additional batteries: all three capacities summed."""

    def test_e3dc_plus_two_batteries(self) -> None:
        """E3DC 10 + Wall-Power 10 + Solar-Battery 5 = 25 kWh total."""
        batteries = [
            {
                CONF_BATTERY_NAME: "Wall-Power",
                CONF_BATTERY_SOC_ENTITY: "sensor.wallpower_soc",
                CONF_BATTERY_CAPACITY_KWH: "10",
                CONF_BATTERY_CHARGE_POWER_ENTITY: "sensor.wallpower_charge",
                CONF_BATTERY_DISCHARGE_POWER_ENTITY: "sensor.wallpower_discharge",
            },
            {
                CONF_BATTERY_NAME: "Solar-Battery",
                CONF_BATTERY_SOC_ENTITY: "sensor.solar_battery_soc",
                CONF_BATTERY_CAPACITY_KWH: "5",
                CONF_BATTERY_CHARGE_POWER_ENTITY: "sensor.solar_battery_charge",
                CONF_BATTERY_DISCHARGE_POWER_ENTITY: "sensor.solar_battery_discharge",
            },
        ]
        entry = _make_entry(
            batteries_json=json.dumps(batteries, ensure_ascii=False),
        )
        hass = _make_hass_with_entities({
            "sensor.e3dc_soc": {"state": "50"},
            "sensor.e3dc_pv": {"state": "3000"},
            "sensor.e3dc_house": {"state": "1500"},
            "sensor.e3dc_grid": {"state": "500"},
            "sensor.e3dc_charge": {"state": "2000"},
            "sensor.e3dc_capacity": {"state": "10"},
            "sensor.e3dc_max": {"state": "3000"},
            "sensor.wallpower_soc": {"state": "75"},
            "sensor.wallpower_charge": {"state": "1500"},
            "sensor.wallpower_discharge": {"state": "-1500"},
            "sensor.solar_battery_soc": {"state": "30"},
            "sensor.solar_battery_charge": {"state": "1000"},
            "sensor.solar_battery_discharge": {"state": "-1000"},
        })
        coord = UemShadowCoordinator(hass, entry)
        storage = coord._build_storage_capabilities()
        assert storage.usable_capacity_kwh == 25.0  # 10 + 10 + 5
        assert storage.max_charge_power_w == 3000.0  # E3DC only


# =========================================================================== #
# TEST 4: Malformed batteries JSON → falls back to E3DC only (no crash)       #
# =========================================================================== #


class TestStorageCapabilitiesMalformedBatteries:
    """Malformed batteries JSON must not crash; E3DC values are used."""

    def test_malformed_batteries_fallback(self) -> None:
        """Malformed JSON is treated as empty list; E3DC values used."""
        entry = _make_entry(batteries_json="{invalid json")
        hass = _make_hass_with_entities({
            "sensor.e3dc_soc": {"state": "50"},
            "sensor.e3dc_pv": {"state": "3000"},
            "sensor.e3dc_house": {"state": "1500"},
            "sensor.e3dc_grid": {"state": "500"},
            "sensor.e3dc_charge": {"state": "2000"},
            "sensor.e3dc_capacity": {"state": "10"},
            "sensor.e3dc_max": {"state": "3000"},
        })
        coord = UemShadowCoordinator(hass, entry)
        storage = coord._build_storage_capabilities()
        assert storage.usable_capacity_kwh == 10.0
        assert storage.max_charge_power_w == 3000.0


# =========================================================================== #
# TEST 5: Empty batteries JSON → E3DC only (no crash)                          #
# =========================================================================== #


class TestStorageCapabilitiesEmptyBatteries:
    """Empty batteries JSON → only E3DC values are used."""

    def test_empty_batteries_fallback(self) -> None:
        """Empty batteries list → E3DC 10 kWh + 3000 W."""
        entry = _make_entry(batteries_json="[]")
        hass = _make_hass_with_entities({
            "sensor.e3dc_soc": {"state": "50"},
            "sensor.e3dc_pv": {"state": "3000"},
            "sensor.e3dc_house": {"state": "1500"},
            "sensor.e3dc_grid": {"state": "500"},
            "sensor.e3dc_charge": {"state": "2000"},
            "sensor.e3dc_capacity": {"state": "10"},
            "sensor.e3dc_max": {"state": "3000"},
        })
        coord = UemShadowCoordinator(hass, entry)
        storage = coord._build_storage_capabilities()
        assert storage.usable_capacity_kwh == 10.0
        assert storage.max_charge_power_w == 3000.0
