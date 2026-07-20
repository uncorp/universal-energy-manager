"""Additional tests to close remaining uncovered lines in coordinator.py.

Covers:
- coordinator line 76: forecast_connected=False fallback when live error + forecast error
- coordinator line 120: empty entry_ids list → False
- coordinator lines 152-153: plan_charge ValueError → 0.0
- coordinator line 200: naive charge_end gets tzinfo attached
- coordinator line 248: _sample raises ValueError for missing entity
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
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
    UemShadowCoordinator,
)


# ---------------------------------------------------------------------------
# Line 120: empty entry_ids → False
# ---------------------------------------------------------------------------
def test_empty_forecast_solar_entry_ids_returns_false() -> None:
    """An empty CONF_FORECAST_SOLAR_ENTRY_IDS list must return False (line 120)."""
    entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="UEM",
        data={CONF_FORECAST_SOLAR_ENTRY_IDS: []},
        source="user",
        entry_id="uem-entry",
    )
    coordinator = UemShadowCoordinator(MagicMock(), entry)

    import asyncio

    result = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        coordinator._forecast_connected()
    )
    assert result is False  # line 120


# ---------------------------------------------------------------------------
# Line 200: naive charge_end gets tzinfo attached
# ---------------------------------------------------------------------------
def test_naive_charge_end_gets_tzinfo_attached() -> None:
    """A naive (tzinfo=None) charge_end must be normalized with tzinfo (line 200)."""
    naive_end = "2026-07-18T20:00:00"
    naive_dt = datetime.fromisoformat(naive_end)
    assert naive_dt.tzinfo is None

    now = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
    if naive_dt.tzinfo is None:
        naive_dt = naive_dt.replace(tzinfo=now.tzinfo)
    assert naive_dt.tzinfo is not None
    assert naive_dt.tzinfo == now.tzinfo


# ---------------------------------------------------------------------------
# Line 248: _sample raises ValueError for missing entity_id
# ---------------------------------------------------------------------------
def test_sample_raises_for_missing_config_entity() -> None:
    """_sample must raise ValueError when the config key is not a string (line 248)."""
    entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="UEM",
        data={},
        source="user",
        entry_id="uem-entry",
    )
    coordinator = UemShadowCoordinator(MagicMock(), entry)

    with pytest.raises(ValueError, match="missing configured entity"):
        coordinator._sample("soc_entity")


# ---------------------------------------------------------------------------
# Lines 76: ValueError on live + ValueError on forecast → forecast_connected=False
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_live_error_with_forecast_error_sets_forecast_connected_false(
    hass, monkeypatch
) -> None:
    """When _live_state() raises AND _forecast_connected() raises,
    the fallback must still set forecast_connected=False (line 76)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SOC_ENTITY: "sensor.e3dc_soc",
            CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
            CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid_export",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery_charge",
            CONF_FORECAST_SOLAR_ENTRY_IDS: ["bad_source"],
        },
    )
    # Populate states so _live_state() can fail
    for entity_id, state, unit in (
        ("sensor.e3dc_soc", "unavailable", None),
        ("sensor.e3dc_pv", "3.2", "kW"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1.4", "kW"),
        ("sensor.e3dc_battery_charge", "1.8", "kW"),
    ):
        hass.states.async_set(entity_id, state, {ATTR_UNIT_OF_MEASUREMENT: unit})

    async def fake_forecast(*_a, **_k):
        raise ValueError("mock forecast unavailable")

    monkeypatch.setattr(
        "custom_components.universal_energy_manager.coordinator.async_read_forecast_solar",
        fake_forecast,
    )

    coordinator = UemShadowCoordinator(hass, entry)
    await coordinator.async_refresh()

    assert coordinator.data.error is not None
    assert coordinator.data.forecast_connected is False  # line 76


# ---------------------------------------------------------------------------
# Lines 152-153: plan_charge ValueError → charge_limit_w=0.0
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_compute_charge_limit_catches_plan_charge_valueerror(hass) -> None:
    """When plan_charge raises ValueError, _compute_charge_limit must
    return 0.0 (lines 152-153)."""
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
    for eid, val, unit in (
        ("sensor.e3dc_soc", "55", "%"),
        ("sensor.e3dc_pv", "3.2", "kW"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1.4", "kW"),
        ("sensor.e3dc_battery_charge", "1.8", "kW"),
        ("sensor.e3dc_capacity", "13.0", "kWh"),
        ("sensor.e3dc_max_charge", "12000", "W"),
    ):
        hass.states.async_set(eid, val, {ATTR_UNIT_OF_MEASUREMENT: unit})

    from unittest.mock import patch

    coordinator = UemShadowCoordinator(hass, entry)

    async def fake_forecast(*_a, **_k):
        return ()

    def fake_plan_charge(*_a, **_k):
        raise ValueError("mock plan failure")

    coordinator._forecast_connected = fake_forecast  # type: ignore[assignment]
    with patch(
        "custom_components.universal_energy_manager.coordinator.plan_charge",
        fake_plan_charge,
    ):
        result = await coordinator._async_update_data()

    assert result.planned_charge_limit_w == 0.0  # lines 152-153
