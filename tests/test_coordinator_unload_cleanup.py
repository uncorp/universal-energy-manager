"""Ensure coordinator registers async_shutdown for cleanup on entry unload.

The DataUpdateCoordinator base class has an async_shutdown() method that
cancels scheduled refreshes.  The coordinator must register this method
with its ConfigEntry via async_on_unload, otherwise the debounced-refresh
scheduler continues to run after the integration is unloaded.
"""

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.universal_energy_manager import (
    async_setup_entry,
    async_unload_entry,
)
from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
)


@pytest.mark.asyncio
async def test_async_unload_entry_cleans_up_coordinator_refresh_scheduler(
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """When the integration is unloaded, the coordinator's _entry must
    have registered its async_shutdown method via async_on_unload so that
    HA calls it automatically during entry removal."""

    entity_data = {
        CONF_SOC_ENTITY: "sensor.e3dc_soc",
        CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
        CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
        CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid_export",
        CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery_charge",
    }

    entry = MockConfigEntry(domain=DOMAIN, data=entity_data)
    entry.add_to_hass(hass)

    for eid, val, unit in (
        ("sensor.e3dc_soc", "55", "%"),
        ("sensor.e3dc_pv", "3.2", "kW"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1.4", "kW"),
        ("sensor.e3dc_battery_charge", "1.8", "kW"),
    ):
        hass.states.async_set(eid, val, {"unit_of_measurement": unit})

    setup_ok = await async_setup_entry(hass, entry)
    assert setup_ok is True

    coordinator = hass.data[DOMAIN][entry.entry_id]

    # The coordinator must have a _debounced_refresh.
    assert hasattr(coordinator, "_debounced_refresh")
    # Before unload, shutdown must NOT be requested.
    assert coordinator._debounced_refresh._shutdown_requested is False

    # Now unload the entry.  Call async_unload_entry directly, then
    # manually invoke the registered on_unload callbacks (this mirrors
    # what HA's ConfigEntry.async_unload does via
    # _async_process_on_unload).
    unload_ok = await async_unload_entry(hass, entry)
    assert unload_ok is True

    # The entry must be removed from hass.data.
    assert entry.entry_id not in hass.data.get(DOMAIN, {})

    # Trigger the on_unload callbacks (async_on_unload registered
    # coordinator.async_shutdown via entry.async_on_unload).
    if hasattr(entry, "_on_unload") and entry._on_unload:
        while entry._on_unload:
            cb = entry._on_unload.pop()
            result = cb()
            if result is not None:
                await result

    # After the on_unload callbacks fire, the coordinator's
    # _debounced_refresh must have _shutdown_requested=True.
    assert coordinator._debounced_refresh._shutdown_requested is True, (
        "coordinator._debounced_refresh was not shut down on unload"
    )
