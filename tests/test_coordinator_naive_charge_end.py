"""Tests for coordinator handling of naive (tzinfo-less) charge_end.

Closes the uncovered branch on coordinator.py _resolve_charge_end:
    if charge_end.tzinfo is None:
        charge_end = charge_end.replace(tzinfo=live.now.tzinfo)

This path is taken when the stored CONF_CHARGE_END is a naive ISO string
that parses to a timezone-naive datetime.
"""

from __future__ import annotations

import pytest
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_CHARGE_END,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
)
from custom_components.universal_energy_manager.coordinator import UemShadowCoordinator


@pytest.mark.asyncio
async def test_naive_charge_end_exercises_coordinator_line_200(hass) -> None:
    """A naive (no tz) charge_end ISO string must reach line 200 and get tzinfo attached."""
    # This naive string has no timezone info
    naive_charge_end = "2026-07-18T18:00:00"

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SOC_ENTITY: "sensor.e3dc_soc",
            CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
            CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
            CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
            CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
            CONF_CHARGE_END: naive_charge_end,  # naive ISO string
        },
    )

    values = {
        "sensor.e3dc_soc": ("55", "%"),
        "sensor.e3dc_pv": ("3.2", "kW"),
        "sensor.e3dc_house": ("800", "W"),
        "sensor.e3dc_grid": ("1.4", "kW"),
        "sensor.e3dc_charge": ("1.8", "kW"),
        "sensor.e3dc_capacity": ("13.0", "kWh"),
        "sensor.e3dc_max_charge": ("12000", "W"),
    }
    for entity_id, (state, unit) in values.items():
        hass.states.async_set(entity_id, state, {ATTR_UNIT_OF_MEASUREMENT: unit})

    coordinator = UemShadowCoordinator(hass, entry)
    await coordinator.async_refresh()

    # The charge_end must have been given tzinfo (_resolve_charge_end)
    assert coordinator.data.error is None
    # If charge_end is naive, _resolve_charge_end attaches tzinfo and planning proceeds
    assert coordinator.data.planned_charge_limit_w >= 0.0
