"""TDD test for coordinator._is_incomplete when max charge power is entirely missing.

Covers line 511 of coordinator.py: the final check where _is_incomplete returns True
because neither max_charge_power entity nor manual W value is configured.

This directly implements MVP acceptance criterion #5:
'Bei fehlenden, alten oder unplausiblen Daten sendet UEM keine neuen E3DC-Befehle
und erklärt den Status.'
"""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_MANUAL_CAPACITY_KWH,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MAX_CHARGE_MANUAL_POWER_W,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
)
from custom_components.universal_energy_manager.coordinator import (
    SHADOW_STATUS_UNVOLLSTANDIG,
    ShadowData,
    UemShadowCoordinator,
)


def test_incomplete_when_max_charge_power_entity_and_manual_both_missing() -> None:
    """All core + capacity OK, but max charge power entity AND manual W are empty.

    This exercises the final branch at line 511 of coordinator.py where
    _is_incomplete returns True because the last remaining required
    field (max_charge_power) is completely missing.

    The coordinator must then report 'Shadow – Einrichtung unvollständig'
    and never send any command (commands_sent is always False).
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SOC_ENTITY: "sensor.e3dc_soc",
            CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
            CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
            CONF_BATTERY_MANUAL_CAPACITY_KWH: "13.0",
            # max charge power completely missing — both entity and manual
            CONF_MAX_CHARGE_POWER_ENTITY: "",
            CONF_MAX_CHARGE_MANUAL_POWER_W: "",
        },
    )

    coordinator = UemShadowCoordinator(None, entry)
    assert coordinator._is_incomplete() is True


def test_incomplete_max_charge_power_missing_yields_shadow_status(hass) -> None:
    """When max charge power is entirely missing the full update cycle must
    produce a ShadowData with the 'unvollständig' status and zero limit."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SOC_ENTITY: "sensor.e3dc_soc",
            CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_charge",
            CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
            CONF_BATTERY_MANUAL_CAPACITY_KWH: "13.0",
            CONF_MAX_CHARGE_POWER_ENTITY: "",
            CONF_MAX_CHARGE_MANUAL_POWER_W: "",
        },
    )

    coordinator = UemShadowCoordinator(hass, entry)

    import asyncio

    result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        coordinator._async_update_data()
    )

    assert isinstance(result, ShadowData)
    assert result.status == SHADOW_STATUS_UNVOLLSTANDIG
    assert result.planned_charge_limit_w == 0.0
    assert result.commands_sent is False
    assert result.error is not None
