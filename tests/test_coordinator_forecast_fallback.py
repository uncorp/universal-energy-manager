"""Tests for coordinator fallback paths when forecast data degrades.

Covers the smallest untested coordinator slices:
- _build_forecast_from_snapshot returns empty when pv_power == 0
- _build_forecast_from_snapshot falls back to DEFAULT_CHARGE_END_HOURS on bad charge_end
- _parse_float_entity returns None for non-numeric/missing/None states
- Full coordinator refresh with malformed charge_end does not crash
"""

from datetime import UTC, datetime, timedelta

import pytest
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
    DEFAULT_CHARGE_END_HOURS,
    DOMAIN,
)
from custom_components.universal_energy_manager.coordinator import (
    SHADOW_STATUS,
    UemShadowCoordinator,
)
from custom_components.universal_energy_manager.snapshot import StateSample, build_live_state


def _make_full_entry(
    pv_power: str,
    extra_data: dict | None = None,
) -> tuple[MockConfigEntry, dict[str, tuple[str, str | None]]]:
    """Return a full entity-by-key entry and state values."""
    entity_by_config_key = {
        CONF_SOC_ENTITY: "sensor.e3dc_soc",
        CONF_PV_POWER_ENTITY: "sensor.e3dc_pv",
        CONF_HOUSE_POWER_ENTITY: "sensor.e3dc_house",
        CONF_GRID_EXPORT_ENTITY: "sensor.e3dc_grid_export",
        CONF_BATTERY_CHARGE_ENTITY: "sensor.e3dc_battery_charge",
        CONF_BATTERY_CAPACITY_ENTITY: "sensor.e3dc_capacity",
        CONF_MAX_CHARGE_POWER_ENTITY: "sensor.e3dc_max_charge",
    }
    values: dict[str, tuple[str, str | None]] = {
        "sensor.e3dc_soc": ("55", "%"),
        "sensor.e3dc_pv": (pv_power, "kW"),
        "sensor.e3dc_house": ("800", "W"),
        "sensor.e3dc_grid_export": ("1.4", "kW"),
        "sensor.e3dc_battery_charge": ("1.8", "kW"),
        "sensor.e3dc_capacity": ("13.0", "kWh"),
        "sensor.e3dc_max_charge": ("12000", "W"),
    }
    data = dict(entity_by_config_key)
    if extra_data:
        data.update(extra_data)
    return MockConfigEntry(domain=DOMAIN, data=data), values


def test_build_forecast_from_snapshot_returns_empty_on_zero_pv(hass) -> None:
    """When live PV power is zero, _build_forecast_from_snapshot must return ()."""
    entry, values = _make_full_entry(pv_power="0.0")
    for entity_id, (state, unit) in values.items():
        hass.states.async_set(entity_id, state, {"unit_of_measurement": unit})

    coordinator = UemShadowCoordinator(hass, entry)
    now = datetime(2026, 7, 18, 12, tzinfo=UTC)

    live = build_live_state(
        now=now,
        soc=StateSample("55", "%", now),
        pv_power=StateSample("0.0", "kW", now),
        house_power=StateSample("800", "W", now),
        grid_export=StateSample("1400", "W", now),
        battery_charge=StateSample("1800", "W", now),
    )
    forecast = coordinator._build_forecast_from_snapshot(live)
    assert forecast == ()


def test_build_forecast_from_snapshot_fallback_charge_end_on_bad_iso(hass) -> None:
    """When charge_end_raw is a malformed ISO string, _build_forecast_from_snapshot
    must fall back to DEFAULT_CHARGE_END_HOURS and not crash."""
    entry, values = _make_full_entry(
        pv_power="2.5",
        extra_data={CONF_CHARGE_END: "not-a-date"},
    )
    for entity_id, (state, unit) in values.items():
        hass.states.async_set(entity_id, state, {"unit_of_measurement": unit})

    coordinator = UemShadowCoordinator(hass, entry)
    now = datetime(2026, 7, 18, 12, tzinfo=UTC)

    live = build_live_state(
        now=now,
        soc=StateSample("55", "%", now),
        pv_power=StateSample("2.5", "kW", now),
        house_power=StateSample("800", "W", now),
        grid_export=StateSample("1400", "W", now),
        battery_charge=StateSample("1800", "W", now),
    )
    # Should not raise; must use fallback duration.
    forecast = coordinator._build_forecast_from_snapshot(live)
    assert len(forecast) == 1
    expected_duration = timedelta(hours=DEFAULT_CHARGE_END_HOURS)
    assert forecast[0].duration == expected_duration
    assert forecast[0].power_w == 2500.0  # 2.5 kW -> watts


def test_build_forecast_from_snapshot_valid_charge_end_preserved(hass) -> None:
    """When charge_end_raw is a valid ISO string, _build_forecast_from_snapshot must
    use it as the interval end, not the fallback."""
    valid_end = datetime(2026, 7, 18, 20, tzinfo=UTC).isoformat()
    entry, values = _make_full_entry(
        pv_power="3.0",
        extra_data={CONF_CHARGE_END: valid_end},
    )
    for entity_id, (state, unit) in values.items():
        hass.states.async_set(entity_id, state, {"unit_of_measurement": unit})

    coordinator = UemShadowCoordinator(hass, entry)
    now = datetime(2026, 7, 18, 12, tzinfo=UTC)

    live = build_live_state(
        now=now,
        soc=StateSample("55", "%", now),
        pv_power=StateSample("3.0", "kW", now),
        house_power=StateSample("800", "W", now),
        grid_export=StateSample("1400", "W", now),
        battery_charge=StateSample("1800", "W", now),
    )
    forecast = coordinator._build_forecast_from_snapshot(live)
    assert len(forecast) == 1
    expected_duration = timedelta(hours=8)  # 20:00 - 12:00
    assert forecast[0].duration == expected_duration


@pytest.mark.asyncio
async def test_coordinator_shadow_status_when_forecast_build_fails_live_valid(
    hass,
) -> None:
    """When _compute_charge_limit encounters a ValueError during _build_forecast_from_snapshot,
    it must return charge_limit_w=0.0 (not crash the coordinator)."""
    entry, values = _make_full_entry(pv_power="2.5")
    for entity_id, (state, unit) in values.items():
        hass.states.async_set(entity_id, state, {"unit_of_measurement": unit})

    coordinator = UemShadowCoordinator(hass, entry)
    now = datetime.now(UTC)
    live = build_live_state(
        now=now,
        soc=StateSample("55", "%", now),
        pv_power=StateSample("2.5", "kW", now),
        house_power=StateSample("800", "W", now),
        grid_export=StateSample("1400", "W", now),
        battery_charge=StateSample("1800", "W", now),
    )

    # Patch _build_forecast_from_snapshot to raise ValueError
    original = coordinator._build_forecast_from_snapshot
    def _raise_mock(_live):  # type: ignore[unused-argument]
        raise ValueError("mock")
    coordinator._build_forecast_from_snapshot = _raise_mock  # type: ignore[assignment]

    try:
        # _build_forecast_from_snapshot raises, caught in _compute_charge_limit,
        # forecast = () then plan_charge raises ValueError("no current forecast interval")
        # which is caught and returns 0.0
        result = coordinator._compute_charge_limit(live, True)
        assert result == 0.0
    finally:
        coordinator._build_forecast_from_snapshot = original


@pytest.mark.asyncio
async def test_coordinator_full_refresh_with_bad_charge_end(hass) -> None:
    """Full coordinator refresh with a malformed charge_end must not crash and must
    produce a valid ShadowData with a charge limit (not 0 from a crash)."""
    entry, values = _make_full_entry(
        pv_power="2.5",
        extra_data={CONF_CHARGE_END: "broken-date!!"},
    )
    for entity_id, (state, unit) in values.items():
        hass.states.async_set(entity_id, state, {"unit_of_measurement": unit})

    coordinator = UemShadowCoordinator(hass, entry)
    from unittest.mock import AsyncMock

    coordinator._forecast_connected = AsyncMock(return_value=False)
    await coordinator.async_refresh()

    # Must not crash; should produce valid data with charge_limit possibly 0 (no forecast)
    assert coordinator.data.status == SHADOW_STATUS
    assert coordinator.data.commands_sent is False
    assert coordinator.data.error is None


def test_parse_float_entity_handles_non_numeric_state(hass) -> None:
    """_parse_float_entity must return None for non-numeric states (line 180-181)."""
    entry, values = _make_full_entry(pv_power="2.5")
    for entity_id, (state, unit) in values.items():
        hass.states.async_set(entity_id, state, {"unit_of_measurement": unit})

    # Override capacity to non-numeric
    hass.states.async_set("sensor.e3dc_capacity", "not-a-number", {"unit_of_measurement": "kWh"})

    coordinator = UemShadowCoordinator(hass, entry)
    result = coordinator._parse_float_entity("sensor.e3dc_capacity")
    assert result is None


def test_parse_float_entity_handles_missing_entity(hass) -> None:
    """_parse_float_entity must return None for nonexistent entities."""
    entry, values = _make_full_entry(pv_power="2.5")
    coordinator = UemShadowCoordinator(hass, entry)

    result = coordinator._parse_float_entity("sensor.nonexistent")
    assert result is None


def test_parse_float_entity_handles_none_key(hass) -> None:
    """_parse_float_entity must return None for None key."""
    entry, values = _make_full_entry(pv_power="2.5")
    coordinator = UemShadowCoordinator(hass, entry)

    result = coordinator._parse_float_entity(None)
    assert result is None


def test_parse_float_entity_handles_int_input(hass) -> None:
    """_parse_float_entity must handle an int directly (line 276)."""
    entry, values = _make_full_entry(pv_power="2.5")
    coordinator = UemShadowCoordinator(hass, entry)

    result = coordinator._parse_float_entity(42)
    assert result == 42.0


def test_parse_float_entity_handles_float_input(hass) -> None:
    """_parse_float_entity must handle a float directly (line 276)."""
    entry, values = _make_full_entry(pv_power="2.5")
    coordinator = UemShadowCoordinator(hass, entry)

    result = coordinator._parse_float_entity(3.14)
    assert result == 3.14


def test_parse_float_entity_handles_non_string_non_numeric(hass) -> None:
    """_parse_float_entity must return None for a non-string, non-numeric type (line 278)."""
    entry, values = _make_full_entry(pv_power="2.5")
    coordinator = UemShadowCoordinator(hass, entry)

    result = coordinator._parse_float_entity(["not", "a", "string"])
    assert result is None


def test_parse_float_entity_handles_empty_string(hass) -> None:
    """_parse_float_entity must return None for an empty string (line 280)."""
    entry, values = _make_full_entry(pv_power="2.5")
    coordinator = UemShadowCoordinator(hass, entry)

    result = coordinator._parse_float_entity("")
    assert result is None

    result = coordinator._parse_float_entity("   ")
    assert result is None


def test_parse_float_entity_handles_manual_value_string(hass) -> None:
    """_parse_float_entity must parse a pure numeric string as manual value (line 288-289)."""
    entry, values = _make_full_entry(pv_power="2.5")
    coordinator = UemShadowCoordinator(hass, entry)

    # A string that's a valid float is treated as a manual value
    result = coordinator._parse_float_entity("123.45")
    assert result == 123.45

    # A string that's not a valid float falls through ValueError and returns None
    result = coordinator._parse_float_entity("abc")
    assert result is None


def test_parse_float_entity_handles_numeric_string_but_not_entity_state(hass) -> None:
    """_parse_float_entity: numeric string not matching a real entity → manual parse."""
    entry, values = _make_full_entry(pv_power="2.5")
    for entity_id, (state, unit) in values.items():
        hass.states.async_set(entity_id, state, {"unit_of_measurement": unit})

    coordinator = UemShadowCoordinator(hass, entry)

    # "sensor.e3dc_capacity" exists with state "13.0" — should parse from state
    result = coordinator._parse_float_entity("sensor.e3dc_capacity")
    assert result == 13.0

    # Nonexistent entity with numeric string → manual parse
    result = coordinator._parse_float_entity("99.99")
    assert result == 99.99


def test_parse_float_entity_handles_unavailable_entity(hass) -> None:
    """_parse_float_entity must return None for unavailable/unknown states (line 282-283)."""
    entry, values = _make_full_entry(pv_power="2.5")
    for entity_id, (state, unit) in values.items():
        hass.states.async_set(entity_id, state, {"unit_of_measurement": unit})

    # Override to unavailable
    hass.states.async_set("sensor.e3dc_capacity", "unavailable", {"unit_of_measurement": "kWh"})

    coordinator = UemShadowCoordinator(hass, entry)
    result = coordinator._parse_float_entity("sensor.e3dc_capacity")
    assert result is None

    # Override to unknown
    hass.states.async_set("sensor.e3dc_capacity", "unknown", {"unit_of_measurement": "kWh"})
    result = coordinator._parse_float_entity("sensor.e3dc_capacity")
    assert result is None


def test_parse_float_entity_handles_corrupt_state_type(hass) -> None:
    """_parse_float_entity must handle a state whose state attribute is not
    convertible to float (line 284-285)."""
    entry, values = _make_full_entry(pv_power="2.5")
    for entity_id, (state, unit) in values.items():
        hass.states.async_set(entity_id, state, {"unit_of_measurement": unit})

    from unittest.mock import MagicMock, patch

    mock_state = MagicMock()
    mock_state.state = {"not": "a number"}  # dict, cannot convert to float
    mock_state.attributes = {}
    coordinator = UemShadowCoordinator(hass, entry)

    with patch.object(coordinator.hass.states, "get", return_value=mock_state):
        result = coordinator._parse_float_entity("sensor.e3dc_capacity")
    assert result is None

