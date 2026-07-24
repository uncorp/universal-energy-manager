"""Additional tests for remaining uncovered lines in coordinator.py.

Covers:
- coordinator line 146: non-default strategy returned by _read_strategy
- coordinator lines 184, 187: _check_forecast_errors invalid/empty entry_ids
- coordinator line 193: _check_forecast_errors returns 'returned no data'
- coordinator lines 213-214: _compute_charge_limit_async catches ValueError
  from _build_forecast_async
- coordinator lines 290-294: _build_forecast_async catches ValueError/TypeError
  from forecast_solar
- coordinator lines 304, 308, 314-318: generic forecast entity
  wh_hours/minute_data/curve paths
- coordinator lines 333-334: combine_producer_forecasts when
  all_forecasts is non-empty
- coordinator lines 389-391: _compute_charge_limit no running loop uses
  new_event_loop
- coordinator lines 407-409: _compute_charge_limit thread storage/config
  ValueError
- coordinator lines 426-427: _compute_charge_limit thread plan_charge
  ValueError
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.universal_energy_manager.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_CHARGE_END,
    CONF_FORECAST_ENTITY,
    CONF_FORECAST_SOLAR_ENTRY_IDS,
    CONF_GRID_EXPORT_ENTITY,
    CONF_HOUSE_POWER_ENTITY,
    CONF_MAX_CHARGE_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_SOC_ENTITY,
    CONF_STRATEGY,
    DOMAIN,
)
from custom_components.universal_energy_manager.coordinator import (
    UemShadowCoordinator,
)
from custom_components.universal_energy_manager.snapshot import (
    StateSample,
    build_live_state,
)


# ---------------------------------------------------------------------------
# Line 146: _read_strategy returns non-default strategy
# ---------------------------------------------------------------------------
def test_read_strategy_returns_non_default_strategy() -> None:
    """When strategy is configured in entry data, _read_strategy returns it (line 146)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STRATEGY: "battery_first"},
    )
    coordinator = UemShadowCoordinator(MagicMock(), entry)
    assert coordinator._read_strategy() == "battery_first"


# ---------------------------------------------------------------------------
# Lines 184, 187: _check_forecast_errors for invalid/empty entry_ids
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_check_forecast_errors_invalid_entry_ids_type() -> None:
    """_check_forecast_errors returns error string when entry_ids is not a list (line 184)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_FORECAST_SOLAR_ENTRY_IDS: "not-a-list"},
    )
    coordinator = UemShadowCoordinator(MagicMock(), entry)
    result = await coordinator._check_forecast_errors()
    assert result == "invalid Forecast.Solar source configuration"


@pytest.mark.asyncio
async def test_check_forecast_errors_invalid_entry_ids_contents() -> None:
    """_check_forecast_errors returns error string when entry_ids list
    contains non-string items (line 184)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_FORECAST_SOLAR_ENTRY_IDS: ["valid", 123]},
    )
    coordinator = UemShadowCoordinator(MagicMock(), entry)
    result = await coordinator._check_forecast_errors()
    assert result == "invalid Forecast.Solar source configuration"


@pytest.mark.asyncio
async def test_check_forecast_errors_empty_entry_ids() -> None:
    """_check_forecast_errors returns None for empty entry_ids list (line 187)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_FORECAST_SOLAR_ENTRY_IDS: []},
    )
    coordinator = UemShadowCoordinator(MagicMock(), entry)
    result = await coordinator._check_forecast_errors()
    assert result is None  # line 187


# ---------------------------------------------------------------------------
# Line 193: _check_forecast_errors returns 'returned no data' when result is None
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_check_forecast_errors_no_data(hass) -> None:
    """_check_forecast_errors returns 'returned no data' when
    async_read_forecast_solar returns None (line 193)."""

    async def fake_read(*_a, **_k):
        return None  # simulates no data from Forecast.Solar

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_FORECAST_SOLAR_ENTRY_IDS: ["source_1"]},
    )
    coordinator = UemShadowCoordinator(hass, entry)

    with patch(
        "custom_components.universal_energy_manager.coordinator.async_read_forecast_solar",
        fake_read,
    ):
        result = await coordinator._check_forecast_errors()

    assert result == "Forecast.Solar source 'source_1' returned no data"  # line 193


# ---------------------------------------------------------------------------
# Lines 213-214: _compute_charge_limit_async catches ValueError from _build_forecast_async
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_compute_charge_limit_async_catches_forecast_valueerror(hass) -> None:
    """When _build_forecast_async raises ValueError,
    _compute_charge_limit_async returns 0.0 (lines 213-214)."""
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
        ("sensor.e3dc_pv", "2.5", "kW"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1400", "W"),
        ("sensor.e3dc_battery_charge", "1800", "W"),
        ("sensor.e3dc_capacity", "13.0", "kWh"),
        ("sensor.e3dc_max_charge", "12000", "W"),
    ):
        hass.states.async_set(eid, val, {ATTR_UNIT_OF_MEASUREMENT: unit})

    coordinator = UemShadowCoordinator(hass, entry)

    async def fake_forecast(*_a, **_k):
        raise ValueError("forecast build failed")

    coordinator._build_forecast_async = fake_forecast  # type: ignore[assignment]

    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    result = await coordinator._compute_charge_limit_async(
        build_live_state(
            now=now,
            soc=StateSample("55", "%", now),
            pv_power=StateSample("2500", "W", now),
            house_power=StateSample("800", "W", now),
            grid_export=StateSample("1400", "W", now),
            battery_charge=StateSample("1800", "W", now),
        ),
        True,  # forecast_connected = True → will trigger _build_forecast_async
    )
    assert result == 0.0  # lines 213-214: caught, forecast = ()


# ---------------------------------------------------------------------------
# Lines 290-294: _build_forecast_async catches ValueError/TypeError from forecast_solar
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_build_forecast_async_catches_forecast_solar_error(hass) -> None:
    """When Forecast.Solar read raises ValueError,
    _build_forecast_async catches it and falls through (lines 290-294)."""
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
            CONF_FORECAST_SOLAR_ENTRY_IDS: ["bad_solar"],
        },
    )
    for eid, val, unit in (
        ("sensor.e3dc_soc", "55", "%"),
        ("sensor.e3dc_pv", "2500", "W"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1400", "W"),
        ("sensor.e3dc_battery_charge", "1800", "W"),
        ("sensor.e3dc_capacity", "13.0", "kWh"),
        ("sensor.e3dc_max_charge", "12000", "W"),
    ):
        hass.states.async_set(eid, val, {ATTR_UNIT_OF_MEASUREMENT: unit})

    coordinator = UemShadowCoordinator(hass, entry)

    async def bad_forecast(*_a, **_k):
        raise ValueError("solar source error")

    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    live = build_live_state(
        now=now,
        soc=StateSample("55", "%", now),
        pv_power=StateSample("2500", "W", now),
        house_power=StateSample("800", "W", now),
        grid_export=StateSample("1400", "W", now),
        battery_charge=StateSample("1800", "W", now),
    )

    with patch(
        "custom_components.universal_energy_manager.coordinator.async_read_forecast_solar",
        bad_forecast,
    ):
        result = await coordinator._build_forecast_async(live)

    # Should fall back to live PV snapshot (pv_power > 0)
    assert len(result) == 1
    assert result[0].power_w == 2500.0


@pytest.mark.asyncio
async def test_build_forecast_async_catches_forecast_solar_typeerror(hass) -> None:
    """When Forecast.Solar read raises TypeError,
    _build_forecast_async catches it (lines 290-294)."""
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
            CONF_FORECAST_SOLAR_ENTRY_IDS: ["bad_solar"],
        },
    )
    for eid, val, unit in (
        ("sensor.e3dc_soc", "55", "%"),
        ("sensor.e3dc_pv", "2500", "W"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1400", "W"),
        ("sensor.e3dc_battery_charge", "1800", "W"),
        ("sensor.e3dc_capacity", "13.0", "kWh"),
        ("sensor.e3dc_max_charge", "12000", "W"),
    ):
        hass.states.async_set(eid, val, {ATTR_UNIT_OF_MEASUREMENT: unit})

    coordinator = UemShadowCoordinator(hass, entry)

    async def bad_forecast(*_a, **_k):
        raise TypeError("type error in solar")

    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    live = build_live_state(
        now=now,
        soc=StateSample("55", "%", now),
        pv_power=StateSample("2500", "W", now),
        house_power=StateSample("800", "W", now),
        grid_export=StateSample("1400", "W", now),
        battery_charge=StateSample("1800", "W", now),
    )

    with patch(
        "custom_components.universal_energy_manager.coordinator.async_read_forecast_solar",
        bad_forecast,
    ):
        result = await coordinator._build_forecast_async(live)

    assert len(result) == 1


# ---------------------------------------------------------------------------
# Lines 304, 308, 314-318: generic forecast entity wh_hours/minute_data/curve
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_build_forecast_async_generic_wh_hours(hass) -> None:
    """_build_forecast_async reads wh_hours from generic forecast entity (line 304)."""
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
            CONF_FORECAST_ENTITY: "sensor.generic_forecast",
        },
    )
    for eid, val, unit in (
        ("sensor.e3dc_soc", "55", "%"),
        ("sensor.e3dc_pv", "2500", "W"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1400", "W"),
        ("sensor.e3dc_battery_charge", "1800", "W"),
        ("sensor.e3dc_capacity", "13.0", "kWh"),
        ("sensor.e3dc_max_charge", "12000", "W"),
    ):
        hass.states.async_set(eid, val, {ATTR_UNIT_OF_MEASUREMENT: unit})

    # Create generic forecast with wh_hours
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    wh_hours = {}
    for i in range(12):
        ts = (now + timedelta(hours=i)).isoformat()
        wh_hours[ts] = 3000.0  # 3 kWh per hour

    hass.states.async_set(
        "sensor.generic_forecast",
        "3000",
        {"wh_hours": wh_hours, "unit_of_measurement": "W",
         "last_updated": now},
    )

    coordinator = UemShadowCoordinator(hass, entry)
    result = await coordinator._build_forecast_async(
        build_live_state(
            now=now,
            soc=StateSample("55", "%", now),
            pv_power=StateSample("2500", "W", now),
            house_power=StateSample("800", "W", now),
            grid_export=StateSample("1400", "W", now),
            battery_charge=StateSample("1800", "W", now),
        ))

    assert len(result) > 0
    # Should be hourly points from wh_hours
    assert all(p.duration == timedelta(hours=1) for p in result)


@pytest.mark.asyncio
async def test_build_forecast_async_generic_minute_data(hass) -> None:
    """_build_forecast_async reads minute_data from generic forecast entity (line 308)."""
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
            CONF_FORECAST_ENTITY: "sensor.generic_forecast",
        },
    )
    for eid, val, unit in (
        ("sensor.e3dc_soc", "55", "%"),
        ("sensor.e3dc_pv", "2500", "W"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1400", "W"),
        ("sensor.e3dc_battery_charge", "1800", "W"),
        ("sensor.e3dc_capacity", "13.0", "kWh"),
        ("sensor.e3dc_max_charge", "12000", "W"),
    ):
        hass.states.async_set(eid, val, {ATTR_UNIT_OF_MEASUREMENT: unit})

    # Create generic forecast with minute_data (15-min intervals)
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    minute_data = {}
    for i in range(16):  # 4 hours of 15-min intervals
        ts = (now + timedelta(minutes=15 * i)).isoformat()
        minute_data[ts] = 750.0  # 750 Wh per 15 min = 750 W

    hass.states.async_set(
        "sensor.generic_forecast",
        "750",
        {"minute_data": minute_data, "unit_of_measurement": "W",
         "last_updated": now},
    )

    coordinator = UemShadowCoordinator(hass, entry)
    result = await coordinator._build_forecast_async(
        build_live_state(
            now=now,
            soc=StateSample("55", "%", now),
            pv_power=StateSample("2500", "W", now),
            house_power=StateSample("800", "W", now),
            grid_export=StateSample("1400", "W", now),
            battery_charge=StateSample("1800", "W", now),
        ))

    assert len(result) > 0
    # Should be 15-min points from minute_data
    assert all(p.duration == timedelta(minutes=15) for p in result)


@pytest.mark.asyncio
async def test_build_forecast_async_generic_curve(hass) -> None:
    """_build_forecast_async reads 'curve' dict from generic forecast entity (lines 314-318)."""
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
            CONF_FORECAST_ENTITY: "sensor.generic_forecast",
        },
    )
    for eid, val, unit in (
        ("sensor.e3dc_soc", "55", "%"),
        ("sensor.e3dc_pv", "2500", "W"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1400", "W"),
        ("sensor.e3dc_battery_charge", "1800", "W"),
        ("sensor.e3dc_capacity", "13.0", "kWh"),
        ("sensor.e3dc_max_charge", "12000", "W"),
    ):
        hass.states.async_set(eid, val, {ATTR_UNIT_OF_MEASUREMENT: unit})

    # Create generic forecast with 'curve' dict (treated like minute_data)
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    curve = {}
    for i in range(8):
        ts = (now + timedelta(minutes=15 * i)).isoformat()
        curve[ts] = 1500.0  # 1500 Wh per 15 min = 1500 W

    hass.states.async_set(
        "sensor.generic_forecast",
        "1500",
        {"curve": curve, "unit_of_measurement": "W",
         "last_updated": now},
    )

    coordinator = UemShadowCoordinator(hass, entry)
    result = await coordinator._build_forecast_async(
        build_live_state(
            now=now,
            soc=StateSample("55", "%", now),
            pv_power=StateSample("2500", "W", now),
            house_power=StateSample("800", "W", now),
            grid_export=StateSample("1400", "W", now),
            battery_charge=StateSample("1800", "W", now),
        ))

    assert len(result) > 0
    # Curve is treated as minute_data → 15-min intervals
    assert all(p.duration == timedelta(minutes=15) for p in result)


@pytest.mark.asyncio
async def test_build_forecast_async_combines_multiple_forecasts(hass) -> None:
    """When multiple forecasts are produced, they are combined via
    combine_producer_forecasts (lines 333-334)."""
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
            CONF_FORECAST_SOLAR_ENTRY_IDS: ["solar_source"],
            CONF_FORECAST_ENTITY: "sensor.generic_forecast",
        },
    )
    for eid, val, unit in (
        ("sensor.e3dc_soc", "55", "%"),
        ("sensor.e3dc_pv", "2500", "W"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1400", "W"),
        ("sensor.e3dc_battery_charge", "1800", "W"),
        ("sensor.e3dc_capacity", "13.0", "kWh"),
        ("sensor.e3dc_max_charge", "12000", "W"),
    ):
        hass.states.async_set(eid, val, {ATTR_UNIT_OF_MEASUREMENT: unit})

    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    # Forecast.Solar source returns hourly data
    solar_wh_hours = {
        (now + timedelta(hours=i)).isoformat(): 2000.0
        for i in range(8)
    }

    async def fake_solar_read(hass_inst: MagicMock, config_entry_ids: list[str]):
        # Return ForecastPoint tuples (as async_read_forecast_solar does
        # internally)
        from custom_components.universal_energy_manager.models import ForecastPoint
        return tuple(
            ForecastPoint(
                start=datetime.fromisoformat(ts),
                duration=timedelta(hours=1),
                power_w=float(energy),
            )
            for ts, energy in solar_wh_hours.items()
        )

    # Generic forecast also provides data
    minute_data = {}
    for i in range(8):
        ts = (now + timedelta(minutes=15 * i)).isoformat()
        minute_data[ts] = 500.0
    hass.states.async_set(
        "sensor.generic_forecast",
        "500",
        {"minute_data": minute_data, "unit_of_measurement": "W",
         "last_updated": now},
    )

    coordinator = UemShadowCoordinator(hass, entry)

    with patch(
        "custom_components.universal_energy_manager.coordinator.async_read_forecast_solar",
        fake_solar_read,
    ):
        result = await coordinator._build_forecast_async(
            build_live_state(
                now=now,
                soc=StateSample("55", "%", now),
                pv_power=StateSample("2500", "W", now),
                house_power=StateSample("800", "W", now),
                grid_export=StateSample("1400", "W", now),
                battery_charge=StateSample("1800", "W", now),
            ))

    # Both sources should be combined
    assert len(result) > 1  # combined from solar + generic


# ---------------------------------------------------------------------------
# Lines 317-318: generic forecast entity curve path ValueError → pass
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_build_forecast_async_generic_curve_valueerror_falls_back(hass) -> None:
    """When forecast_from_minute_data raises ValueError on 'curve' attribute,
    the except block (lines 317-318) catches it and falls back to live PV snapshot."""
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
            CONF_FORECAST_ENTITY: "sensor.generic_forecast",
        },
    )
    for eid, val, unit in (
        ("sensor.e3dc_soc", "55", "%"),
        ("sensor.e3dc_pv", "2500", "W"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1400", "W"),
        ("sensor.e3dc_battery_charge", "1800", "W"),
        ("sensor.e3dc_capacity", "13.0", "kWh"),
        ("sensor.e3dc_max_charge", "12000", "W"),
    ):
        hass.states.async_set(eid, val, {ATTR_UNIT_OF_MEASUREMENT: unit})

    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    # 'curve' with non-naive timestamps will cause ValueError
    # because curve is a dict but the timestamps inside aren't parseable
    bad_curve = {"invalid-timestamp!!!" : 1500.0}

    hass.states.async_set(
        "sensor.generic_forecast",
        "1500",
        {"curve": bad_curve, "unit_of_measurement": "W",
         "last_updated": now},
    )

    coordinator = UemShadowCoordinator(hass, entry)
    # Should not crash — falls back to live PV snapshot
    result = await coordinator._build_forecast_async(
        build_live_state(
            now=now,
            soc=StateSample("55", "%", now),
            pv_power=StateSample("2500", "W", now),
            house_power=StateSample("800", "W", now),
            grid_export=StateSample("1400", "W", now),
            battery_charge=StateSample("1800", "W", now),
        ))

    # Falls back to live PV snapshot
    assert len(result) == 1
    assert result[0].power_w == 2500.0


# ---------------------------------------------------------------------------
# Lines 389-391: _compute_charge_limit no running loop uses new_event_loop
# ---------------------------------------------------------------------------
def test_compute_charge_limit_no_running_loop(hass) -> None:
    """When there's no running event loop,
    _compute_charge_limit uses new_event_loop (lines 389-391)."""
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
        ("sensor.e3dc_pv", "3000", "W"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1400", "W"),
        ("sensor.e3dc_battery_charge", "1800", "W"),
        ("sensor.e3dc_capacity", "13.0", "kWh"),
        ("sensor.e3dc_max_charge", "12000", "W"),
    ):
        hass.states.async_set(eid, val, {ATTR_UNIT_OF_MEASUREMENT: unit})

    coordinator = UemShadowCoordinator(hass, entry)
    coordinator._forecast_connected = AsyncMock(return_value=False)

    # This must NOT raise "cannot schedule new futures on a stopped event loop"
    # It goes through line 389-391 (no running loop → new_event_loop)
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    live = build_live_state(
        now=now,
        soc=StateSample("55", "%", now),
        pv_power=StateSample("3000", "W", now),
        house_power=StateSample("800", "W", now),
        grid_export=StateSample("1400", "W", now),
        battery_charge=StateSample("1800", "W", now),
    )
    # Since forecast_connected=False and no forecast → plan_charge returns 0.0
    result = coordinator._compute_charge_limit(live, False)
    assert isinstance(result, (int, float))


# ---------------------------------------------------------------------------
# Lines 407-409: _compute_charge_limit thread storage/config ValueError → 0.0
# ---------------------------------------------------------------------------
def test_compute_charge_limit_thread_storage_config_error(hass) -> None:
    """When _build_storage_capabilities or _build_planner_config raises in the thread,
    the thread returns 0.0 (lines 407-409)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            # Missing battery_capacity_entity and max_charge_power_entity → ValueError
            CONF_SOC_ENTITY: "sensor.e3dc_soc",
            CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
            CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid_export",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery_charge",
        },
    )
    for eid, val, unit in (
        ("sensor.e3dc_soc", "55", "%"),
        ("sensor.e3dc_pv", "3000", "W"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1400", "W"),
        ("sensor.e3dc_battery_charge", "1800", "W"),
    ):
        hass.states.async_set(eid, val, {ATTR_UNIT_OF_MEASUREMENT: unit})

    coordinator = UemShadowCoordinator(hass, entry)
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    live = build_live_state(
        now=now,
        soc=StateSample("55", "%", now),
        pv_power=StateSample("3000", "W", now),
        house_power=StateSample("800", "W", now),
        grid_export=StateSample("1400", "W", now),
        battery_charge=StateSample("1800", "W", now),
    )
    result = coordinator._compute_charge_limit(live, False)
    assert result == 0.0  # lines 407-409: caught in thread, returns 0.0


# ---------------------------------------------------------------------------
# Lines 426-427: _compute_charge_limit thread plan_charge ValueError → 0.0
# ---------------------------------------------------------------------------
def test_compute_charge_limit_thread_plan_charge_error(hass) -> None:
    """When plan_charge raises ValueError inside the thread,
    the thread returns 0.0 (lines 426-427)."""
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
            # Set charge_end to a past time → plan_charge raises
            CONF_CHARGE_END: "2020-01-01T00:00:00+00:00",
        },
    )
    for eid, val, unit in (
        ("sensor.e3dc_soc", "55", "%"),
        ("sensor.e3dc_pv", "3000", "W"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1400", "W"),
        ("sensor.e3dc_battery_charge", "1800", "W"),
        ("sensor.e3dc_capacity", "13.0", "kWh"),
        ("sensor.e3dc_max_charge", "12000", "W"),
    ):
        hass.states.async_set(eid, val, {ATTR_UNIT_OF_MEASUREMENT: unit})

    coordinator = UemShadowCoordinator(hass, entry)
    coordinator._forecast_connected = AsyncMock(return_value=True)

    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    live = build_live_state(
        now=now,
        soc=StateSample("55", "%", now),
        pv_power=StateSample("3000", "W", now),
        house_power=StateSample("800", "W", now),
        grid_export=StateSample("1400", "W", now),
        battery_charge=StateSample("1800", "W", now),
    )
    result = coordinator._compute_charge_limit(live, True)
    assert result == 0.0  # lines 426-427: plan_charge ValueError caught in thread


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def live_state_from_hass(hass: MagicMock, now: datetime):
    """Build a LiveState from current hass states."""
    def _sample(eid):
        state = hass.states.get(eid)
        return StateSample(
            state.state,
            state.attributes.get(ATTR_UNIT_OF_MEASUREMENT),
            state.last_updated,
        )
    return build_live_state(
        now=now,
        soc=_sample("sensor.e3dc_soc"),
        pv_power=_sample("sensor.e3dc_pv"),
        house_power=_sample("sensor.e3dc_house"),
        grid_export=_sample("sensor.e3dc_grid_export"),
        battery_charge=_sample("sensor.e3dc_battery_charge"),
    )


# ---------------------------------------------------------------------------
# Lines 445-447, 464-465: _compute_charge_limit thread path with running loop
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_compute_charge_limit_thread_storage_config_value_error(hass) -> None:
    """When _build_storage_capabilities raises in the thread (running loop path),
    lines 445-447 catch it and return 0.0."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            # Missing battery_capacity_entity and max_charge_power_entity
            CONF_SOC_ENTITY: "sensor.e3dc_soc",
            CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
            CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
            CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid_export",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery_charge",
        },
    )
    for eid, val, unit in (
        ("sensor.e3dc_soc", "55", "%"),
        ("sensor.e3dc_pv", "3000", "W"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1400", "W"),
        ("sensor.e3dc_battery_charge", "1800", "W"),
    ):
        hass.states.async_set(eid, val, {ATTR_UNIT_OF_MEASUREMENT: unit})

    coordinator = UemShadowCoordinator(hass, entry)
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    live = build_live_state(
        now=now,
        soc=StateSample("55", "%", now),
        pv_power=StateSample("3000", "W", now),
        house_power=StateSample("800", "W", now),
        grid_export=StateSample("1400", "W", now),
        battery_charge=StateSample("1800", "W", now),
    )
    # Called from async context → running loop exists → thread path (lines 438-472)
    result = coordinator._compute_charge_limit(live, False)
    assert result == 0.0  # lines 445-447: caught in thread


@pytest.mark.asyncio
async def test_compute_charge_limit_thread_plan_charge_value_error(hass) -> None:
    """When plan_charge raises ValueError inside the thread (running loop path),
    lines 464-465 catch it and return 0.0."""
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
            CONF_CHARGE_END: "2020-01-01T00:00:00+00:00",
        },
    )
    for eid, val, unit in (
        ("sensor.e3dc_soc", "55", "%"),
        ("sensor.e3dc_pv", "3000", "W"),
        ("sensor.e3dc_house", "800", "W"),
        ("sensor.e3dc_grid_export", "1400", "W"),
        ("sensor.e3dc_battery_charge", "1800", "W"),
        ("sensor.e3dc_capacity", "13.0", "kWh"),
        ("sensor.e3dc_max_charge", "12000", "W"),
    ):
        hass.states.async_set(eid, val, {ATTR_UNIT_OF_MEASUREMENT: unit})

    coordinator = UemShadowCoordinator(hass, entry)
    coordinator._forecast_connected = AsyncMock(return_value=True)

    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    live = build_live_state(
        now=now,
        soc=StateSample("55", "%", now),
        pv_power=StateSample("3000", "W", now),
        house_power=StateSample("800", "W", now),
        grid_export=StateSample("1400", "W", now),
        battery_charge=StateSample("1800", "W", now),
    )
    # Called from async context → running loop exists → thread path (lines 438-472)
    result = coordinator._compute_charge_limit(live, True)
    assert result == 0.0  # lines 464-465: plan_charge ValueError caught in thread
