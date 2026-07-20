"""Shadow coordinator must surface the planner's computed charge limit.

In Shadow mode UEM never sends commands, but it must still compute and
publish ``planned_charge_limit_w`` based on the pure planner. Before this
Slice the coordinator always returned ``0.0`` despite having a working
``plan_charge()``.

This is the smallest Shadow-only vertical slice that closes the gap
between the planner's calculation and the coordinator's published data.

No HA entity writes, no service calls, no credentials.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntry
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_FORECAST_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
)
from custom_components.universal_energy_manager.coordinator import UemShadowCoordinator
from custom_components.universal_energy_manager.snapshot import StateSample


def _make_basic_config(
    extra: dict | None = None,
) -> dict:
    data = {
        CONF_SOC_ENTITY: "sensor.e3dc_soc",
        CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
        CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
        CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid_export",
        CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery_charge",
        CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
        CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
        CONF_FORECAST_ENTITY: "sensor.e3dc_forecast",
    }
    if extra:
        data.update(extra)
    return data


def _set_basic_states(
    hass,
    soc: str = "55",
    pv: str = "3.2",
    pv_unit: str = "kW",
) -> None:
    for entity_id, state, unit in (
        ("sensor.e3dc_soc", soc, "%"),
        ("sensor.e3dc_pv", pv, pv_unit),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1.4", "kW"),
        ("sensor.e3dc_battery_charge", "1.8", "kW"),
        ("sensor.e3dc_capacity", "13.0", "kWh"),
        ("sensor.e3dc_max_charge", "12000", "W"),
        ("sensor.e3dc_forecast", "10:00", "{}"),
    ):
        hass.states.async_set(entity_id, state, {"unit_of_measurement": unit})


def _make_sample(key: str, entry: ConfigEntry, hass, now: datetime) -> StateSample:
    return StateSample(
        value=hass.states.get(entry.data.get(key)).state,
        unit=hass.states.get(entry.data.get(key)).attributes.get(
            "unit_of_measurement"
        ),
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Test 1: planned_charge_limit_w is non-zero when forecast is connected
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_shadow_coordinator_exposes_nonzero_charge_limit_with_forecast(
    hass,
) -> None:
    """When live data is valid and a forecast interval covers *now*, the
    ShadowData must contain a computed charge limit > 0, not the old 0.0."""
    _set_basic_states(hass)
    now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_make_basic_config(),
    )

    coordinator = UemShadowCoordinator(hass, entry)

    with patch.object(coordinator, "_sample", lambda key: _make_sample(key, entry, hass, now)):
        with patch(
            "custom_components.universal_energy_manager.coordinator.dt_util.utcnow",
            return_value=now,
        ):
            result = await coordinator._async_update_data()

    assert result.error is None
    assert result.commands_sent is False
    assert result.forecast_connected is True
    assert result.planned_charge_limit_w > 0, (
        f"Expected non-zero planned charge limit with valid data, "
        f"got {result.planned_charge_limit_w}"
    )


# ---------------------------------------------------------------------------
# Test 2: planned_charge_limit_w is zero when final target already reached
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_shadow_coordinator_zero_limit_when_target_already_reached(
    hass,
) -> None:
    """If SoC >= target_soc_pct, the planner returns zero and the
    coordinator must surface that zero."""
    _set_basic_states(hass, soc="95")
    now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_make_basic_config(),
    )

    coordinator = UemShadowCoordinator(hass, entry)

    with patch.object(coordinator, "_sample", lambda key: _make_sample(key, entry, hass, now)):
        with patch(
            "custom_components.universal_energy_manager.coordinator.dt_util.utcnow",
            return_value=now,
        ):
            result = await coordinator._async_update_data()

    assert result.error is None
    assert result.commands_sent is False
    assert result.planned_charge_limit_w == 0.0


# ---------------------------------------------------------------------------
# Test 3: planned_charge_limit_w is capped by storage max_charge_power_w
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_shadow_coordinator_respects_max_charge_power_cap(
    hass,
) -> None:
    """The coordinator's planned limit must never exceed the battery's
    max_charge_power_w, even when the surplus is larger."""
    _set_basic_states(hass, pv="10", pv_unit="kW")
    now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_make_basic_config(),
    )

    coordinator = UemShadowCoordinator(hass, entry)

    with patch.object(coordinator, "_sample", lambda key: _make_sample(key, entry, hass, now)):
        with patch(
            "custom_components.universal_energy_manager.coordinator.dt_util.utcnow",
            return_value=now,
        ):
            result = await coordinator._async_update_data()

    assert result.error is None
    assert result.commands_sent is False
    assert result.planned_charge_limit_w <= 12000.0, (
        f"Planned charge limit {result.planned_charge_limit_w}W must not "
        f"exceed max_charge_power_w of 12000W"
    )
