"""E3DC-RSCP grid-power mapping regressions."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_INVERT_GRID_POWER_SIGN,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
)
from custom_components.universal_energy_manager.coordinator import UemShadowCoordinator
from custom_components.universal_energy_manager.e3dc_rscp import (
    discover_e3dc_entities,
    source_by_key_from_unique_ids,
)


def test_e3dc_rscp_uses_signed_grid_netchange_sensor() -> None:
    """The upstream adapter's signed source is grid-netchange, not export-only."""
    sources = source_by_key_from_unique_ids(
        {
            "device_grid-netchange": "sensor.e3dc_grid_netchange",
            "device_grid-production": "sensor.e3dc_grid_export",
        }
    )
    result = discover_e3dc_entities(sources)

    assert result.grid_export == "sensor.e3dc_grid_netchange"


def test_e3dc_rscp_keeps_signed_grid_netchange_in_its_native_direction(hass) -> None:
    """E3DC import-positive/export-negative is also UEM's standard convention."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SOC_ENTITY: "sensor.soc",
            CONF_PV_POWER_ENTITY: "sensor.pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.house",
            CONF_GRID_EXPORT_ENTITY: "sensor.grid_netchange",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.battery",
            CONF_INVERT_GRID_POWER_SIGN: False,
        },
    )
    values = {
        "sensor.soc": ("50", "%"),
        "sensor.pv": ("1000", "W"),
        "sensor.house": ("1650", "W"),
        "sensor.grid_netchange": ("650", "W"),
        "sensor.battery": ("0", "W"),
    }
    for entity_id, (state, unit) in values.items():
        hass.states.async_set(entity_id, state, {"unit_of_measurement": unit})

    live = UemShadowCoordinator(hass, entry)._live_state()

    assert live.grid_export_w == 650
