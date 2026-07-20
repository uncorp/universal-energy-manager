"""Shadow coordinator with zero PV power.

When live PV power is zero, the coordinator's _build_forecast_from_snapshot
must return an empty forecast. plan_charge with an empty forecast should
return zero charge limit (no current forecast interval).

This is purely Shadow-only: no HA entity writes, no service calls, no credentials.
"""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
)
from custom_components.universal_energy_manager.coordinator import UemShadowCoordinator


@pytest.mark.asyncio
async def test_coordinator_returns_zero_limit_when_pv_power_is_zero(hass) -> None:
    """When PV power is 0 W, the coordinator must return a zero planned charge limit."""
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

    for entity_id, state, unit in (
        ("sensor.e3dc_soc", "50", "%"),
        ("sensor.e3dc_pv", "0", "W"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1400", "W"),
        ("sensor.e3dc_battery_charge", "0", "W"),
        ("sensor.e3dc_capacity", "13.0", "kWh"),
        ("sensor.e3dc_max_charge", "12000", "W"),
    ):
        hass.states.async_set(entity_id, state, {"unit_of_measurement": unit})

    coordinator = UemShadowCoordinator(hass, entry)
    await coordinator.async_refresh()

    assert coordinator.data.error is None
    assert coordinator.data.commands_sent is False
    assert coordinator.data.planned_charge_limit_w == 0.0
    assert coordinator.data.forecast_connected is False


@pytest.mark.asyncio
async def test_coordinator_rejects_negative_pv_power_entity(hass) -> None:
    """When PV power entity reports an invalid (negative) value,
    the snapshot builder rejects it and the coordinator returns an error."""
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

    for entity_id, state, unit in (
        ("sensor.e3dc_soc", "50", "%"),
        ("sensor.e3dc_pv", "-100", "W"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1400", "W"),
        ("sensor.e3dc_battery_charge", "0", "W"),
        ("sensor.e3dc_capacity", "13.0", "kWh"),
        ("sensor.e3dc_max_charge", "12000", "W"),
    ):
        hass.states.async_set(entity_id, state, {"unit_of_measurement": unit})

    coordinator = UemShadowCoordinator(hass, entry)
    await coordinator.async_refresh()

    assert coordinator.data.error is not None
    assert coordinator.data.planned_charge_limit_w == 0.0
    assert coordinator.data.commands_sent is False
