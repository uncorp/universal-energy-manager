"""Tests for MVP-Akzeptanzfall 5: stale/old data handling."""

from datetime import UTC, datetime, timedelta

import pytest
from homeassistant.core import State
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
from custom_components.universal_energy_manager.coordinator import (
    UemShadowCoordinator,
)


def _make_stale_state(entity_id: str, state_value: str,
                      unit: str | None = None) -> State:
    """Create a State object with a timestamp older than 15 minutes."""
    stale_time = datetime.now(UTC) - timedelta(minutes=30)
    attrs = {}
    if unit is not None:
        attrs["unit_of_measurement"] = unit
    return State(entity_id, state_value, attrs,
                 stale_time, stale_time, "test")


@pytest.mark.asyncio
async def test_shadow_coordinator_rejects_stale_measurements(
    hass,
) -> None:
    """UEM reports a clear error when all live states > 15 min old."""
    entity_by_config_key = {
        CONF_SOC_ENTITY: "sensor.e3dc_soc",
        CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
        CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
        CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid_export",
        CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery_charge",
        CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
        CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=entity_by_config_key)

    # Write stale State objects (last_updated > 15 min ago).
    # Directly inject because async_set() overwrites last_updated.
    ids = list(entity_by_config_key.values())
    hass.states._states[ids[0]] = _make_stale_state(ids[0], "55", "%")
    hass.states._states[ids[1]] = _make_stale_state(ids[1], "3.2", "kW")
    hass.states._states[ids[2]] = _make_stale_state(ids[2], "1000", "W")
    hass.states._states[ids[3]] = _make_stale_state(ids[3], "1000", "W")
    hass.states._states[ids[4]] = _make_stale_state(ids[4], "1000", "W")
    hass.states._states[ids[5]] = _make_stale_state(ids[5], "55", "%")
    hass.states._states[ids[6]] = _make_stale_state(ids[6], "12000", "W")

    coordinator = UemShadowCoordinator(hass, entry)
    await coordinator.async_refresh()

    assert coordinator.data.error is not None
    assert coordinator.data.status != "Shadow - keine aktive Steuerung"
    assert coordinator.data.commands_sent is False
    # MVP-Akzeptanzfall 5: error message mentions stale data
    err = coordinator.data.error.lower()
    assert "stale" in err or "alt" in err or "updated_at" in err


@pytest.mark.asyncio
async def test_shadow_coordinator_rejects_unavailable_input(
    hass,
) -> None:
    """UEM reports an error when a source entity is unavailable."""
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

    soc_unavail = {"sensor.e3dc_soc"}
    for eid in ("sensor.e3dc_soc", "sensor.e3dc_pv",
                "sensor.e3dc_house", "sensor.e3dc_grid_export",
                "sensor.e3dc_battery_charge", "sensor.e3dc_capacity",
                "sensor.e3dc_max_charge"):
        if eid in soc_unavail:
            hass.states.async_set(eid, "unavailable")
        else:
            is_pct = "soc" in eid or "capacity" in eid
            hass.states.async_set(
                eid,
                "55" if is_pct else "3.2",
                {"unit_of_measurement": "%" if is_pct else "kW"},
            )

    coordinator = UemShadowCoordinator(hass, entry)
    await coordinator.async_refresh()

    assert coordinator.data.error is not None
    err = coordinator.data.error.lower()
    assert "unavailable" in err or "missing" in err
    assert coordinator.data.commands_sent is False
