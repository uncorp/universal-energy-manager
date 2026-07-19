"""Runtime regression guard: the Shadow coordinator must never call HA services.

This test verifies that the coordinator cannot send service/control commands
even when the HA service registry is active. It patches ``hass.services`` so
that any attempt to call a service (``async_call``, ``call``, ``fire``) is
detected and causes the test to fail.

This complements ``test_shadow_no_control.py`` which only checks for forbidden
imports via AST parsing. The AST guard misses calls like ``hass.services.async_call()``
that do not import any of the forbidden symbols.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
)
from custom_components.universal_energy_manager.coordinator import (
    UemShadowCoordinator,
)


@pytest.fixture
def _minimal_config() -> dict:
    return {
        CONF_SOC_ENTITY: "sensor.e3dc_soc",
        CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
        CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
        CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid_export",
        CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery_charge",
    }


@pytest.fixture
def _populated_states(hass: HomeAssistant, _minimal_config: dict) -> dict:
    values = {
        "sensor.e3dc_soc": ("55", "%"),
        "sensor.e3dc_pv": ("3.2", "kW"),
        "sensor.e3dc_house": ("800", "W"),
        "sensor.e3dc_grid_export": ("1.4", "kW"),
        "sensor.e3dc_battery_charge": ("1.8", "kW"),
    }
    for entity_id, (state, unit) in values.items():
        hass.states.async_set(entity_id, state, {"unit_of_measurement": unit})
    return values


@pytest.mark.asyncio
async def test_coordinator_never_calls_hass_services(
    hass: HomeAssistant, _minimal_config: dict, _populated_states: dict
) -> None:
    """Assert that the coordinator does not invoke any HA service method.

    The ``hass.services`` object has methods like ``async_call``, ``call``,
    and ``fire`` that constitute control-plane actions. Shadow mode must not
    call any of them.
    """
    services_mock = MagicMock()
    services_mock.async_call = AsyncMock()
    services_mock.call = MagicMock()
    services_mock.fire = MagicMock()

    with patch.object(hass, "services", services_mock):
        entry = MockConfigEntry(domain=DOMAIN, data=_minimal_config)
        coordinator = UemShadowCoordinator(hass, entry)
        await coordinator.async_refresh()

    # If any service call slipped through, the mock would have been called.
    assert services_mock.async_call.call_count == 0, (
        "Shadow coordinator must not call hass.services.async_call()"
    )
    assert services_mock.call.call_count == 0, (
        "Shadow coordinator must not call hass.services.call()"
    )
    assert services_mock.fire.call_count == 0, (
        "Shadow coordinator must not call hass.services.fire()"
    )


@pytest.mark.asyncio
async def test_shadow_data_commands_sent_is_always_false(
    hass: HomeAssistant, _minimal_config: dict, _populated_states: dict
) -> None:
    """Verify the data contract: commands_sent is False."""
    entry = MockConfigEntry(domain=DOMAIN, data=_minimal_config)
    coordinator = UemShadowCoordinator(hass, entry)
    await coordinator.async_refresh()

    assert coordinator.data.commands_sent is False
    assert coordinator.data.planned_charge_limit_w == 0.0


@pytest.mark.asyncio
async def test_coordinator_reads_states_via_hass_states_not_services(
    hass: HomeAssistant, _minimal_config: dict, _populated_states: dict
) -> None:
    """Confirm the coordinator reaches entities through hass.states (read-only),
    not through the service registry (control).

    ``hass.states.get()`` is the legitimate read-only API; anything that
    touches ``hass.services`` is a regression.
    """
    services_mock = MagicMock()
    services_mock.async_call = AsyncMock()

    with patch.object(hass, "services", services_mock):
        entry = MockConfigEntry(domain=DOMAIN, data=_minimal_config)
        coordinator = UemShadowCoordinator(hass, entry)
        await coordinator.async_refresh()

    assert coordinator.data.error is None
    assert services_mock.async_call.call_count == 0
