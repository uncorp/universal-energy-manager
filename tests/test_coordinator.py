from datetime import UTC, datetime, timedelta

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_FORECAST_SOLAR_ENTRY_IDS,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
)
from custom_components.universal_energy_manager.coordinator import (
    SHADOW_STATUS,
    UemShadowCoordinator,
)
from custom_components.universal_energy_manager.models import ForecastPoint


@pytest.mark.asyncio
async def test_shadow_coordinator_reads_live_states_without_control_calls(hass) -> None:
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
    values = {
        "sensor.e3dc_soc": ("55", "%"),
        "sensor.e3dc_pv": ("3.2", "kW"),
        "sensor.e3dc_house": ("800", "W"),
        "sensor.e3dc_grid_export": ("1.4", "kW"),
        "sensor.e3dc_battery_charge": ("1.8", "kW"),
        "sensor.e3dc_capacity": ("13.0", "kWh"),
        "sensor.e3dc_max_charge": ("12000", "W"),
    }
    for entity_id, (state, unit) in values.items():
        hass.states.async_set(entity_id, state, {"unit_of_measurement": unit})

    coordinator = UemShadowCoordinator(hass, entry)
    await coordinator.async_refresh()

    assert coordinator.data.status == SHADOW_STATUS
    assert coordinator.data.commands_sent is False
    assert coordinator.data.error is None
    assert "Akku 55 %" in coordinator.data.decision


@pytest.mark.asyncio
async def test_shadow_coordinator_shows_safe_error_for_unavailable_input(hass) -> None:
    """With complete config but unavailable entity → Messdatenfehler."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SOC_ENTITY: "sensor.e3dc_soc",
            CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery_charge",
            CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
            CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
        },
    )
    for sid in (
        "sensor.e3dc_soc",
        "sensor.e3dc_pv",
        "sensor.e3dc_house",
        "sensor.e3dc_battery_charge",
        "sensor.e3dc_capacity",
        "sensor.e3dc_max_charge",
    ):
        hass.states.async_set(sid, "unavailable")

    coordinator = UemShadowCoordinator(hass, entry)
    await coordinator.async_refresh()

    assert coordinator.data.status == "Shadow – Messdatenfehler"
    assert coordinator.data.commands_sent is False
    assert coordinator.data.error is not None


@pytest.mark.asyncio
async def test_shadow_coordinator_reads_cached_forecast_without_sending_command(
    hass, monkeypatch
) -> None:
    data = {
        CONF_SOC_ENTITY: "sensor.e3dc_soc",
        CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
        CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
        CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid_export",
        CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery_charge",
        CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
        CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
        CONF_FORECAST_SOLAR_ENTRY_IDS: ["roof"],
    }
    for entity_id, state, unit in (
        ("sensor.e3dc_soc", "55", "%"),
        ("sensor.e3dc_pv", "3.2", "kW"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1.4", "kW"),
        ("sensor.e3dc_battery_charge", "1.8", "kW"),
        ("sensor.e3dc_capacity", "13.0", "kWh"),
        ("sensor.e3dc_max_charge", "12000", "W"),
    ):
        hass.states.async_set(entity_id, state, {"unit_of_measurement": unit})

    async def read_cached_forecast(*_args, **_kwargs):
        return (
            ForecastPoint(
                start=datetime(2026, 7, 18, 10, tzinfo=UTC),
                duration=timedelta(hours=1),
                power_w=1200.0,
            ),
        )

    monkeypatch.setattr(
        "custom_components.universal_energy_manager.coordinator.async_read_forecast_solar",
        read_cached_forecast,
    )
    coordinator = UemShadowCoordinator(hass, MockConfigEntry(domain=DOMAIN, data=data))
    await coordinator.async_refresh()

    assert coordinator.data.forecast_connected is True
    assert coordinator.data.commands_sent is False


@pytest.mark.asyncio
async def test_shadow_coordinator_rejects_malformed_forecast_source_list(hass) -> None:
    coordinator = UemShadowCoordinator(
        hass,
        MockConfigEntry(
            domain=DOMAIN,
            data={CONF_FORECAST_SOLAR_ENTRY_IDS: ["roof", 3]},
        ),
    )

    with pytest.raises(ValueError, match="invalid Forecast.Solar"):
        await coordinator._forecast_connected()
